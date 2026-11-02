#!/usr/bin/env python3
"""End-to-end test of the Sea Siege online hub (server.py).

Joins two fake players over the real HTTP API, opens both SSE streams, then walks a
whole trade: request -> invite -> accept -> offers -> lock -> confirm -> execute.
Exits non-zero if any step misbehaves.

    python tools/test_trade_hub.py [--url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.request

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(("  ok   " if ok else "  FAIL ") + label + (("  <- " + detail) if detail else ""))
    if not ok:
        FAILS.append(label + (" " + detail if detail else ""))


def post(url: str, path: str, body: dict, expect_error: bool = False) -> dict:
    """POST JSON. A 4xx is a legitimate answer here, so unwrap it into the body."""
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        if not expect_error and exc.code >= 500:
            raise
        try:
            return json.loads(exc.read().decode())
        except Exception:
            return {"ok": False, "status": exc.code}


class Stream(threading.Thread):
    """Consumes one SSE stream and parks events in self.events."""

    def __init__(self, url: str, cid: str, token: str) -> None:
        super().__init__(daemon=True)
        self.url, self.cid, self.token = url, cid, token
        self.events: list[dict] = []
        self.alive = True

    def run(self) -> None:
        req = urllib.request.Request(f"{self.url}/api/events?id={self.cid}&token={self.token}")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if line.startswith("data:"):
                        try:
                            self.events.append(json.loads(line[5:].strip()))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            self.alive = False

    def wait(self, kind: str, timeout: float = 6.0, tid: str | None = None) -> dict | None:
        """Wait for the *next* matching event and consume it (so repeats are visible)."""
        end = time.time() + timeout
        while time.time() < end:
            for e in list(self.events):
                if e.get("kind") == kind and (tid is None or e.get("tradeId") == tid):
                    self.events.remove(e)
                    return e
            time.sleep(0.05)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()
    url = args.url.rstrip("/")
    print(f"hub: {url}")

    health = json.loads(urllib.request.urlopen(url + "/api/health", timeout=10).read())
    check("hub answers /api/health", health.get("ok") is True, json.dumps(health))

    a = post(url, "/api/join", {"name": "TestAlpha", "prof": "local:alpha", "worth": 1200})
    b = post(url, "/api/join", {"name": "TestBravo", "prof": "local:bravo", "worth": 340})
    check("two players joined", bool(a.get("id")) and bool(b.get("id")))
    check("join returns a session token", bool(a.get("token")) and a["token"] != b["token"])

    sa, sb = Stream(url, a["id"], a["token"]), Stream(url, b["id"], b["token"])
    sa.start(); sb.start()
    check("A got hello", sa.wait("hello") is not None)
    check("B got hello", sb.wait("hello") is not None)

    # A must see both players, with B's reported worth. A's first presence event is
    # the one from its own join (before B existed), so wait for the list to grow.
    def presence_with(stream, n: int, timeout: float = 6.0) -> dict | None:
        end = time.time() + timeout
        while time.time() < end:
            e = stream.wait("presence", timeout=end - time.time())
            if e and len(e.get("players") or []) >= n:
                return e
        return None

    seen = presence_with(sa, 2)
    players = [p for p in ((seen or {}).get("players") or []) if p["name"].startswith("Test")]
    names = sorted(p["name"] for p in players)
    check("presence lists both players", len(players) == 2, str(names))
    bravo = next((p for p in players if p["name"] == "TestBravo"), {})
    check("presence carries worth + host", bravo.get("worth") == 340 and bravo.get("host") == "local",
          json.dumps(bravo))

    # ---- trade: request -> invite -> accept -> open -------------------------
    r = post(url, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-request", "to": b["id"]})
    check("A's trade request accepted by hub", r.get("ok") is True, json.dumps(r))
    tid = r.get("tradeId")
    check("hub returned a trade id", bool(tid))
    invite = sb.wait("trade-invite", 4.0)
    check("B received the invitation", invite is not None and invite.get("from", {}).get("name") == "TestAlpha",
          json.dumps(invite or {}))

    post(url, "/api/signal", {"id": b["id"], "token": b["token"], "kind": "trade-accept", "tradeId": tid})
    opened = sa.wait("trade-open", 4.0)
    check("A was told B accepted", opened is not None and opened.get("peer", {}).get("name") == "TestBravo",
          json.dumps(opened or {}))

    # ---- offers -------------------------------------------------------------
    post(url, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer", "tradeId": tid,
                              "payload": {"items": ["env:volcanic"], "worth": 1200, "locked": False}})
    got = sb.wait("trade-offer", 4.0)
    check("B live-previews A's unlocked offer",
          got is not None and got.get("items") == ["env:volcanic"] and got.get("locked") is False,
          json.dumps(got or {}))

    # confirming before both locks must be refused
    r = post(url, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-confirm", "tradeId": tid})
    check("confirm refused while the offer is unlocked", r.get("ok") is False, json.dumps(r))

    post(url, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer", "tradeId": tid,
                              "payload": {"items": ["env:volcanic"], "worth": 1200, "locked": True}})
    post(url, "/api/signal", {"id": b["id"], "token": b["token"], "kind": "trade-offer", "tradeId": tid,
                              "payload": {"items": ["fx:ember", "banner:kraken"], "worth": 300, "locked": True}})
    a_side = sa.wait("trade-offer", 4.0)
    b_side = sb.wait("trade-offer", 4.0)
    check("each side sees the other's locked offer",
          bool(a_side and a_side.get("locked")) and bool(b_side and b_side.get("locked")))

    # locked offers cannot be edited
    r = post(url, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer", "tradeId": tid,
                                  "payload": {"items": [], "worth": 0, "locked": False}})
    check("a locked offer cannot be changed", r.get("ok") is False, json.dumps(r))

    # ---- confirm twice -> execute ------------------------------------------
    r1 = post(url, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-confirm", "tradeId": tid})
    check("A confirm accepted, not both yet", r1.get("ok") and r1.get("both") is False, json.dumps(r1))
    check("B sees that A confirmed", sb.wait("trade-confirmed", 4.0) is not None)
    r2 = post(url, "/api/signal", {"id": b["id"], "token": b["token"], "kind": "trade-confirm", "tradeId": tid})
    check("B confirm completes the trade", r2.get("ok") and r2.get("both") is True, json.dumps(r2))

    ea = sa.wait("trade-execute", 4.0, tid)
    eb = sb.wait("trade-execute", 4.0, tid)
    check("A got an execute with matching sides",
          bool(ea) and ea.get("mine") == ["env:volcanic"] and sorted(ea.get("theirs", [])) == ["banner:kraken", "fx:ember"],
          json.dumps(ea or {}))
    check("B got the mirrored execute",
          bool(eb) and sorted(eb.get("mine", [])) == ["banner:kraken", "fx:ember"] and eb.get("theirs") == ["env:volcanic"],
          json.dumps(eb or {}))
    # The trade is finished when the hub refuses further signals for it (the global
    # trade count is not a safe assertion - real players may be connected).
    after = post(url, "/api/signal", {"id": a["id"], "token": a["token"],
                                      "kind": "trade-confirm", "tradeId": tid})
    check("trade cleared from the hub", after.get("ok") is False, json.dumps(after))

    # ---- rejecting a second trade, then leave ------------------------------
    r = post(url, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-request", "to": b["id"]})
    tid2 = r.get("tradeId")
    post(url, "/api/signal", {"id": b["id"], "token": b["token"], "kind": "trade-decline", "tradeId": tid2})
    check("decline closes the trade", sa.wait("trade-cancel", 4.0, tid2) is not None)

    post(url, "/api/ping", {"id": a["id"], "token": a["token"], "worth": 9999})
    pres = sb.wait("presence", 3.0)
    # presence may already have been consumed; a fresh ping from B refreshes it
    post(url, "/api/ping", {"id": b["id"], "token": b["token"]})
    time.sleep(0.3)
    seen = [e for e in sb.events if e.get("kind") == "presence"]
    worths = [p.get("worth") for p in (seen[-1]["players"] if seen else [])]
    check("worth updates propagate through presence", 9999 in worths, str(worths))

    bad = post(url, "/api/signal", {"id": "deadbeef", "token": "nope", "kind": "trade-request", "to": b["id"]})
    check("a bad session token is refused", bad.get("ok") is False, json.dumps(bad))

    post(url, "/api/leave", {"id": a["id"], "token": a["token"]})
    post(url, "/api/leave", {"id": b["id"], "token": b["token"]})
    time.sleep(0.6)
    live = json.loads(urllib.request.urlopen(url + "/api/players", timeout=10).read())["players"]
    ids = {p["id"] for p in live}
    check("both players left cleanly", a["id"] not in ids and b["id"] not in ids,
          str(sorted(p["name"] for p in live)))

    print()
    if FAILS:
        print(f"{len(FAILS)} check(s) FAILED:")
        for f in FAILS:
            print("  - " + f)
        return 1
    print("all hub checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
