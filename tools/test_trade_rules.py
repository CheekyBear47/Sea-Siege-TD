#!/usr/bin/env python3
"""Does the hub actually refuse basic gear in a trade?

Starts its own server, joins two players, opens a trade and offers a Common item
(must be refused) then a Rare one (must be accepted).

    python tools/test_trade_rules.py
"""
from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  -> {detail}" if not ok else ""))
    if not ok:
        FAILED.append(label)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(base: str, path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, {}


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    tmp = Path(tempfile.mkdtemp(prefix="seasiege_trade_"))
    log = open(tmp / "server.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "server.py"), "--port", str(port), "--host", "127.0.0.1",
         "--no-ngrok", "--accounts", str(tmp / "accounts.json"), "--root", str(ROOT)],
        stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT))
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=2)
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("server did not start; see", log.name)
            return 1

        st, a = post(base, "/api/join", {"name": "Alpha", "prof": "test-a", "worth": 0})
        st, b = post(base, "/api/join", {"name": "Bravo", "prof": "test-b", "worth": 0})
        check("two players joined", bool(a.get("id")) and bool(b.get("id")), f"{a} {b}")

        st, r = post(base, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-request",
                                           "to": b["id"], "payload": {}})
        check("trade requested", st == 200 and r.get("tradeId"), str(r))
        tid = r.get("tradeId")
        post(base, "/api/signal", {"id": b["id"], "token": b["token"], "kind": "trade-accept",
                                   "tradeId": tid, "payload": {}})

        st, r = post(base, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer",
                                           "tradeId": tid,
                                           "payload": {"items": ["env:dawn"], "worth": 10, "locked": False}})
        check("Common offer refused (400)", st == 400 and "Rare" in r.get("error", ""), f"{st} {r}")

        st, r = post(base, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer",
                                           "tradeId": tid,
                                           "payload": {"items": ["fleet:royal"], "worth": 10, "locked": False}})
        check("second Common offer refused", st == 400, f"{st} {r}")

        st, r = post(base, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer",
                                           "tradeId": tid,
                                           "payload": {"items": ["env:sunset"], "worth": 50, "locked": False}})
        check("Rare offer accepted", st == 200 and r.get("ok"), f"{st} {r}")

        st, r = post(base, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer",
                                           "tradeId": tid,
                                           "payload": {"items": ["turret:kraken"], "worth": 10000, "locked": True}})
        check("Mythic turret card accepted", st == 200, f"{st} {r}")

        st, r = post(base, "/api/signal", {"id": a["id"], "token": a["token"], "kind": "trade-offer",
                                           "tradeId": tid,
                                           "payload": {"items": ["nonsense:thing"], "worth": 0, "locked": False}})
        check("unknown item refused", st == 400, f"{st} {r}")

        # the generated table must agree with a fresh parse of index.html
        sys.path.insert(0, str(ROOT))
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "gen_trade_rarity.py")
        gen = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
        spec.loader.exec_module(gen)                          # type: ignore[union-attr]
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        fresh: dict[str, str] = {}
        for name, prefix in gen.TABLES.items():
            for line in gen.table_block(html, name).splitlines():
                m = gen.RARITY_RE.match(line)
                if m:
                    fresh[f"{prefix}:{m.group(1)}"] = m.group(2)
        # turret cards: every order list the client defines, so a new tier cannot make
        # this parse disagree with the generated table
        import re as _re
        for order_name in ("MYTHIC_ORDER", "SECRET_ORDER"):
            found = _re.search(rf"{order_name}\s*=\s*\[([^\]]*)\]", html)
            if not found:
                continue
            rarity = "secret" if order_name == "SECRET_ORDER" else "mythic"
            for key in _re.findall(r'"([^"]+)"', found.group(1)):
                fresh[f"turret:{key}"] = rarity

        src = (ROOT / "server.py").read_text(encoding="utf-8")
        m = _re.search(r"TRADE_RARITY = (\{.*?\})\n", src, _re.S)
        server_map = json.loads(m.group(1))
        check("server item table matches index.html", server_map == fresh,
              f"{len(server_map)} vs {len(fresh)}")
        # tradeability is decided by the server's own ladder, so a new rarity cannot
        # silently become untradeable (or tradeable)
        rank_src = _re.search(r"RARITY_RANK = (\{.*?\})\n", src, _re.S)
        ranks = json.loads(rank_src.group(1))
        min_rank = ranks.get("rare", 1)
        tradeable_ids = [k for k, v in server_map.items() if ranks.get(v, -1) >= min_rank]
        refused_ids = [k for k, v in server_map.items() if ranks.get(v, -1) < min_rank]
        check("every item maps to a rarity the ladder knows",
              all(v in ranks for v in server_map.values()),
              str(sorted(set(server_map.values()) - set(ranks))))
        check("the only refused items are the sub-rare ones (the starter gear)",
              all(server_map[k] in ("common",) for k in refused_ids),
              f"refused: {sorted(set(server_map[k] for k in refused_ids))}")
        check("the rare+ set is what the trade endpoint accepts",
              len(tradeable_ids) + len(refused_ids) == len(server_map) and len(tradeable_ids) > 0,
              f"{len(tradeable_ids)} tradeable, {len(refused_ids)} refused, of {len(server_map)}")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
        try:
            log.close()
        except Exception:
            pass

    print()
    if FAILED:
        print(f"{len(FAILED)} check(s) FAILED")
        return 1
    print("all trade-rule checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
