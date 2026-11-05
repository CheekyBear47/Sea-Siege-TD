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
import hashlib
import hmac
import http.server
import json
import os
import re
import secrets
import socketserver
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8000
CLIENT_TTL = 120.0         # seconds with no ping *and* no open stream before dropping
SWEEP_TTL = 8.0            # no stream + silent this long = a ghost from a page reload
KEEPALIVE = 12.0           # seconds between SSE comments
OFFER_SLOTS = 8            # max items per side of a trade

# --- accounts ---------------------------------------------------------------
# The local fallback store. On a cloud host the database is the real home; this file is
# the offline fallback and the thing to restore from. $ACCOUNTS_FILE or --accounts moves it.
ACCOUNTS_FILE = Path(os.environ.get("ACCOUNTS_FILE") or (ROOT / "accounts.json"))
SESSION_TTL = 60 * 60 * 24 * 30           # a session token stays good for 30 days
PBKDF2_ROUNDS = 120_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
# The OAuth client the page uses. Google's tokeninfo endpoint only accepts a token
# minted for this audience, so a token for somebody else's app is refused.
GOOGLE_CLIENT_ID = (os.environ.get("GOOGLE_CLIENT_ID")
                    or "686810591475-21j0gv8i0uf8n9aiuof6jbbr6gi6uj9k.apps.googleusercontent.com")
VERIFY_GOOGLE = True       # --no-verify-google turns this off (offline development only)


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
        if PG and PG.ok:
            try:
                PG.save_trade(tid, a, b, offers)
            except Exception as exc:
                print(f"[db] could not log a trade ({exc})")

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


# --- trading rules (generated from index.html by tools/gen_trade_rarity.py)
# item key -> rarity, used to keep basic starter gear out of trades.
RARITY_RANK = {"common": 0, "rare": 1, "epic": 2, "legendary": 3, "mythic": 4, "secret": 5}
TRADE_RARITY = {"banner:harbour": "common", "banner:kraken": "rare", "banner:royal": "legendary", "banner:sunfire": "rare", "banner:verdant": "epic", "env:dawn": "common", "env:frozen": "epic", "env:midnight": "rare", "env:storm": "epic", "env:sunset": "rare", "env:volcanic": "legendary", "fleet:crimson": "rare", "fleet:ghost": "epic", "fleet:jade": "legendary", "fleet:royal": "common", "fx:ember": "epic", "fx:gilded": "rare", "fx:prism": "legendary", "fx:standard": "common", "turret:bear": "secret", "turret:crontomelon": "secret", "turret:kraken": "mythic", "turret:leviathan": "mythic", "turret:sunfire": "mythic", "turret:trident": "mythic", "wrap:aurora": "legendary", "wrap:bare": "common", "wrap:brass": "rare", "wrap:coral": "epic", "wrap:obsidian": "rare", "wrap:verdant": "epic"}
ITEM_POINTS = {"banner:harbour": 4, "banner:kraken": 18, "banner:royal": 260, "banner:sunfire": 18, "banner:verdant": 70, "env:dawn": 4, "env:frozen": 70, "env:midnight": 18, "env:storm": 70, "env:sunset": 18, "env:volcanic": 260, "fleet:crimson": 18, "fleet:ghost": 70, "fleet:jade": 260, "fleet:royal": 4, "fx:ember": 70, "fx:gilded": 18, "fx:prism": 260, "fx:standard": 4, "turret:bear": 4000, "turret:crontomelon": 4000, "turret:kraken": 900, "turret:leviathan": 900, "turret:sunfire": 900, "turret:trident": 900, "wrap:aurora": 260, "wrap:bare": 4, "wrap:brass": 18, "wrap:coral": 70, "wrap:obsidian": 18, "wrap:verdant": 70}

def owned_ids(save) -> dict:
    """The own-store out of a save blob: {"env:dawn": True, ...}."""
    cos = (save or {}).get("cos") or {}
    own = cos.get("own") if isinstance(cos, dict) else None
    return own if isinstance(own, dict) else {}

def profile_worth(save) -> int:
    return sum(ITEM_POINTS.get(k, 0) for k, v in owned_ids(save).items() if v)

def profile_owned(save) -> int:
    return sum(1 for v in owned_ids(save).values() if v)


def tradeable(item_id: str) -> bool:
    """Rare and above only - sprats and starter skins never change hands."""
    return RARITY_RANK.get(TRADE_RARITY.get(str(item_id), ""), -1) >= RARITY_RANK["rare"]

# --- end trading rules


# ----------------------------------------------------------------- accounts
def decode_jwt_claims(token: str) -> dict | None:
    """Read a JWT's claims WITHOUT checking the signature (dev fallback only)."""
    import base64
    try:
        part = str(token).split(".")[1]
        pad = part + "=" * ((4 - len(part) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(pad).decode("utf-8"))
    except Exception:  # noqa: BLE001 - a junk token is the caller's problem
        return None


def verify_google(credential: str, timeout: float = 8.0) -> dict | None:
    """Ask Google whether this ID token is genuine, and whose it is.

    tokeninfo checks the signature and the expiry for us and needs no crypto
    dependency (RS256 verification in pure stdlib is not practical). Returns the
    claims, or None when Google refuses the token or cannot be reached.
    """
    if not credential:
        return None
    url = "https://oauth2.googleapis.com/tokeninfo?id_token=" + quote(str(credential), safe="")
    try:
        with urlopen(url, timeout=timeout) as resp:
            claims = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:160]
        except Exception:  # noqa: BLE001
            detail = ""
        print(f"[auth] Google rejected that ID token ({exc.code}) {detail}")
        return None
    except (URLError, OSError, ValueError) as exc:
        print(f"[auth] could not reach Google to verify a token ({exc})")
        return None
    aud = str(claims.get("aud") or "")
    if GOOGLE_CLIENT_ID and aud and aud != GOOGLE_CLIENT_ID:
        print(f"[auth] token was minted for client {aud[:24]}…, not this game - refusing it")
        return None
    return claims


# ============================ permanent cloud storage ==========================
# DATABASE_URL points at Postgres (Supabase, Render, Neon, a local server...). When it
# is set the database is the source of truth for accounts, inventories, gems, gold,
# leaderboards and chat; when it is not, the JSON file carries on so the game still
# runs offline. The four tables the brief asks for are created on startup:
# users, inventories, leaderboards and chat_history (plus sessions for auth tokens).
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

DDL = [
    """CREATE TABLE IF NOT EXISTS users (
         id          TEXT PRIMARY KEY,
         provider    TEXT NOT NULL,
         username    TEXT,
         name        TEXT,
         email       TEXT,
         avatar      TEXT,
         sub         TEXT,
         created_at  BIGINT DEFAULT 0,
         last_seen   BIGINT DEFAULT 0,
         rev         INTEGER DEFAULT 0,
         at          BIGINT DEFAULT 0,
         pw_hash     TEXT,
         pw_salt     TEXT,
         stats       JSONB DEFAULT '{}'::jsonb,
         record      JSONB
       )""",
    """CREATE TABLE IF NOT EXISTS inventories (
         user_id    TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
         save       JSONB,
         gems       INTEGER DEFAULT 0,
         gold       INTEGER DEFAULT 0,
         worth      INTEGER DEFAULT 0,
         owned      INTEGER DEFAULT 0,
         updated_at BIGINT DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS leaderboards (
         id       BIGSERIAL PRIMARY KEY,
         user_id  TEXT NOT NULL,
         kind     TEXT NOT NULL,
         wave     INTEGER DEFAULT 0,
         score    BIGINT DEFAULT 0,
         worth    INTEGER DEFAULT 0,
         at       BIGINT DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS chat_history (
         id       BIGSERIAL PRIMARY KEY,
         user_id  TEXT,
         name     TEXT,
         worth    INTEGER DEFAULT 0,
         body     TEXT NOT NULL,
         at       BIGINT DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS sessions (
         token      TEXT PRIMARY KEY,
         user_id    TEXT NOT NULL,
         created_at BIGINT DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS collections (
         user_id  TEXT NOT NULL,
         item_id  TEXT NOT NULL,
         rarity   TEXT,
         worth    INTEGER DEFAULT 0,
         at       BIGINT DEFAULT 0,
         PRIMARY KEY (user_id, item_id)
       )""",
    """CREATE TABLE IF NOT EXISTS trades (
         id       BIGSERIAL PRIMARY KEY,
         a        TEXT,
         b        TEXT,
         state    TEXT,
         offers   JSONB,
         at       BIGINT DEFAULT 0
       )""",
    "CREATE INDEX IF NOT EXISTS leaderboards_user_idx ON leaderboards (user_id)",
    "CREATE INDEX IF NOT EXISTS collections_user_idx ON collections (user_id)",
    "CREATE INDEX IF NOT EXISTS chat_at_idx ON chat_history (at DESC)",
]


class PgStore:
    """Thin Postgres layer: load the whole world on boot, write through on changes.

    Accounts are keyed exactly as before, so every auth path keeps working untouched -
    only where the bytes live changes.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self.lock = threading.RLock()
        self.ok = False
        self.why = ""
        self._conn = None
        try:
            import psycopg2                     # noqa: F401
            from psycopg2.extras import Json    # noqa: F401
            self._psycopg2 = psycopg2
            self._Json = Json
        except Exception as exc:                # driver missing is not fatal
            self.why = f"psycopg2 not installed ({exc})"
            return
        try:
            self.connect()
            self.create_tables()
            self.ok = True
        except Exception as exc:
            self.why = f"could not reach the database ({exc})"
            print(f"[db] {self.why} - falling back to the local file")

    # --- plumbing --------------------------------------------------------
    def connect(self) -> None:
        if self._conn is not None and getattr(self._conn, "closed", 1) == 0:
            return
        self._conn = self._psycopg2.connect(self.url, connect_timeout=10)
        self._conn.autocommit = True

    def create_tables(self) -> None:
        with self.lock:
            self.connect()
            with self._conn.cursor() as cur:
                for stmt in DDL:
                    cur.execute(stmt)
            print(f"[db] tables ready ({len(DDL)} statements)")

    def rows(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self.lock:
            self.connect()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall() if cur.description else []

    def run(self, sql: str, params: tuple = ()) -> None:
        with self.lock:
            self.connect()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)

    def json(self, value):
        return self._Json(value if value is not None else None)

    # --- whole-world load -------------------------------------------------
    def load_all(self) -> tuple[dict, dict]:
        accounts: dict[str, dict] = {}
        for (uid, provider, username, name, email, avatar, sub, created, seen,
             rev, at, stats, save, gems, gold, record) in self.rows(
                """SELECT u.id, u.provider, u.username, u.name, u.email, u.avatar, u.sub,
                          u.created_at, u.last_seen, u.rev, u.at, u.stats,
                          i.save, i.gems, i.gold, u.record
                     FROM users u LEFT JOIN inventories i ON i.user_id = u.id"""):
            # The stored record is authoritative when present: it is the exact object
            # that was saved, so no field (hash, salt, createdAt, ...) can be lost.
            acct = dict(record) if isinstance(record, dict) else {}
            acct.update({
                "id": uid, "provider": provider, "username": username, "name": name,
                "email": email, "avatar": avatar, "sub": sub,
                "createdAt": acct.get("createdAt") or created or 0,
                "lastSeen": seen or acct.get("lastSeen") or 0,
                "rev": rev or 0, "at": at or 0,
                "stats": stats or acct.get("stats") or {}, "boards": [],
            })
            if save is not None:
                acct["save"] = save
            accounts[uid] = acct
        boards: dict[str, list[dict]] = {}
        for (uid, kind, wave, score, worth, at) in self.rows(
                "SELECT user_id, kind, wave, score, worth, at FROM leaderboards ORDER BY id"):
            boards.setdefault(uid, []).append(
                {"kind": kind, "wave": wave, "score": score, "worth": worth, "at": at})
        for uid, rows in boards.items():
            if uid in accounts:
                accounts[uid]["boards"] = rows
        tokens: dict[str, dict] = {}
        for (token, uid, created) in self.rows("SELECT token, user_id, created_at FROM sessions"):
            tokens[token] = {"id": uid, "at": created or 0}
        return accounts, tokens

    # --- write through ----------------------------------------------------
    def save_account(self, acct: dict) -> None:
        save = acct.get("save") or None
        gems = gold = 0
        if isinstance(save, dict):
            wallet = save.get("wallet") or {}
            gems = int(wallet.get("gems") or 0)
            run = save.get("run") or {}
            gold = int(run.get("gold") or 0)
        # `record` carries the WHOLE account object: the explicit columns are for
        # querying, but the record guarantees a restart cannot silently drop a field
        # (a missing password hash meant a local account could not sign in again).
        self.run(
            """INSERT INTO users (id, provider, username, name, email, avatar, sub,
                                 created_at, last_seen, rev, at, pw_hash, pw_salt, stats, record)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET
                 provider = EXCLUDED.provider, username = EXCLUDED.username, name = EXCLUDED.name,
                 email = EXCLUDED.email, avatar = EXCLUDED.avatar, sub = EXCLUDED.sub,
                 last_seen = EXCLUDED.last_seen, rev = EXCLUDED.rev, at = EXCLUDED.at,
                 pw_hash = EXCLUDED.pw_hash, pw_salt = EXCLUDED.pw_salt,
                 stats = EXCLUDED.stats, record = EXCLUDED.record""",
            (acct.get("id"), acct.get("provider"), acct.get("username"), acct.get("name"),
             acct.get("email"), acct.get("avatar"), acct.get("sub"),
             int(acct.get("createdAt") or acct.get("created") or 0),
             int(acct.get("lastSeen") or 0),
             int(acct.get("rev") or 0), int(acct.get("at") or 0),
             acct.get("hash"), acct.get("salt"),
             self.json(acct.get("stats") or {}), self.json(acct)))
        self.run(
            """INSERT INTO inventories (user_id, save, gems, gold, worth, owned, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id) DO UPDATE SET
                 save = EXCLUDED.save, gems = EXCLUDED.gems, gold = EXCLUDED.gold,
                 worth = EXCLUDED.worth, owned = EXCLUDED.owned, updated_at = EXCLUDED.updated_at""",
            (acct.get("id"), self.json(save), gems, gold,
             profile_worth(save) if save else 0, profile_owned(save) if save else 0,
             int(time.time() * 1000)))
        # item collections, as a queryable index (the whole blob also lives above)
        self.run("DELETE FROM collections WHERE user_id = %s", (acct.get("id"),))
        try:
            owned = owned_ids(save) if isinstance(save, dict) else {}
        except Exception:
            owned = {}
        for item_id in sorted(owned):
            self.run(
                """INSERT INTO collections (user_id, item_id, rarity, worth, at)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT (user_id, item_id) DO UPDATE
                   SET rarity = EXCLUDED.rarity, worth = EXCLUDED.worth""",
                (acct.get("id"), item_id, str(owned[item_id]), ITEM_POINTS.get(str(owned[item_id]), 0),
                 int(time.time() * 1000)))
        self.run("DELETE FROM leaderboards WHERE user_id = %s", (acct.get("id"),))
        for row in (acct.get("boards") or [])[-40:]:
            self.run(
                """INSERT INTO leaderboards (user_id, kind, wave, score, worth, at)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (acct.get("id"), str(row.get("kind") or "run"), int(row.get("wave") or 0),
                 int(row.get("score") or 0), int(row.get("worth") or 0), int(row.get("at") or 0)))

    def save_trade(self, tid: str, a: str, b: str, offers: dict, state: str = "settled") -> None:
        self.run(
            """INSERT INTO trades (a, b, state, offers, at) VALUES (%s,%s,%s,%s,%s)""",
            (a, b, state, self.json(offers or {}), int(time.time() * 1000)))

    def save_token(self, token: str, uid: str, at: float = 0) -> None:
        self.run(
            """INSERT INTO sessions (token, user_id, created_at) VALUES (%s,%s,%s)
               ON CONFLICT (token) DO UPDATE SET user_id = EXCLUDED.user_id""",
            (token, uid, int(at or time.time() * 1000)))

    def drop_token(self, token: str) -> None:
        self.run("DELETE FROM sessions WHERE token = %s", (token,))

    # --- chat -------------------------------------------------------------
    def add_chat(self, uid: str, name: str, body: str, worth: int = 0) -> dict:
        at = int(time.time() * 1000)
        self.run(
            """INSERT INTO chat_history (user_id, name, worth, body, at)
               VALUES (%s,%s,%s,%s,%s)""", (uid, name, int(worth or 0), body, at))
        return {"id": uid, "name": name, "worth": int(worth or 0), "body": body, "at": at}

    def recent_chat(self, limit: int = 60) -> list[dict]:
        out = []
        for (uid, name, worth, body, at) in self.rows(
                "SELECT user_id, name, worth, body, at FROM chat_history ORDER BY id DESC LIMIT %s",
                (limit,)):
            out.append({"id": uid, "name": name, "worth": worth, "body": body, "at": at})
        return list(reversed(out))

    # --- the global wipe ------------------------------------------------
    def table_counts(self) -> dict:
        out = {}
        for t in WIPE_ORDER:
            out[t] = self.count_rows(t)
        return out

    def wipe_all(self, backup_path: Path | None = None) -> dict:
        """Truncate every table and restart its identity. Backs up first.

        Children are listed before parents so the truncate is safe even without
        CASCADE; RESTART IDENTITY puts every BIGSERIAL back to 1.
        """
        report = {"backend": "postgres", "rows_before": self.table_counts(), "backup": None}
        if backup_path is not None:
            dump = {}
            for (table, sql) in (("users", "SELECT id, provider, username, name, email, avatar, sub, created_at, last_seen, rev, at, stats, record FROM users"),
                                 ("inventories", "SELECT user_id, save, gems, gold, worth, owned, updated_at FROM inventories"),
                                 ("collections", "SELECT user_id, item_id, rarity, worth, at FROM collections"),
                                 ("leaderboards", "SELECT user_id, kind, wave, score, worth, at FROM leaderboards"),
                                 ("chat_history", "SELECT user_id, name, worth, body, at FROM chat_history"),
                                 ("trades", "SELECT a, b, state, offers, at FROM trades"),
                                 ("sessions", "SELECT token, user_id, created_at FROM sessions")):
                try:
                    dump[table] = [list(r) for r in self.rows(sql)]
                except Exception as exc:
                    dump[table] = [f"<could not dump: {exc}>"]
            backup_path.write_text(json.dumps(dump, indent=1, default=str), encoding="utf-8")
            report["backup"] = str(backup_path)
        with self.lock:
            self.connect()
            with self._conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE " + ", ".join(WIPE_ORDER) + " RESTART IDENTITY CASCADE")
        report["rows_after"] = self.table_counts()
        return report

    def prune_orphans(self) -> dict:
        """Remove rows whose owning account no longer exists. Never touches live data."""
        removed = {}
        for (table, col) in (("inventories", "user_id"), ("collections", "user_id"),
                             ("leaderboards", "user_id"), ("sessions", "user_id")):
            try:
                before = self.count_rows(table)
                self.run(f"DELETE FROM {table} WHERE {col} NOT IN (SELECT id FROM users)")
                after = self.count_rows(table)
                if before - after:
                    removed[table] = before - after
            except Exception as exc:
                print(f"[db] could not prune {table} ({exc})")
        return removed

    def count_rows(self, table: str) -> int:
        try:
            r = self.rows(f"SELECT COUNT(*) FROM {table}")
            return int(r[0][0]) if r else 0
        except Exception:
            return -1


# A chat log that survives a database-less host: memory, capped, so the /api/health
# view and the client always have something to show.
class MemoryChat:
    def __init__(self, limit: int = 200) -> None:
        self.limit = limit
        self.messages: list[dict] = []

    def add_chat(self, uid: str, name: str, body: str, worth: int = 0) -> dict:
        msg = {"id": uid, "name": name, "worth": int(worth or 0), "body": body,
               "at": int(time.time() * 1000)}
        self.messages.append(msg)
        self.messages = self.messages[-self.limit:]
        return msg

    def recent_chat(self, limit: int = 60) -> list[dict]:
        return self.messages[-limit:]


# Every table the game owns, children first. The wipe covers all of them.
WIPE_ORDER = ["trades", "collections", "leaderboards", "chat_history", "sessions",
              "inventories", "users"]
WIPE_PHRASE = "WIPE ALL DATA"        # the admin route insists on this exact string
# The admin wipe is DISABLED until a token is configured: an open endpoint that erases
# every account is a worse failure than forgetting to set a variable.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()
WIPE_BACKUP_DIR = ROOT / "backups"

PG = PgStore(DATABASE_URL) if DATABASE_URL else None
_MEMCHAT = MemoryChat()


def chat_store():
    """Where chat lives: the database while it is usable, memory otherwise.

    `PG or MemoryChat()` was wrong - a constructed PgStore is truthy even when the
    connection failed, so a database-less host would have raised on every message.
    """
    return PG if (PG and PG.ok) else _MEMCHAT


def chat_add(uid: str, name: str, body: str, worth: int = 0) -> dict:
    """Append a message, falling back to memory if the database is misbehaving."""
    try:
        return chat_store().add_chat(uid, name, body, worth)
    except Exception as exc:
        print(f"[db] chat write failed ({exc}) - keeping it in memory")
        return _MEMCHAT.add_chat(uid, name, body, worth)


def chat_recent(limit: int = 60) -> list[dict]:
    try:
        return chat_store().recent_chat(limit)
    except Exception as exc:
        print(f"[db] chat read failed ({exc}) - serving memory")
        return _MEMCHAT.recent_chat(limit)


CHAT = chat_store()


def wipe_everything(reason: str = "manual", admin: bool = True) -> dict:
    """Erase every account, inventory, collection, leaderboard, chat log, trade,
    gem and gold record. Always writes a backup first. Returns a report.

    Deliberately NOT called on boot unless WIPE_ON_START is set - a schema init that
    emptied the tables would erase every player on each redeploy.
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        WIPE_BACKUP_DIR.mkdir(exist_ok=True)
    except OSError:
        pass
    report = {"at": int(time.time() * 1000), "reason": reason, "admin": bool(admin)}
    if PG and PG.ok:
        try:
            report["postgres"] = PG.wipe_all(WIPE_BACKUP_DIR / f"postgres-before-wipe-{stamp}.json")
        except Exception as exc:
            report["postgres"] = {"error": str(exc)}
    else:
        report["postgres"] = {"backend": "json-fallback"}
    report["json"] = ACCOUNTS.wipe(WIPE_BACKUP_DIR / f"accounts-before-wipe-{stamp}.json")
    # live session state: the hub holds names, worths, trades and settled history
    try:
        with HUB.lock:
            HUB.clients.clear()
            HUB.trades.clear()
            HUB.done.clear()
    except Exception:
        pass
    try:
        if isinstance(_MEMCHAT, MemoryChat):
            _MEMCHAT.messages.clear()
    except Exception:
        pass
    print(f"[wipe] GLOBAL WIPE complete ({reason}) - every account, inventory, collection, "
          f"leaderboard, chat log, trade, gem and gold record is gone. Backup: "
          f"{report.get('postgres', {}).get('backup') or report['json'].get('backup')}", flush=True)
    return report


class Accounts:
    """Player accounts. Persisted to Postgres when DATABASE_URL is set, else a JSON file.

    Records are keyed by a STABLE identity: the Google `sub` (falling back to the
    verified email for records made before sub-keying) or `local:<username>` for
    username/password players. Deliberately *not* keyed by session token, origin or
    IP - that is what used to spawn a fresh empty account whenever a known Google
    account arrived from a new browser, device or tunnel URL. Signing in again with
    the same Google account always resolves to the same record, which is how a
    player's profile, inventory and stats follow them across devices.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lock = threading.RLock()
        self.accounts: dict[str, dict] = {}
        self.tokens: dict[str, dict] = {}
        self._sig: dict[str, int] = {}       # content signature of what the DB last took
        self._tsig = None                    # signature of the token set
        self.load()

    # --- storage ---------------------------------------------------------
    def load(self) -> None:
        # The database wins whenever it is reachable: it is the permanent store.
        if PG and PG.ok:
            try:
                self.accounts, self.tokens = PG.load_all()
                print(f"[db] loaded {len(self.accounts)} account(s), {len(self.tokens)} session(s)")
                # First run against an empty database: seed it from the local file so
                # nobody loses the profile they already had.
                if not self.accounts and self.path.is_file():
                    self.load_json()
                    if self.accounts:
                        print(f"[db] seeding {len(self.accounts)} account(s) from {self.path.name}")
                        self.flush()
                self.dirty = False
                return
            except Exception as exc:
                print(f"[db] load failed ({exc}) - using the local file")
        self.load_json()

    def load_json(self) -> None:
        try:
            if self.path.is_file():
                blob = json.loads(self.path.read_text(encoding="utf-8") or "{}")
                self.accounts = blob.get("accounts") or {}
                self.tokens = blob.get("tokens") or {}
        except (OSError, ValueError) as exc:
            print(f"[auth] could not read {self.path.name} ({exc}) - starting empty")

    def wipe(self, backup_path: Path | None = None) -> dict:
        """Erase every account and session, after writing the whole store to a file."""
        out = {"backend": "json", "accounts_before": len(self.accounts),
               "sessions_before": len(self.tokens), "backup": None}
        if backup_path is not None:
            try:
                backup_path.write_text(json.dumps(
                    {"accounts": self.accounts, "tokens": self.tokens, "wiped": time.time()},
                    default=str), encoding="utf-8")
                out["backup"] = str(backup_path)
            except OSError as exc:
                out["backup_error"] = str(exc)
        with self.lock:
            self.accounts = {}
            self.tokens = {}
            self._sig = {}
            self._tsig = None
        self.flush()
        out["accounts_after"] = len(self.accounts)
        out["sessions_after"] = len(self.tokens)
        return out

    def flush(self) -> None:
        """Persist every profile. Postgres when configured, else an atomic JSON write."""
        with self.lock:
            if PG and PG.ok:
                # Write through only what actually changed, keyed on a content
                # signature - so a 15-second profile push does not rewrite the world,
                # and no mutation can slip past by forgetting to mark itself dirty.
                for uid, acct in list(self.accounts.items()):
                    sig = hash(json.dumps(acct, sort_keys=True, default=str))
                    if self._sig.get(uid) == sig:
                        continue
                    try:
                        PG.save_account(acct)
                        self._sig[uid] = sig
                    except Exception as exc:
                        print(f"[db] could not save {uid} ({exc})")
                tsig = hash(tuple(sorted(self.tokens)))
                if tsig != self._tsig:
                    # The token set changed - possibly by revoking one, so replace the
                    # table wholesale rather than only adding.
                    try:
                        PG.run("DELETE FROM sessions")
                        for token, info in self.tokens.items():
                            PG.save_token(token, info.get("id"), info.get("at"))
                        self._tsig = tsig
                    except Exception as exc:
                        print(f"[db] could not sync sessions ({exc})")
            # Always keep the local file in step: it is the offline fallback and the
            # thing to restore from if the database is ever wiped.
            blob = {"accounts": self.accounts, "tokens": self.tokens, "saved": time.time()}
            tmp = self.path.with_name(self.path.name + ".tmp")
            try:
                # default=str so one stray non-JSON value can never take persistence down
                # (the database write above already succeeded by this point).
                tmp.write_text(json.dumps(blob, separators=(",", ":"), default=str),
                               encoding="utf-8")
                os.replace(tmp, self.path)
            except (OSError, TypeError, ValueError) as exc:
                if not (PG and PG.ok):
                    print(f"[auth] could not save {self.path.name} ({exc})")

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _new(provider: str, username, name, email, avatar, sub=None) -> dict:
        now = int(time.time() * 1000)
        return {
            "id": f"google:{sub}" if provider == "google" else f"local:{str(username).lower()}",
            "provider": provider, "username": username, "name": name or username or "Captain",
            "email": email, "avatar": avatar, "sub": sub,
            "createdAt": now, "lastSeen": now,
            "stats": {}, "save": None, "boards": [], "salt": None, "hash": None,
            "rev": 0,        # bumped on every accepted profile push (see store_profile)
        }

    def find_username(self, username: str) -> dict | None:
        want = str(username or "").strip().lower()
        if not want:
            return None
        for a in self.accounts.values():
            if str(a.get("username") or "").lower() == want:
                return a
        return None

    def find_email(self, email: str) -> dict | None:
        want = str(email or "").strip().lower()
        if not want:
            return None
        for a in self.accounts.values():
            if str(a.get("email") or "").lower() == want:
                return a
        return None

    def leaderboard(self) -> list[dict]:
        """Every registered player, online or not, ranked by their best wave.

        The board is built from the account store (server-side, persisted), not from
        whoever happens to be connected: a captain who logged off yesterday still holds
        their rank. `online` only marks who the hub can see right now.
        """
        live_prof = {c.get("prof") for c in HUB.clients.values() if c.get("prof")}
        live_name = {c.get("name") for c in HUB.clients.values()}
        rows = []
        for acct in self.accounts.values():
            st = acct.get("stats") or {}
            save = acct.get("save") or {}
            run = save.get("run") or {}
            wallet = save.get("wallet") or {}
            best = int(st.get("bestWave") or run.get("wave") or 0)
            waves = int(st.get("waves") or 0)
            kills = int(st.get("kills") or 0)
            worth = profile_worth(save)
            rows.append({
                "id": acct["id"],
                "name": acct.get("username") or acct.get("name") or "Captain",
                "provider": acct.get("provider") or "local",
                "bestWave": best, "waves": waves, "kills": kills,
                "gems": int(st.get("gems") or 0), "gemsHeld": int(wallet.get("gems") or 0),
                "gold": int(st.get("gold") or 0), "breaches": int(st.get("breaches") or 0),
                "runs": int(st.get("runs") or 0),
                "worth": worth, "owned": profile_owned(save),
                "lastSeen": int(acct.get("lastSeen") or 0),
                # a rough overall score: wave progress dominates, wealth and sinking break ties
                "score": best * 100 + waves * 25 + kills * 2 + worth // 5,
                "online": acct["id"] in live_prof or (acct.get("username") in live_name),
            })
        rows.sort(key=lambda r: (-r["bestWave"], -r["worth"], -r["kills"]))
        return rows

    @staticmethod
    def public(acct: dict) -> dict:
        """An account as the client may see it - never the password material."""
        out = dict(acct)
        out.pop("salt", None)
        out.pop("hash", None)
        return out

    @staticmethod
    def _hash(password: str, salt: str) -> str:
        dk = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"),
                                 str(salt).encode("utf-8"), PBKDF2_ROUNDS)
        return f"pbkdf2${PBKDF2_ROUNDS}${dk.hex()}"

    # --- google ----------------------------------------------------------
    def login_google(self, sub, email, name, picture) -> tuple[dict, bool]:
        with self.lock:
            acct = self.accounts.get("google:" + str(sub))
            if not acct and email:
                # adopt a record created before this build keyed on the email instead
                for a in self.accounts.values():
                    if a.get("provider") == "google" and \
                            str(a.get("email") or "").lower() == str(email).lower():
                        acct = a
                        break
            created = False
            if not acct:
                acct = self._new("google", None, name, email, picture, sub=str(sub))
                created = True
            acct["sub"] = str(sub)
            acct["email"] = email or acct.get("email")
            acct["avatar"] = picture or acct.get("avatar")
            acct["name"] = acct.get("username") or name or acct.get("name") or "Captain"
            acct["lastSeen"] = int(time.time() * 1000)
            self.accounts[acct["id"]] = acct
        self.flush()
        return acct, created

    # --- username / password ---------------------------------------------
    def register(self, username, password, email=None) -> dict:
        username = str(username or "").strip()
        if not USERNAME_RE.match(username):
            raise ValueError("Username must be 3-16 characters: letters, numbers and underscores.")
        if len(str(password or "")) < 6:
            raise ValueError("Password must be at least 6 characters.")
        email = str(email or "").strip().lower() or None
        if email and not EMAIL_RE.match(email):
            raise ValueError("That does not look like an email address.")
        with self.lock:
            if self.find_username(username):
                raise ValueError("That username is already taken - pick another.")
            if email and self.find_email(email):
                raise ValueError("That email is already registered - sign in instead.")
            salt = secrets.token_hex(16)
            acct = self._new("local", username, username, email, None)
            acct["salt"] = salt
            acct["hash"] = self._hash(password, salt)
            self.accounts[acct["id"]] = acct
        self.flush()
        return acct

    def login_local(self, identifier, password) -> dict:
        """Sign in with either the registered username OR the registered email."""
        who = str(identifier or "").strip()
        with self.lock:
            acct = (self.accounts.get("local:" + who.lower())
                    or self.find_username(who)
                    or self.find_email(who))
        if not acct or not acct.get("hash"):
            raise ValueError("No account with that username or email.")
        if not hmac.compare_digest(str(acct["hash"]), self._hash(password, acct.get("salt") or "")):
            raise ValueError("Wrong password.")
        with self.lock:
            acct["lastSeen"] = int(time.time() * 1000)
        self.flush()
        return acct

    def set_avatar(self, acct_id: str, avatar) -> dict:
        """Choose the player's profile picture (a glyph, or Google's image URL)."""
        avatar = str(avatar or "").strip()[:200] or None
        with self.lock:
            acct = self.accounts.get(acct_id)
            if not acct:
                raise ValueError("No such account.")
            acct["avatar"] = avatar
            acct["lastSeen"] = int(time.time() * 1000)
        self.flush()
        return acct

    def set_username(self, acct_id: str, username) -> dict:
        username = str(username or "").strip()
        if not USERNAME_RE.match(username):
            raise ValueError("3-16 characters: letters, numbers and underscores only.")
        with self.lock:
            acct = self.accounts.get(str(acct_id))
            if not acct:
                raise ValueError("Unknown account.")
            other = self.find_username(username)
            if other and other["id"] != acct["id"]:
                raise ValueError("That username is already taken - pick another.")
            acct["username"] = username
            acct["name"] = username
            acct["namedAt"] = int(time.time() * 1000)
        self.flush()
        return acct

    # --- sessions ---------------------------------------------------------
    def issue(self, acct: dict) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.tokens[token] = {"id": acct["id"], "at": time.time()}
            self._prune()
        self.flush()
        return token

    def by_token(self, token) -> dict | None:
        """Resolve a session token to its account - the cross-device load path."""
        key = str(token or "")
        with self.lock:
            rec = self.tokens.get(key)
            if not rec:
                return None
            if time.time() - rec["at"] > SESSION_TTL:
                self.tokens.pop(key, None)
                return None
            rec["at"] = time.time()               # sliding expiry
            return self.accounts.get(rec["id"])

    def revoke(self, token) -> None:
        with self.lock:
            self.tokens.pop(str(token or ""), None)
        self.flush()

    def _prune(self) -> None:
        now = time.time()
        for t in [t for t, r in self.tokens.items() if now - r["at"] > SESSION_TTL]:
            self.tokens.pop(t, None)

    @staticmethod
    def _stamp(blob) -> int:
        """When a client wrote this blob. Every save carries `at` (ms)."""
        if not isinstance(blob, dict):
            return 0
        try:
            return int(blob.get("at") or 0)
        except (TypeError, ValueError):
            return 0

    def store_profile(self, acct: dict, save, boards, stats, base_rev=None) -> bool:
        """Keep the newest copy of a profile and report whether this one won.

        Two devices signed into one account both push, and a wall-clock stamp is NOT
        enough to tell them apart: a browser sitting on an older state re-saves it with
        a fresh timestamp and would win. So the server hands out a `rev` and the client
        must say which rev it based its work on. A push from an older rev is refused -
        the caller then returns the server's copy, which the client adopts, and its next
        push (now based on the current rev) is accepted again.

        Returns False when the incoming blob was refused.
        """
        fresh = True
        with self.lock:
            cur = int(acct.get("rev") or 0)
            if save is not None:
                if base_rev is None:
                    # Legacy client (no rev): fall back to the timestamp comparison.
                    mine = self._stamp(save)
                    theirs = self._stamp(acct.get("save"))
                    if theirs and mine < theirs:
                        fresh = False
                elif int(base_rev) < cur:
                    fresh = False
                if fresh:
                    acct["save"] = save
                    acct["rev"] = cur + 1
            if fresh:
                if boards is not None:
                    acct["boards"] = boards
                if stats is not None:
                    acct["stats"] = stats
            acct["lastSeen"] = int(time.time() * 1000)
        self.flush()
        return fresh


ACCOUNTS = Accounts(ACCOUNTS_FILE)


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

    def _body(self, limit: int = 524288) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > limit:
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
    # Anything here must never be served over HTTP. The static handler sits in the same
    # directory as the account store, the backups and the server log, so without this a
    # public link hands out every password hash and session token at /accounts.json.
    BLOCKED_PREFIXES = ("/backups", "/tools", "/__pycache__", "/.git", "/venv", "/node_modules")
    BLOCKED_FILES = {"/accounts.json", "/server.log", "/start.bat", "/requirements.txt",
                     "/hub_test.txt", "/preview.png"}
    BLOCKED_EXTS = (".json", ".log", ".py", ".pyc", ".bat", ".sh", ".ps1", ".tmp", ".bak",
                    ".db", ".sqlite", ".sqlite3", ".sql", ".env", ".yml", ".yaml", ".toml",
                    ".ini", ".cfg", ".md")

    def _blocked(self, path: str) -> bool:
        p = (path or "/").lower()
        if p.startswith("/api/"):
            return False                       # the API is routed above this
        if any(p.startswith(pre) for pre in self.BLOCKED_PREFIXES):
            return True
        if p in {f.lower() for f in self.BLOCKED_FILES}:
            return True
        if any(seg.startswith(".") for seg in p.split("/") if seg):
            return True                        # dotfiles: .env, .git internals, editors
        return p.endswith(self.BLOCKED_EXTS)

    def list_directory(self, path):            # no directory listings, ever
        self.send_error(404, "No such file")
        return None

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib signature
        if self._blocked(urlparse(self.path).path):
            return self.send_error(404, "No such file")
        return super().do_HEAD()

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        path = urlparse(self.path).path
        if self._blocked(path):
            return self.send_error(404, "No such file")
        if path == "/api/events":
            return self._sse()
        if path == "/api/players":
            return self._json({"players": HUB.public_players()})
        if path == "/api/leaderboard":
            rows = ACCOUNTS.leaderboard()
            return self._json({"ok": True, "at": int(time.time() * 1000),
                               "accounts": len(rows), "rows": rows})
        if path == "/api/chat":
            # The permanent log (Postgres when configured, memory otherwise).
            return self._json({"ok": True, "at": int(time.time() * 1000),
                               "messages": chat_recent(80)})
        if path == "/api/health":
            return self._json({"ok": True, "players": len(HUB.clients), "trades": len(HUB.trades),
                               "accounts": len(ACCOUNTS.accounts)})
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        path = urlparse(self.path).path
        body = self._body()
        if path.startswith("/api/account/"):
            return self._account(path, body)
        if path == "/api/chat/send":
            acct = ACCOUNTS.by_token(body.get("token"))
            if not acct:
                return self._json({"ok": False, "error": "sign in to chat"}, 401)
            text = " ".join(str(body.get("body") or "").split())
            if not text:
                return self._json({"ok": False, "error": "nothing to say"}, 400)
            if len(text) > 240:
                text = text[:240]
            if acct.get("mutedUntil") and acct["mutedUntil"] > time.time() * 1000:
                return self._json({"ok": False, "error": "you are muted for a moment"}, 429)
            # Worth is computed server-side from the account's own save, so a client
            # cannot claim a net worth it does not have.
            worth = profile_worth(acct.get("save"))
            who = acct.get("name") or acct.get("username") or "Captain"
            msg = chat_add(acct["id"], who, text, worth)
            msg["avatar"] = acct.get("avatar")
            msg["provider"] = acct.get("provider")
            msg["prof"] = acct["id"]
            HUB.broadcast({"type": "chat", "msg": msg})
            return self._json({"ok": True, "msg": msg})
        if path == "/api/admin/wipe-all-data":
            # Erases every account, inventory, collection, leaderboard, chat log, trade,
            # gem and gold record. Needs the admin token AND the exact phrase, and it
            # writes a backup first. Add ?dry=1 (or "dry": true) to see the counts only.
            if not ADMIN_TOKEN:
                return self._json({"ok": False, "error":
                                   "the admin wipe is disabled - set ADMIN_TOKEN on the server to enable it"}, 403)
            if str(body.get("token") or "") != ADMIN_TOKEN:
                print("  !! a wipe request arrived with the wrong admin token", flush=True)
                return self._json({"ok": False, "error": "bad admin token"}, 401)
            if str(body.get("confirm") or "") != WIPE_PHRASE:
                return self._json({"ok": False, "error":
                                   'refusing: send {"confirm": "' + WIPE_PHRASE + '"} to confirm'}, 400)
            if body.get("dry") or "dry=1" in (self.path or ""):
                counts = PG.table_counts() if (PG and PG.ok) else {}
                return self._json({"ok": True, "dry": True, "postgres": counts,
                                   "accounts": len(ACCOUNTS.accounts),
                                   "sessions": len(ACCOUNTS.tokens),
                                   "online": len(HUB.clients), "trades_open": len(HUB.trades),
                                   "note": "nothing was deleted"})
            report = wipe_everything(reason="admin route", admin=True)
            return self._json({"ok": True, "dry": False, "report": report})
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

    # --- accounts ---------------------------------------------------------
    def _account(self, path: str, body: dict) -> None:
        """The account API. Every reply carries the account, so a client can adopt it."""
        action = path.rsplit("/", 1)[-1]
        try:
            if action == "google":
                return self._acct_google(body)
            if action == "register":
                return self._acct_ok(
                    ACCOUNTS.register(body.get("username"), body.get("password"), body.get("email")),
                    created=True)
            if action == "login":
                # one field, either identifier: the username or the registered email
                who = body.get("identifier") or body.get("username")
                return self._acct_ok(ACCOUNTS.login_local(who, body.get("password")))
            if action in ("session", "username", "save", "avatar"):
                acct = ACCOUNTS.by_token(body.get("token"))
                if not acct:
                    return self._json({"ok": False, "error": "session expired"}, 401)
                if action == "session":
                    return self._acct_ok(acct, token=body.get("token"))
                if action == "username":
                    return self._acct_ok(ACCOUNTS.set_username(acct["id"], body.get("username")),
                                         token=body.get("token"))
                if action == "avatar":
                    return self._acct_ok(ACCOUNTS.set_avatar(acct["id"], body.get("avatar")),
                                         token=body.get("token"))
                fresh = ACCOUNTS.store_profile(acct, body.get("save"), body.get("boards"),
                                               body.get("stats"), body.get("baseRev"))
                if not fresh:
                    print(f"  ~ profile push from {acct['id']} was older than the stored copy - kept theirs",
                          flush=True)
                return self._json({"ok": True, "at": int(time.time() * 1000), "stale": not fresh,
                                   "account": ACCOUNTS.public(acct)})
            if action == "logout":
                ACCOUNTS.revoke(body.get("token"))
                return self._json({"ok": True})
        except ValueError as exc:
            return self._json({"ok": False, "error": str(exc)}, 400)
        return self._json({"ok": False, "error": "unknown account action"}, 404)

    def _acct_google(self, body: dict) -> None:
        credential = str(body.get("credential") or "")
        claims = verify_google(credential) if VERIFY_GOOGLE else decode_jwt_claims(credential)
        if not claims or not claims.get("sub"):
            return self._json({"ok": False,
                               "error": "Google could not verify that sign-in - try again."}, 401)
        acct, created = ACCOUNTS.login_google(claims.get("sub"), claims.get("email"),
                                              claims.get("name"), claims.get("picture"))
        who = acct.get("username") or "no username yet"
        print(f"  {'+' if created else '='} account {acct['id']} ({who})"
              f" - {len(ACCOUNTS.accounts)} account(s)", flush=True)
        return self._acct_ok(acct, created=created)

    def _acct_ok(self, acct: dict, created: bool = False, token: str | None = None) -> None:
        token = token or ACCOUNTS.issue(acct)
        return self._json({
            "ok": True, "token": token, "created": bool(created),
            "needsUsername": not bool(acct.get("username")),
            "account": ACCOUNTS.public(acct),
        })

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
            # The hub refuses basic gear outright: Rare and above only.
            blocked = [i for i in items if not tradeable(i)]
            if blocked:
                msg = ("only Rare and above can be traded - " +
                       ", ".join(blocked[:3]) + " cannot change hands")
                print(f"  x trade-offer refused from {me['name']}: {blocked[:3]}", flush=True)
                return self._json({"ok": False, "error": msg}, 400)
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
    p.add_argument("--accounts", default=str(ACCOUNTS_FILE),
                   help="where to keep player accounts (default: accounts.json)")
    p.add_argument("--no-verify-google", action="store_true",
                   help="skip Google's token check (offline development ONLY - unsafe)")
    p.add_argument("--wipe-all-data", action="store_true",
                   help="erase every account, inventory, collection, leaderboard, chat log, "
                        "trade, gem and gold record, then exit. Requires --yes.")
    p.add_argument("--wipe-on-start", action="store_true",
                   help="wipe everything at boot before serving (same as WIPE_ON_START=1)")
    p.add_argument("--yes", action="store_true", help="confirm a destructive command")
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
    global VERIFY_GOOGLE
    args = parse_args()
    root = str(Path(args.root).resolve())
    handler = functools.partial(QuietHandler, directory=root)

    if args.wipe_all_data:
        if not args.yes:
            print("refusing to wipe without --yes")
            print("  this erases EVERY account, inventory, collection, leaderboard, chat log,")
            print("  trade, gem and gold record. Run:  python server.py --wipe-all-data --yes")
            return 2
        print("=" * 66)
        print("  GLOBAL WIPE")
        print("=" * 66)
        report = wipe_everything(reason="--wipe-all-data", admin=True)
        print(json.dumps(report, indent=1, default=str))
        print("\n  every player is back to a blank slate. Backups are in ./backups/")
        return 0

    if args.no_verify_google:
        VERIFY_GOOGLE = False
        print("[auth] WARNING: Google ID tokens are NOT being verified (--no-verify-google).")
        print("[auth] anyone can claim any account id - development use only.\n")

    # a different accounts file (tests, a second instance) is honoured before serving
    wanted = Path(args.accounts)
    if wanted.resolve() != ACCOUNTS.path.resolve():
        ACCOUNTS.path = wanted
        ACCOUNTS.accounts, ACCOUNTS.tokens = {}, {}
        ACCOUNTS.load()

    # A schema init must NEVER silently empty the tables: that would erase every player
    # on each redeploy. The default is to keep data and remove only orphaned rows; a full
    # reset happens when it is explicitly asked for (WIPE_ON_START=1 or --wipe-on-start).
    wipe_on_start = args.wipe_on_start or bool(os.environ.get("WIPE_ON_START"))
    if wipe_on_start:
        print("[wipe] WIPE_ON_START is set - erasing all player data before serving.")
        wipe_everything(reason="startup flag", admin=True)
    elif PG and PG.ok:
        pruned = PG.prune_orphans()
        print(f"[db] schema ready; orphan rows pruned: {pruned or 'none'} (set WIPE_ON_START=1 for a full reset)")

    print("=" * 66)
    print("  SEA SIEGE TOWER DEFENSE")
    print("=" * 66)
    print(f"  serving : {root}")
    print(f"  accounts: {ACCOUNTS.path} ({len(ACCOUNTS.accounts)} saved)")

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
        print("  accounts: /api/account/* - Google + username/password, synced across devices")
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
