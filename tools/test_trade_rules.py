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
        import re as _re
        for key in _re.findall(r'"([^"]+)"', _re.search(r"MYTHIC_ORDER\s*=\s*\[([^\]]*)\]", html).group(1)):
            fresh[f"turret:{key}"] = "mythic"

        src = (ROOT / "server.py").read_text(encoding="utf-8")
        m = _re.search(r"TRADE_RARITY = (\{.*?\})\n", src, _re.S)
        server_map = json.loads(m.group(1))
        check("server item table matches index.html", server_map == fresh,
              f"{len(server_map)} vs {len(fresh)}")
        check("only rare+ ids are tradeable",
              sum(1 for v in server_map.values() if v != "common") == 24,
              str({v: list(server_map.values()).count(v) for v in set(server_map.values())}))
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
