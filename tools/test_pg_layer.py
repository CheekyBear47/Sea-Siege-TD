"""Verify the Postgres/Supabase storage layer without a Postgres server.

There is no Postgres on this machine, so the driver is faked: `psycopg2` is installed
into sys.modules as a small in-memory emulator that actually *runs* the handful of
statements PgStore issues (upserts, the leaderboard swap, the session swap, chat
inserts) and answers the SELECTs in the exact column order the code asks for. That
makes the real risk testable - does a profile survive a save -> restart -> load round
trip, in the right columns, with gems/gold/inventory intact - and it catches column
order mistakes that a "recorded SQL" test would sleep through.

What this does NOT prove: that the DDL is accepted by a real Postgres, or that a real
Supabase URL authenticates. Point DATABASE_URL at a real database to prove those.

Run:  python tools/test_pg_layer.py
"""
import importlib
import os
import sys
import types
import pathlib
import json
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

PASSED = []
FAILED = []


def check(label, ok, detail=""):
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"   [{detail}]" if detail and not ok else ""))


# --------------------------------------------------------------- fake psycopg2
class Json:
    """Stand-in for psycopg2.extras.Json - carries a value into a JSONB column."""

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Json({self.value!r})"


class FakeDB:
    """Just enough Postgres for the statements this app sends."""

    def __init__(self):
        self.users = {}          # id -> dict of columns
        self.inventories = {}    # user_id -> dict
        self.leaderboards = []   # list of dicts
        self.sessions = {}       # token -> dict
        self.chat = []           # list of dicts
        self.collections = {}    # (user_id, item_id) -> dict
        self.trades = []         # list of dicts
        self.ddl = []
        self.queries = []
        self.fail_connect = False

    def prune(self, table):
        """Simulate `DELETE FROM <table> WHERE user_id NOT IN (SELECT id FROM users)`."""
        store = getattr(self, table, None)
        if isinstance(store, dict):
            for k in [k for k, v in store.items() if v.get("user_id") not in self.users]:
                del store[k]
        elif isinstance(store, list):
            self.__dict__[table] = [r for r in store
                                    if r.get("user_id") in self.users or r.get("a") in self.users
                                    or r.get("b") in self.users]

    # --- statement handling ------------------------------------------------
    @staticmethod
    def unwrap(params):
        """Real psycopg2 hands back decoded JSON, not a Json wrapper - mimic that."""
        return tuple(p.value if isinstance(p, Json) else p for p in params)

    def execute(self, sql, params=()):
        flat = " ".join(sql.split())
        params = self.unwrap(params)
        self.queries.append((flat[:70], params))
        if flat.startswith("CREATE TABLE") or flat.startswith("CREATE INDEX"):
            self.ddl.append(flat)
            return []
        if flat.startswith("INSERT INTO users"):
            (uid, provider, username, name, email, avatar, sub, created, seen, rev, at,
             pw_hash, pw_salt, stats, record) = params
            self.users[uid] = dict(id=uid, provider=provider, username=username, name=name,
                                   email=email, avatar=avatar, sub=sub, created_at=created,
                                   last_seen=seen, rev=rev, at=at, pw_hash=pw_hash,
                                   pw_salt=pw_salt, stats=stats, record=record)
            return []
        if flat.startswith("INSERT INTO inventories"):
            uid, save, gems, gold, worth, owned, updated = params
            # user_id is a real column: keep it in the row so orphan-pruning can find it
            self.inventories[uid] = dict(user_id=uid, save=save, gems=gems, gold=gold,
                                         worth=worth, owned=owned, updated_at=updated)
            return []
        if flat.startswith("DELETE FROM leaderboards"):
            if not params:
                self.prune("leaderboards")
                return []
            uid = params[0]
            self.leaderboards = [r for r in self.leaderboards if r["user_id"] != uid]
            return []
        if flat.startswith("INSERT INTO leaderboards"):
            uid, kind, wave, score, worth, at = params
            self.leaderboards.append(dict(user_id=uid, kind=kind, wave=wave, score=score,
                                          worth=worth, at=at))
            return []
        if flat.startswith("DELETE FROM sessions"):
            self.sessions = {}
            return []
        if flat.startswith("INSERT INTO sessions"):
            token, uid, at = params
            self.sessions[token] = dict(token=token, user_id=uid, created_at=at)
            return []
        if flat.startswith("INSERT INTO chat_history"):
            uid, name, worth, body, at = params
            self.chat.append(dict(user_id=uid, name=name, worth=worth, body=body, at=at))
            return []
        if flat.startswith("INSERT INTO collections"):
            uid, item_id, rarity, worth, at = params
            self.collections[(uid, item_id)] = dict(user_id=uid, item_id=item_id, rarity=rarity,
                                                    worth=worth, at=at)
            return []
        if flat.startswith("DELETE FROM collections"):
            if not params:
                self.prune("collections")
                return []
            uid = params[0]
            self.collections = {k: v for k, v in self.collections.items() if v["user_id"] != uid}
            return []
        if flat.startswith("INSERT INTO trades"):
            a, b, state, offers, at = params
            self.trades.append(dict(a=a, b=b, state=state, offers=offers, at=at))
            return []
        if flat.startswith("TRUNCATE TABLE"):
            # the wipe: clear every table named in the statement and restart the identity
            attrs = {"trades": "trades", "collections": "collections",
                     "leaderboards": "leaderboards", "chat_history": "chat",
                     "sessions": "sessions", "inventories": "inventories", "users": "users"}
            for table, attr in attrs.items():
                if table in flat:
                    store = getattr(self, attr)
                    store.clear()
            self.seq = 0
            self.truncated = getattr(self, "truncated", [])
            self.truncated.append(flat)
            return []
        if flat.startswith("DELETE FROM") and "NOT IN (SELECT id FROM users)" in flat:
            table = flat.split("DELETE FROM", 1)[1].split("WHERE")[0].strip()
            self.prune("chat" if table == "chat_history" else table)
            return []
        raise AssertionError(f"unhandled statement: {flat[:90]}")

    def fetch(self, sql, params=()):
        flat = " ".join(sql.split())
        if flat.startswith("SELECT COUNT(*)"):
            # check this first: otherwise COUNT(*) is mistaken for a column name and the
            # real SELECT branches below answer with None
            table = flat.split("FROM", 1)[1].strip()
            return [(len(getattr(self, {"users": "users", "inventories": "inventories",
                                        "leaderboards": "leaderboards",
                                        "chat_history": "chat", "collections": "collections",
                                        "trades": "trades", "sessions": "sessions"}[table])),)]
        cols = flat.split("SELECT", 1)[1].split(" FROM ", 1)[0]
        names = [c.strip().split(".")[-1] for c in cols.split(",")]
        if "FROM users" in flat:
            out = []
            for uid, u in self.users.items():
                inv = self.inventories.get(uid, {})
                row = dict(id=u["id"], provider=u["provider"], username=u["username"], name=u["name"],
                           email=u["email"], avatar=u["avatar"], sub=u["sub"], created_at=u["created_at"],
                           last_seen=u["last_seen"], rev=u["rev"], at=u["at"], stats=u["stats"],
                           record=u.get("record"), save=inv.get("save"), gems=inv.get("gems"),
                           gold=inv.get("gold"))
                out.append(tuple(row.get(n) for n in names))
            return out
        if "FROM leaderboards" in flat:
            return [tuple(r.get(n) for n in names) for r in self.leaderboards]
        if "FROM sessions" in flat:
            return [tuple(r.get(n) for n in names) for r in self.sessions.values()]
        if "FROM collections" in flat:
            return [tuple(r.get(n) for n in names) for r in self.collections.values()]
        if "FROM trades" in flat:
            return [tuple(r.get(n) for n in names) for r in self.trades]
        if "FROM chat_history" in flat:
            lim = params[0] if params else 60
            return [tuple(r.get(n) for n in names) for r in self.chat[-int(lim):]][::-1]
        if flat.startswith("SELECT COUNT(*)"):
            table = flat.split("FROM", 1)[1].strip()
            return [(len(getattr(self, {"users": "users", "inventories": "inventories",
                                        "leaderboards": "leaderboards",
                                        "chat_history": "chat", "collections": "collections",
                                        "trades": "trades", "sessions": "sessions"}[table])),)]
        raise AssertionError(f"unhandled select: {flat[:90]}")


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rows = []
        self.description = None

    def execute(self, sql, params=()):
        flat = " ".join(sql.split())
        if flat.startswith("SELECT"):
            self.rows = self.db.fetch(flat, params)
            self.description = [("x",)] if self.rows is not None else None
            if not self.rows:
                self.description = [("x",)]
        else:
            self.rows = []
            self.description = None
            self.db.execute(flat, params)

    def fetchall(self):
        return list(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, db):
        self.db = db
        self.closed = 0
        self.autocommit = True

    def cursor(self):
        return FakeCursor(self.db)

    def close(self):
        self.closed = 1


def install_fake_psycopg2(db):
    mod = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")

    def connect(url, connect_timeout=None):
        if db.fail_connect:
            raise RuntimeError("could not connect to server: Connection refused")
        db.url = url
        return FakeConn(db)

    mod.connect = connect
    extras.Json = Json
    mod.extras = extras
    sys.modules["psycopg2"] = mod
    sys.modules["psycopg2.extras"] = extras
    return mod


def fresh_server(db, url):
    install_fake_psycopg2(db)
    os.environ["DATABASE_URL"] = url
    for name in ("server",):
        sys.modules.pop(name, None)
    return importlib.import_module("server")


def main():
    print("=" * 78)
    print("POSTGRES STORAGE LAYER (driver faked: no Postgres is available here)")
    print("=" * 78)

    db = FakeDB()
    sandbox = pathlib.Path(tempfile.mkdtemp())
    tmp = sandbox / "accounts.json"
    # Point the fallback file at the sandbox BEFORE importing, so the real accounts.json
    # is never even read (it holds a player's live account).
    os.environ["ACCOUNTS_FILE"] = str(tmp)
    srv = fresh_server(db, "postgresql://user:pw@db.example.com:5432/postgres")
    check("ACCOUNTS_FILE is honoured from the environment",
          str(srv.ACCOUNTS_FILE) == str(tmp), str(srv.ACCOUNTS_FILE))
    state = srv.Accounts(tmp)

    print("\n[1] tables are created on startup")
    names = [d.split("TABLE IF NOT EXISTS")[1].split("(")[0].strip() if "TABLE" in d
             else d.split("INDEX IF NOT EXISTS")[1].split("ON")[0].strip() for d in db.ddl]
    for t in ("users", "inventories", "leaderboards", "chat_history", "sessions"):
        check(f"table {t} created", t in names, str(names))
    check("indexes created too", len([d for d in db.ddl if "INDEX" in d]) >= 3, str(db.ddl))
    check("the store reports healthy", srv.PG.ok is True, srv.PG.why)

    print("\n[2] accounts land in the database")
    a1 = state.register("PgCaptain", "pgpass123", "pg@example.com")
    a2, _ = state.login_google("sub-pg-1", "pg@example.com", "PG Captain", None)
    check("local account written to users", "local:pgcaptain" in db.users, str(list(db.users)))
    check("google account written to users", "google:sub-pg-1" in db.users, str(list(db.users)))
    check("email stored", db.users["local:pgcaptain"]["email"] == "pg@example.com")
    check("inventory row created", "local:pgcaptain" in db.inventories, str(list(db.inventories)))

    print("\n[3] a profile push writes inventory, gems, gold and leaderboards")
    save = {"wallet": {"gems": 321}, "run": {"wave": 44, "gold": 5678},
            "cos": {"own": {"env:sunset": True, "turret:kraken": True}}}
    state.store_profile(a1, save, [{"kind": "run", "wave": 44, "score": 4400, "worth": 0, "at": 1}],
                        {"bestWave": 44, "gems": 321, "gold": 5678})
    inv = db.inventories["local:pgcaptain"]
    check("gems persisted", inv["gems"] == 321, str(inv))
    check("gold persisted", inv["gold"] == 5678, str(inv))
    # derived from the server's own generated points, so a rebalance cannot stale this
    want_worth = srv.ITEM_POINTS["env:sunset"] + srv.ITEM_POINTS["turret:kraken"]
    check("worth computed into the row", inv["worth"] == want_worth, f"{inv['worth']} vs {want_worth}")
    check("owned count computed into the row", inv["owned"] == 2, str(inv["owned"]))
    check("leaderboard row written", any(r["user_id"] == "local:pgcaptain" for r in db.leaderboards),
          str(db.leaderboards))
    check("no duplicate leaderboard rows on a re-flush",
          len([r for r in db.leaderboards if r["user_id"] == "local:pgcaptain"]) == 1,
          str(db.leaderboards))

    print("\n[4] sessions: issued, then revoked")
    token = state.issue(state.accounts["local:pgcaptain"])
    check("token written to sessions", token in db.sessions, str(list(db.sessions)))
    check("token maps to the account", db.sessions[token]["user_id"] == "local:pgcaptain")
    state.revoke(token)
    check("revoked token removed from sessions", token not in db.sessions, str(list(db.sessions)))

    print("\n[5] chat history")
    srv.CHAT.add_chat("local:pgcaptain", "PgCaptain", "ahoy from the database", 10050)
    srv.CHAT.add_chat("google:sub-pg-1", "PG Captain", "second message", 0)
    msgs = srv.CHAT.recent_chat(10)
    check("messages stored in chat_history", len(db.chat) == 2, str(db.chat))
    check("history comes back oldest-first",
          [m["body"] for m in msgs] == ["ahoy from the database", "second message"], str(msgs))
    check("name and worth travel with the message",
          msgs[0]["name"] == "PgCaptain" and msgs[0]["worth"] == 10050, str(msgs[0]))  # chat worth is whatever the caller passes

    print("\n[6] the real test: restart and read it all back")
    state2 = srv.Accounts(tmp)          # a fresh instance = a server restart
    check("both accounts came back", len(state2.accounts) == 2, str(list(state2.accounts)))
    check("the password hash survived",
          bool((state2.accounts.get("local:pgcaptain") or {}).get("hash")), "no hash after reload")
    check("the salt survived", bool((state2.accounts.get("local:pgcaptain") or {}).get("salt")))
    check("createdAt survived",
          int((state2.accounts.get("local:pgcaptain") or {}).get("createdAt") or 0) > 0,
          str((state2.accounts.get("local:pgcaptain") or {}).get("createdAt")))
    got = state2.accounts.get("local:pgcaptain") or {}
    check("username survived", got.get("username") == "PgCaptain", str(got.get("username")))
    check("email survived", got.get("email") == "pg@example.com")
    check("the whole save blob survived", (got.get("save") or {}).get("wallet", {}).get("gems") == 321,
          str(got.get("save"))[:120])
    check("gems survived", (got.get("save") or {}).get("wallet", {}).get("gems") == 321)
    check("gold survived", (got.get("save") or {}).get("run", {}).get("gold") == 5678)
    check("inventory items survived",
          (got.get("save") or {}).get("cos", {}).get("own", {}).get("turret:kraken") is True,
          str((got.get("save") or {}).get("cos"))[:120])
    check("stats survived", (got.get("stats") or {}).get("bestWave") == 44, str(got.get("stats")))
    check("profile revision survived", got.get("rev") == 1, str(got.get("rev")))
    check("leaderboard rows survived", len(got.get("boards") or []) == 1, str(got.get("boards")))
    check("google account survived too", "google:sub-pg-1" in state2.accounts)
    check("signing in again finds the same record",
          state2.login_local("PgCaptain", "pgpass123")["id"] == "local:pgcaptain")

    print("\n[7] a dead database must not take the game down")
    dead = FakeDB()
    dead.fail_connect = True
    tmp2 = pathlib.Path(tempfile.mkdtemp()) / "accounts.json"
    srv2 = fresh_server(dead, "postgresql://nope@nowhere:5432/none")
    srv2.ACCOUNTS_FILE = tmp2
    check("the store reports unhealthy", srv2.PG.ok is False, srv2.PG.why)
    check("...and says why", "could not" in srv2.PG.why or "not installed" in srv2.PG.why, srv2.PG.why)
    state3 = srv2.Accounts(tmp2)
    acct = state3.register("OfflineCap", "offlinepass", None)
    check("registration still works on the JSON fallback", acct["id"] == "local:offlinecap", str(acct)[:80])
    check("it wrote the local file instead", tmp2.is_file(), str(tmp2))
    check("and that file can be read back", (json.loads(tmp2.read_text())["accounts"].get("local:offlinecap") or {}).get("username") == "OfflineCap")
    check("the memory chat takes over", isinstance(srv2.CHAT, srv2.MemoryChat), type(srv2.CHAT).__name__)
    check("chat_store() also picks memory", isinstance(srv2.chat_store(), srv2.MemoryChat))
    srv2.chat_add("local:offlinecap", "OfflineCap", "still talking", 0)
    check("a message can still be sent", len(srv2.chat_recent(5)) == 1)
    check("chat_add falls back instead of raising", srv2.chat_add("x", "X", "y", 0)["body"] == "y")

    print("\n[8] the driver present but the database down (mid-session outage)")
    half = FakeDB()
    srv3 = fresh_server(half, "postgresql://user:pw@db.example.com:5432/postgres")
    check("healthy at first", srv3.PG.ok is True)
    half.fail_connect = True
    srv3.PG._conn = None            # the pool drops: next query must not explode
    try:
        srv3.chat_add("local:x", "X", "after the drop", 0)
        check("a chat write survives a mid-session outage", True)
    except Exception as exc:
        check("a chat write survives a mid-session outage", False, f"{type(exc).__name__}: {exc}")

    print("\n" + "=" * 78)
    print(f"{len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print("  FAILED:", f)
    print("=" * 78)
    print("NOTE: verified against a faked driver. Point DATABASE_URL at a real Postgres")
    print("      (or Supabase) to prove the DDL and the connection itself.")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
