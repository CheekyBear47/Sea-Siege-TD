#!/usr/bin/env python3
"""End-to-end test for the account store: Google keying, cross-device load, local accounts.

Starts its own server on a spare port with a throwaway accounts file, drives the real
HTTP API, and exits non-zero on the first failed assertion.

    python tools/test_account_sync.py
"""
from __future__ import annotations

import base64
import json
import os
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
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  -> ' + detail) if detail and not ok else ''}")
    if not ok:
        FAILED.append(label)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(base: str, path: str, body: dict, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, {}


def fake_google_token(sub: str, email: str, name: str) -> str:
    """A well-formed unsigned JWT - accepted only while verification is off."""
    def part(obj) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return ".".join([part({"alg": "none", "typ": "JWT"}),
                     part({"sub": sub, "email": email, "name": name, "picture": ""}),
                     "sig"])


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    tmp = Path(tempfile.mkdtemp(prefix="seasiege_acct_"))
    accounts = tmp / "accounts.json"
    log = open(tmp / "server.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "server.py"), "--port", str(port), "--host", "127.0.0.1",
         "--no-ngrok", "--no-verify-google", "--accounts", str(accounts), "--root", str(ROOT)],
        stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT))
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=2) as r:
                    health = json.loads(r.read().decode())
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("server did not come up; log tail:")
            print(log.name)
            return 1

        print(f"\nserver up on {base} (accounts -> {accounts.name})")
        print(f"health: {health}")

        # ---------------------------------------------------------------- google, first device
        print("\n[1] first Google sign-in on device A")
        st, j = post(base, "/api/account/google", {"credential": fake_google_token("sub-A", "iron@example.com", "Iron Fisher")})
        check("login accepted", st == 200 and j.get("ok"), str(j))
        check("flagged as created", j.get("created") is True, str(j.get("created")))
        check("needsUsername is true", j.get("needsUsername") is True, str(j.get("needsUsername")))
        check("keyed by the Google sub", j.get("account", {}).get("id") == "google:sub-A",
              str(j.get("account", {}).get("id")))
        tok_a = j.get("token")
        check("a session token came back", bool(tok_a))

        print("\n[2] username onboarding")
        st, j = post(base, "/api/account/username", {"token": tok_a, "username": "IronTeddy"})
        check("username accepted", st == 200 and j["account"]["username"] == "IronTeddy", str(j))
        check("needsUsername now false", j.get("needsUsername") is False, str(j.get("needsUsername")))
        for bad in ("ab", "bad name", "x" * 17, "emoji!"):
            st, j = post(base, "/api/account/username", {"token": tok_a, "username": bad})
            check(f"rejects username {bad[:8]!r}", st == 400, f"{st} {j}")

        print("\n[3] profile saved from device A")
        save = {"owner": "google:sub-A", "gems": 42, "owned": {"env:coral": 1, "wrap:aurora": 1},
                "run": {"wave": 7, "gold": 512}}
        st, j = post(base, "/api/account/save",
                     {"token": tok_a, "save": save, "boards": [{"wave": 7, "gems": 42}],
                      "stats": {"bestWave": 7, "gems": 42, "runs": 3}})
        check("save stored", st == 200 and j.get("ok"), str(j))

        # ---------------------------------------------------------------- same account, new device
        print("\n[4] SAME Google account, a different device/origin/IP (the bug being fixed)")
        st, j = post(base, "/api/account/google",
                     {"credential": fake_google_token("sub-A", "iron@example.com", "Iron Fisher")},
                     headers={"X-Forwarded-For": "203.0.113.9", "Origin": "https://elsewhere.example"})
        check("accepted", st == 200 and j.get("ok"), str(j))
        check("NOT created again", j.get("created") is False, str(j.get("created")))
        check("same account id", j["account"]["id"] == "google:sub-A", j["account"]["id"])
        check("no username prompt (returning player)", j.get("needsUsername") is False,
              str(j.get("needsUsername")))
        check("username came back", j["account"]["username"] == "IronTeddy", j["account"]["username"])
        check("inventory came back", j["account"]["save"] == save, str(j["account"].get("save"))[:80])
        check("stats came back", (j["account"].get("stats") or {}).get("bestWave") == 7,
              str(j["account"].get("stats")))
        check("leaderboard came back", bool(j["account"].get("boards")), str(j["account"].get("boards"))[:60])
        check("a fresh token was issued", j["token"] != tok_a)

        print("\n[5] the second device's token loads the profile directly (fast path)")
        tok_b = j["token"]
        st, j = post(base, "/api/account/session", {"token": tok_b})
        check("session loads", st == 200 and j["account"]["username"] == "IronTeddy", str(j)[:120])
        check("save present in the session load", j["account"]["save"] == save)
        st, j = post(base, "/api/account/session", {"token": "not-a-real-token"})
        check("bogus token refused", st == 401, f"{st} {j}")

        # ---------------------------------------------------------------- username collisions
        print("\n[6] a second Google account cannot steal the username")
        st, j = post(base, "/api/account/google", {"credential": fake_google_token("sub-B", "bravo@example.com", "Bravo")})
        tok_c = j["token"]
        st, j = post(base, "/api/account/username", {"token": tok_c, "username": "ironTeddy"})
        check("case-insensitive clash rejected", st == 400 and "taken" in j.get("error", ""), f"{st} {j}")
        st, j = post(base, "/api/account/username", {"token": tok_c, "username": "Bravo_2"})
        check("a free name is accepted", st == 200 and j["account"]["username"] == "Bravo_2", str(j)[:90])

        # ---------------------------------------------------------------- username + password
        print("\n[7] username & password accounts")
        st, j = post(base, "/api/account/register", {"username": "CaptainSalty", "password": "hunter2hunter"})
        check("registered", st == 200 and j["account"]["provider"] == "local", str(j)[:110])
        check("unlocks immediately (no onboarding)", j.get("needsUsername") is False, str(j.get("needsUsername")))
        check("keyed local:<name>", j["account"]["id"] == "local:captainsalty", j["account"]["id"])
        check("no password material leaks", "hash" not in j["account"] and "salt" not in j["account"],
              str(sorted(j["account"].keys())))
        tok_d = j["token"]
        st, j = post(base, "/api/account/register", {"username": "CaptainSalty", "password": "anotherpass"})
        check("duplicate registration refused", st == 400, f"{st} {j}")
        st, j = post(base, "/api/account/register", {"username": "CaptainSalty", "password": "short"})
        check("short password refused", st == 400, f"{st} {j}")
        st, j = post(base, "/api/account/login", {"username": "CaptainSalty", "password": "wrong-password"})
        check("wrong password refused", st == 400 and "Wrong password" in j.get("error", ""), f"{st} {j}")
        st, j = post(base, "/api/account/login", {"username": "captainsalty", "password": "hunter2hunter"})
        check("sign-in works, case-insensitively", st == 200 and j["account"]["id"] == "local:captainsalty",
              f"{st} {str(j)[:90]}")
        tok_e = j["token"]
        st, j = post(base, "/api/account/save", {"token": tok_e, "save": {"gems": 9}, "boards": [], "stats": {"runs": 1}})
        check("local account saves too", st == 200, str(j))

        # ---------------------------------------------------------------- logout + storage
        print("\n[8] logout, and what landed on disk")
        st, j = post(base, "/api/account/logout", {"token": tok_d})
        check("logout ok", st == 200, str(j))
        st, j = post(base, "/api/account/session", {"token": tok_d})
        check("token dead after logout", st == 401, f"{st} {j}")

        blob = json.loads(accounts.read_text(encoding="utf-8"))
        ids = sorted(blob["accounts"])
        check("exactly 3 accounts on disk", len(ids) == 3, str(ids))
        check("no duplicate google record", ids.count("google:sub-A") == 1, str(ids))
        check("google record has its sub", blob["accounts"]["google:sub-A"]["sub"] == "sub-A")
        check("save persisted to disk",
              blob["accounts"]["google:sub-A"]["save"]["gems"] == 42)
        check("local password is hashed, not stored raw",
              blob["accounts"]["local:captainsalty"]["hash"].startswith("pbkdf2$")
              and "hunter2hunter" not in json.dumps(blob))

        with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
            h = json.loads(r.read().decode())
        check("health reports the account count", h.get("accounts") == 3, str(h))

        # ---------------------------------------------------------------- reload persistence
        print("\n[9] restarting the server keeps every account (JSON, not memory)")
        proc.terminate()
        proc.wait(timeout=10)
        log.close()
        log = open(tmp / "server2.log", "w", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "server.py"), "--port", str(port), "--host", "127.0.0.1",
             "--no-ngrok", "--no-verify-google", "--accounts", str(accounts), "--root", str(ROOT)],
            stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT))
        for _ in range(60):
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=2) as r:
                    h = json.loads(r.read().decode())
                break
            except Exception:
                time.sleep(0.25)
        check("accounts survived the restart", h.get("accounts") == 3, str(h))
        st, j = post(base, "/api/account/login", {"username": "CaptainSalty", "password": "hunter2hunter"})
        check("password still works after restart", st == 200, f"{st} {str(j)[:90]}")
        st, j = post(base, "/api/account/google", {"credential": fake_google_token("sub-A", "iron@example.com", "Iron Fisher")})
        check("Google player still resolves to the same account",
              st == 200 and j["account"]["id"] == "google:sub-A" and j["account"]["save"]["gems"] == 42,
              str(j)[:110])

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
        print(f"{len(FAILED)} check(s) FAILED:")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print("all account checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
