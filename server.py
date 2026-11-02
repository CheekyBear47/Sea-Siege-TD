#!/usr/bin/env python3
"""Sea Siege Tower Defense - local static server, online hub and ngrok tunnel.

Two jobs
--------
1. Serve index.html (and friends) from this folder over HTTP.
2. Run a tiny online hub so players on localhost *and* on the public ngrok URL can
   see each other and trade: a Server-Sent Events stream down (/api/events) and a
   few JSON endpoints up (/api/join, /api/ping, /api/signal, /api/players).

Why SSE and not WebSockets: this keeps the whole hub on the standard library - no
extra install, and it passes through ngrok cleanly. A trade is a small state machine
the hub referees (offer -> lock -> confirm x2 -> execute). The items themselves live
in each player's browser storage, so the hub validates the *sequence*, never the
inventory.

Usage
-----
    python server.py                          # local play on :8000, no tunnel
    USE_NGROK=1 python server.py              # also open a public ngrok tunnel
    python server.py --ngrok                  # same, as a flag
    python server.py --port 8080              # pick the port
    python server.py --no-ngrok               # force the tunnel off
    NGROK_AUTHTOKEN=xxxx USE_NGROK=1 python server.py

Cloud hosts (Render, Railway, Fly, Heroku…)
-------------------------------------------
The host tells you which port to listen on through $PORT and expects a bind on
0.0.0.0 - both are honoured automatically:

    PORT=10000 python server.py      # binds 0.0.0.0:10000, no ngrok

ngrok is OFF unless you ask for it, so a cloud host never tries to open a tunnel
behind your back. To enable it set USE_NGROK=1 (or pass --ngrok); the auth token is
then read from --token, $NGROK_AUTHTOKEN, $NGROK_TOKEN, or an existing ngrok login
(ngrok.yml). If pyngrok is missing, no token is available, or the ngrok agent cannot
be launched, the game still serves normally and the tunnel is skipped with a clear
message. The tunnel step is time-bounded so startup never hangs.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import secrets
import socketserver
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8000
CLIENT_TTL = 120.0         # seconds with no ping *and* no open stream before dropping
SWEEP_TTL = 8.0            # no stream + silent this long = a ghost from a page reload
KEEPALIVE = 12.0           # seconds between SSE comments
OFFER_SLOTS = 8            # max items per side of a trade


# --------------------------------------------------------------------------- hub
class Hub:
    """Online registry: who is connected, and which trades are in flight."""

    # Finished trades are kept briefly so a client whose SSE stream dropped mid-trade
    # still learns the result when it reconnects - otherwise one side would swap items
    # and the other would not.
    DONE_TTL = 300.0

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.clients: dict[str, dict] = {}
        self.trades: dict[str, dict] = {}
        self.done: deque = deque(maxlen=40)
        self.rev = 0                      # bumped whenever presence changes

    def remember_done(self, tid: str, a: str, b: str, offers: dict) -> None:
        with self.lock:
            self.done.append({"tid": tid, "a": a, "b": b,
                              "offers": {a: list(offers.get(a, [])), b: list(offers.get(b, []))},
                              "at": time.time()})

    def done_for(self, cid: str) -> list[dict]:
        """Replays this client's settled trades as execute events."""
        out = []
        now = time.time()
        with self.lock:
            for rec in list(self.done):
                if now - rec["at"] > self.DONE_TTL:
                    continue
                if cid == rec["a"]:
                    out.append({"kind": "trade-execute", "tradeId": rec["tid"],
                                "mine": rec["offers"][rec["a"]], "theirs": rec["offers"][rec["b"]],
                                "replay": True})
                elif cid == rec["b"]:
                    out.append({"kind": "trade-execute", "tradeId": rec["tid"],
                                "mine": rec["offers"][rec["b"]], "theirs": rec["offers"][rec["a"]],
                                "replay": True})
        return out

    # --- clients ----------------------------------------------------------
    def sweep(self, silent: float = 8.0) -> list[str]:
        """Drop sessions that have no stream open and stopped pinging.

        A page reload leaves its previous session behind for a few seconds; without
        this, players see (and try to trade with) a ghost.
        """
        gone = []
        now = time.time()
        with self.lock:
            for cid, c in list(self.clients.items()):
                if not c["live"] and now - c["last"] > silent:
                    self.clients.pop(cid, None)
                    gone.append(c["name"])
            if gone:
                self.rev += 1
        return gone

    def add_client(self, name: str, prof: str | None, worth: int, remote: str) -> dict:
        self.sweep()
        client = {
            "id": secrets.token_hex(8),
            "token": secrets.token_hex(16),
            "name": (str(name or "Captain"))[:24],
            "prof": (str(prof or ""))[:64],
            "worth": max(0, int(worth or 0)),
            "host": "local" if str(remote).startswith(("127.", "localhost", "::1")) else "remote",
            "queue": deque(),
            "joined": time.time(),
            "last": time.time(),
            "live": False,
        }
        with self.lock:
            self.clients[client["id"]] = client
            self.rev += 1
        return client

    def get(self, cid: str, token: str | None = None) -> dict | None:
        with self.lock:
            c = self.clients.get(str(cid or ""))
            if not c:
                return None
            if token is not None and token != c["token"]:
                return None
            return c

    def touch(self, cid: str, token: str, **fields) -> dict | None:
        c = self.get(cid, token)
        if not c:
            return None
        changed = False
        with self.lock:
            c["last"] = time.time()
            for k in ("name", "worth"):
                if fields.get(k) is not None:
                    v = str(fields[k])[:24] if k == "name" else max(0, int(fields[k]))
                    if c[k] != v:
                        c[k] = v
                        changed = True
            if changed:
                self.rev += 1
        return c

    def drop(self, cid: str) -> None:
        with self.lock:
            if cid not in self.clients:
                return
            self.clients.pop(cid, None)
            for tid, tr in list(self.trades.items()):
                if cid in (tr["a"], tr["b"]):
                    self.trades.pop(tid, None)
                    self.push(tr["a"], {"kind": "trade-cancel", "tradeId": tid,
                                        "reason": "the other captain disconnected"})
                    self.push(tr["b"], {"kind": "trade-cancel", "tradeId": tid,
                                        "reason": "the other captain disconnected"})
            self.rev += 1

    def push(self, cid: str, event: dict) -> bool:
        with self.lock:
            c = self.clients.get(cid)
            if not c:
                return False
            if len(c["queue"]) > 200:          # a stalled client must not grow forever
                c["queue"].popleft()
            c["queue"].append(event)
            return True

    def broadcast(self, event: dict, skip: str | None = None) -> None:
        with self.lock:
            ids = list(self.clients)
        for cid in ids:
            if cid != skip:
                self.push(cid, event)

    def public_players(self) -> list[dict]:
        with self.lock:
            return [{"id": c["id"], "name": c["name"], "prof": c["prof"], "worth": c["worth"],
                     "host": c["host"], "since": int(c["joined"])}
                    for c in self.clients.values()]

    def presence_event(self) -> dict:
        with self.lock:
            self.rev += 1
            return {"kind": "presence", "rev": self.rev, "players": self.public_players()}

    # --- trades -----------------------------------------------------------
    def start_trade(self, a: str, b: str) -> dict | None:
        with self.lock:
            if a == b or a not in self.clients or b not in self.clients:
                return None
            for tr in self.trades.values():
                if {a, b} <= {tr["a"], tr["b"]}:
                    return None                       # already trading with each other
            tid = secrets.token_hex(6)
            trade = {"id": tid, "a": a, "b": b, "offers": {a: {}, b: {}},
                     "confirmed": {}, "at": time.time()}
            self.trades[tid] = trade
            return trade

    def trade_for(self, cid: str, tid: str) -> dict | None:
        with self.lock:
            tr = self.trades.get(str(tid or ""))
            if not tr or cid not in (tr["a"], tr["b"]):
                return None
            return tr

    def end_trade(self, tid: str, reason: str) -> None:
        with self.lock:
            tr = self.trades.pop(tid, None)
        if tr:
            for who in (tr["a"], tr["b"]):
                self.push(who, {"kind": "trade-cancel", "tradeId": tid, "reason": reason})


HUB = Hub()


# ----------------------------------------------------------------------- handler
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Static handler plus the /api/* online hub, with one compact log line."""

    server_version = "SeaSiege/1.0"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - stdlib signature
        sys.stdout.write("  · %s - %s\n" % (self.address_string(), fmt % args))

    def handle_one_request(self) -> None:
        # A browser closing an SSE stream (or a tab) is normal traffic, not a crash:
        # swallow the aborted/reset errors the stdlib would otherwise traceback on.
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # --- helpers ----------------------------------------------------------
    def _json(self, obj: dict | list, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 65536:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8", "replace") or "{}")
        except Exception:  # noqa: BLE001 - a malformed body is the caller's problem
            return {}

    @property
    def _remote(self) -> str:
        fwd = self.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "?"

    # --- routing ----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        path = urlparse(self.path).path
        if path == "/api/events":
            return self._sse()
        if path == "/api/players":
            return self._json({"players": HUB.public_players()})
        if path == "/api/health":
            return self._json({"ok": True, "players": len(HUB.clients), "trades": len(HUB.trades)})
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        path = urlparse(self.path).path
        body = self._body()
        if path == "/api/join":
            client = HUB.add_client(body.get("name"), body.get("prof"), body.get("worth"), self._remote)
            print(f"  + online: {client['name']} ({client['host']}) worth {client['worth']:,}"
                  f" - {len(HUB.clients)} player(s)")
            HUB.broadcast(HUB.presence_event())
            return self._json({"id": client["id"], "token": client["token"],
                               "you": client["id"], "players": HUB.public_players()})
        if path == "/api/ping":
            rev_before = HUB.rev
            c = HUB.touch(body.get("id"), body.get("token") or "",
                          name=body.get("name"), worth=body.get("worth"))
            if not c:
                return self._json({"ok": False, "error": "unknown session"}, 403)
            if HUB.rev != rev_before:
                # the name or worth changed - let everyone's player list catch up
                HUB.broadcast(HUB.presence_event(), skip=c["id"])
            return self._json({"ok": True, "players": HUB.public_players(), "rev": HUB.rev})
        if path == "/api/leave":
            c = HUB.get(body.get("id"), body.get("token") or "")
            if c:
                print(f"  - offline: {c['name']}")
                HUB.drop(c["id"])
                HUB.broadcast(HUB.presence_event())
            return self._json({"ok": True})
        if path == "/api/signal":
            return self._signal(body)
        return self._json({"error": "not found"}, 404)

    # --- trade signalling -------------------------------------------------
    def _signal(self, body: dict) -> None:
        me = HUB.get(body.get("id"), body.get("token") or "")
        if not me:
            return self._json({"ok": False, "error": "unknown session"}, 403)
        HUB.touch(me["id"], me["token"])
        kind = str(body.get("kind") or "")
        payload = body.get("payload") or {}

        if kind == "trade-request":
            peer = HUB.get(body.get("to"))
            if not peer:
                return self._json({"ok": False, "error": "that player just went offline"})
            trade = HUB.start_trade(me["id"], peer["id"])
            if not trade:
                return self._json({"ok": False, "error": "a trade with that player is already open"})
            HUB.push(peer["id"], {"kind": "trade-invite", "tradeId": trade["id"],
                                  "from": {"id": me["id"], "name": me["name"], "worth": me["worth"]}})
            return self._json({"ok": True, "tradeId": trade["id"],
                               "peer": {"id": peer["id"], "name": peer["name"], "worth": peer["worth"]}})

        tid = str(body.get("tradeId") or "")
        trade = HUB.trade_for(me["id"], tid)
        if not trade:
            return self._json({"ok": False, "error": "no such trade"})
        other = trade["b"] if me["id"] == trade["a"] else trade["a"]
        if kind in ("trade-offer", "trade-confirm", "trade-accept"):
            detail = ""
            if kind == "trade-offer":
                detail = f" items={payload.get('items')} locked={bool(payload.get('locked'))}"
            print(f"  ~ {kind} from {me['name']} (trade {tid}){detail}", flush=True)

        if kind == "trade-accept":
            HUB.push(other, {"kind": "trade-open", "tradeId": tid,
                             "peer": {"id": me["id"], "name": me["name"], "worth": me["worth"]}})
            return self._json({"ok": True})

        if kind in ("trade-decline", "trade-cancel"):
            HUB.end_trade(tid, "declined" if kind == "trade-decline" else "cancelled")
            return self._json({"ok": True})

        if kind == "trade-offer":
            items = payload.get("items") or []
            if not isinstance(items, list):
                items = []
            items = [str(i)[:64] for i in items][:OFFER_SLOTS]
            locked = bool(payload.get("locked"))
            worth = max(0, int(payload.get("worth") or 0))
            mine = trade["offers"][me["id"]]
            if locked:
                mine["locked"] = True
                mine["items"] = items
                mine["worth"] = worth
                trade["confirmed"].pop(me["id"], None)
            else:
                if mine.get("locked"):
                    return self._json({"ok": False, "error": "your offer is locked - unlock it first"})
                mine["items"] = items
                mine["worth"] = worth
                # the terms just changed, so any confirmation is void
                trade["confirmed"].clear()
            HUB.push(other, {"kind": "trade-offer", "tradeId": tid, "from": me["id"],
                             "items": items, "worth": worth, "locked": locked})
            return self._json({"ok": True})

        if kind == "trade-confirm":
            mine = trade["offers"][me["id"]]
            their = trade["offers"][other]
            if not mine.get("locked"):
                return self._json({"ok": False, "error": "lock your offer first"})
            if not their.get("locked"):
                return self._json({"ok": False, "error": "the other captain has not locked their offer yet"})
            trade["confirmed"][me["id"]] = True
            print(f"  ~ confirm from {me['name']}: {len(trade['confirmed'])}/2", flush=True)
            HUB.push(other, {"kind": "trade-confirmed", "tradeId": tid, "from": me["id"]})
            if len(trade["confirmed"]) == 2:
                a_offer = list(trade["offers"][trade["a"]].get("items", []))
                b_offer = list(trade["offers"][trade["b"]].get("items", []))
                HUB.remember_done(tid, trade["a"], trade["b"],
                                  {trade["a"]: a_offer, trade["b"]: b_offer})
                HUB.push(trade["a"], {"kind": "trade-execute", "tradeId": tid,
                                      "mine": a_offer, "theirs": b_offer})
                HUB.push(trade["b"], {"kind": "trade-execute", "tradeId": tid,
                                      "mine": b_offer, "theirs": a_offer})
                with HUB.lock:
                    HUB.trades.pop(tid, None)
                names = (HUB.clients.get(trade["a"], {}).get("name", "?"),
                         HUB.clients.get(trade["b"], {}).get("name", "?"))
                print(f"  = trade executed: {names[0]} gave {a_offer} for {names[1]}'s {b_offer}",
                      flush=True)
            return self._json({"ok": True, "both": len(trade["confirmed"]) == 2})
        return self._json({"ok": False, "error": "unknown signal"})

    # --- server-sent events ----------------------------------------------
    def _sse(self) -> None:
        qs = parse_qs(urlparse(self.path).query)
        cid = (qs.get("id") or [""])[0]
        token = (qs.get("token") or [""])[0]
        c = HUB.get(cid, token)
        if not c:
            return self._json({"ok": False, "error": "unknown session"}, 403)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        queue = c["queue"]
        with HUB.lock:
            c["live"] = True
        try:
            self._write_event({"kind": "hello", "you": c["id"],
                               "players": HUB.public_players(), "rev": HUB.rev})
            for replay in HUB.done_for(c["id"]):
                self._write_event(replay)          # a trade this client may have missed
            last = time.time()
            while True:
                # An open stream is proof of life: browsers throttle timers in hidden
                # tabs, so a player sitting in a background tab would otherwise stop
                # pinging and get reaped mid-trade.
                with HUB.lock:
                    c["last"] = time.time()
                try:
                    event = queue.popleft()
                except IndexError:
                    event = None
                if event is not None:
                    self._write_event(event)
                    last = time.time()
                    continue
                if time.time() - last > KEEPALIVE:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last = time.time()
                time.sleep(0.25)
        except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
            pass
        finally:
            with HUB.lock:
                c["live"] = False
            if time.time() - c["last"] > CLIENT_TTL:
                HUB.drop(c["id"])
                HUB.broadcast(HUB.presence_event())

    def _write_event(self, event: dict) -> None:
        data = json.dumps(event).encode("utf-8")
        self.wfile.write(b"event: msg\ndata: " + data + b"\n\n")
        self.wfile.flush()


class ReusableServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ------------------------------------------------------------------- maintenance
TRADE_TTL = 600.0          # an abandoned trade is closed after this long


def reaper() -> None:
    """Drop players who stopped pinging, and close trades nobody finished."""
    while True:
        time.sleep(4.0)
        now = time.time()
        with HUB.lock:
            stale = [tid for tid, tr in HUB.trades.items() if now - tr["at"] > TRADE_TTL]
        for tid in stale:
            print(f"  - trade {tid} timed out", flush=True)
            HUB.end_trade(tid, "timed out")
        removed = HUB.sweep()
        with HUB.lock:
            now = time.time()
            for cid, c in list(HUB.clients.items()):
                if now - c["last"] > CLIENT_TTL:
                    HUB.clients.pop(cid, None)
                    removed.append(c["name"])
        if removed:
            for name in removed:
                print(f"  - timed out: {name}")
            HUB.broadcast(HUB.presence_event())


def env_port() -> int:
    """The port to listen on: $PORT when the host sets one (Render and friends), else 8000."""
    raw = (os.environ.get("PORT") or "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        print(f"[env] PORT={raw!r} is not a number - using {DEFAULT_PORT}")
        return DEFAULT_PORT
    if not 1 <= port <= 65535:
        print(f"[env] PORT={port} is out of range - using {DEFAULT_PORT}")
        return DEFAULT_PORT
    return port


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Serve Sea Siege Tower Defense (cloud-host friendly) and optionally open an ngrok tunnel.")
    p.add_argument("--port", type=int, default=env_port(),
                   help="port to listen on (default: $PORT, else 8000)")
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"),
                   help="bind address (default: $HOST, else 0.0.0.0)")
    p.add_argument("--token", default=None, help="ngrok auth token (or set NGROK_AUTHTOKEN)")
    p.add_argument("--root", default=str(ROOT), help="directory to serve")
    p.add_argument("--ngrok", action="store_true", help="open an ngrok tunnel (same as USE_NGROK=1)")
    p.add_argument("--no-ngrok", action="store_true", help="force the tunnel off, whatever else is set")
    p.add_argument("--region", default=None, help="optional ngrok region (e.g. au, eu, us)")
    return p.parse_args()


def resolve_token(cli_token: str | None) -> str | None:
    """Token precedence: --token, $NGROK_AUTHTOKEN, $NGROK_TOKEN, an existing ngrok login."""
    tok = cli_token or os.environ.get("NGROK_AUTHTOKEN") or os.environ.get("NGROK_TOKEN")
    if tok:
        return tok.strip()
    candidates = [
        Path(os.path.expanduser("~")) / "AppData/Local/ngrok/ngrok.yml",   # Windows
        Path(os.path.expanduser("~")) / ".config/ngrok/ngrok.yml",         # Linux / macOS
        Path(os.path.expanduser("~")) / "Library/Application Support/ngrok/ngrok.yml",
        Path(os.path.expanduser("~")) / ".ngrok2/ngrok.yml",
    ]
    for cfg in candidates:
        try:
            if not cfg.is_file():
                continue
            for line in cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith("authtoken:"):
                    value = line.split(":", 1)[1].strip().strip("'\"")
                    if value:
                        print(f"[ngrok] using the authtoken stored in {cfg}")
                        return value
        except OSError:
            continue
    return None


def start_tunnel(port: int, token: str | None, region: str | None, timeout: float = 30.0) -> str | None:
    """Open an ngrok tunnel, bounded in time. Returns the public https URL or None.

    The connect runs on a worker thread: ngrok's first run downloads its agent and
    can stall indefinitely behind a firewall or security policy, and the server must
    still come up. If it times out we keep serving locally.
    """
    try:
        from pyngrok import conf, ngrok
    except ImportError:
        print("[ngrok] pyngrok is not installed - run: pip install -r requirements.txt")
        print("[ngrok] continuing without a public tunnel.\n")
        return None

    if token:
        try:
            ngrok.set_auth_token(token)
        except Exception as exc:  # noqa: BLE001 - agent may be blocked, or already configured
            # "Authtoken already set in configuration file" is not a failure: the agent
            # is already configured, so carry on and let the connect attempt decide.
            print(f"[ngrok] note: could not write the token ({type(exc).__name__}) - "
                  "continuing with the agent's existing configuration")

    box: dict[str, object] = {}

    def _connect() -> None:
        try:
            if region:
                conf.get_default().region = region
            tunnel = ngrok.connect(port, "http")
            box["url"] = getattr(tunnel, "public_url", str(tunnel))
        except Exception as exc:  # noqa: BLE001 - surfaced below
            box["err"] = exc

    worker = threading.Thread(target=_connect, daemon=True)
    worker.start()
    worker.join(timeout)

    if "url" in box:
        url = str(box["url"])
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        return url

    if "err" in box:
        print(f"[ngrok] tunnel failed: {box['err']}")
        text = str(box["err"])
        if "ERR_NGROK_108" in text or "simultaneous ngrok agent sessions" in text:
            print("[ngrok] the free plan allows 3 agent sessions at once, and this account has")
            print("[ngrok] that many already open (stale sessions from restarted servers count).")
            print("[ngrok] fix: open https://dashboard.ngrok.com/agents and kill the old sessions,")
            print("[ngrok] or wait a few minutes for them to expire, then start the server again.")
        elif "ERR_NGROK_334" in text or "already online" in text:
            print("[ngrok] another ngrok agent is already holding this domain.")
            print("[ngrok] close the other session (or Task Manager -> end every ngrok.exe), then retry.")
        elif not token:
            print("[ngrok] no token supplied and no ngrok login was found.")
            print("[ngrok] get a free token at https://dashboard.ngrok.com/get-started/your-authtoken")
            print("[ngrok] then: set NGROK_AUTHTOKEN=xxxx  (or --token xxxx)")
        print("[ngrok] continuing with local hosting only.\n")
        return None

    print(f"[ngrok] no response after {timeout:.0f}s (agent download or security policy?) - "
          "still trying in the background; check https://dashboard.ngrok.com/agents")
    print("[ngrok] continuing with local hosting only.\n")
    return None


def _serve_forever(httpd: ReusableServer) -> int:
    """Block until Ctrl+C, then close the server (and any ngrok agent) cleanly."""
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nshutting down…")
    finally:
        try:
            from pyngrok import ngrok as _ngrok
            _ngrok.kill()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
        httpd.shutdown()
        httpd.server_close()
    return 0


def main() -> int:
    args = parse_args()
    root = str(Path(args.root).resolve())
    handler = functools.partial(QuietHandler, directory=root)

    print("=" * 66)
    print("  SEA SIEGE TOWER DEFENSE")
    print("=" * 66)
    print(f"  serving : {root}")

    try:
        httpd = ReusableServer((args.host, args.port), handler)
    except OSError as exc:
        print(f"  !! cannot bind {args.host}:{args.port} -> {exc}")
        print("     try: python server.py --port 8080")
        return 1

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    threading.Thread(target=reaper, daemon=True).start()

    # ngrok only runs when it is asked for, so a cloud host (or a plain local run)
    # never reaches out to it by surprise.
    want_tunnel = (bool(os.environ.get("USE_NGROK")) or args.ngrok) and not args.no_ngrok

    if not want_tunnel:
        print(f"Server starting on port {args.port}")
        print(f"  local   : http://localhost:{args.port}/")
        print(f"  lan     : http://<your-ip>:{args.port}/")
        print("  hub     : /api/events (SSE) - /api/join - /api/signal - /api/players")
        print("  ngrok   : off  (set USE_NGROK=1 or pass --ngrok for a public link)")
        print("=" * 66)
        print("  Ctrl+C to stop.\n")
        return _serve_forever(httpd)

    print(f"Server starting on port {args.port} (with ngrok)")
    print(f"  local   : http://localhost:{args.port}/")
    print(f"  lan     : http://<your-ip>:{args.port}/")
    print("  hub     : /api/events (SSE) - /api/join - /api/signal - /api/players")

    public_url = start_tunnel(args.port, resolve_token(args.token), args.region)

    if public_url:
        print(f"  PUBLIC  : {public_url}")
        print("            ^ share this HTTPS link (may show an ngrok interstitial first)")
        print("            ^ everyone on it shows up in Trading & Players automatically")
    else:
        print("  PUBLIC  : (no tunnel - start the server with USE_NGROK=1 for remote play)")

    print("=" * 66)
    print("  Ctrl+C to stop.\n")
    return _serve_forever(httpd)


if __name__ == "__main__":
    raise SystemExit(main())
