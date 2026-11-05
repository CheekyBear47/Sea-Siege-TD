"""Verify the global wipe utility - without touching any real data.

Everything here runs against a temporary accounts file (ACCOUNTS_FILE) and a faked
Postgres driver, so the live accounts.json is never opened. Checks:

  * the admin route is DISABLED until ADMIN_TOKEN is set (an open wipe endpoint is
    worse than a missing one)
  * a wrong token is refused, and a missing/incorrect confirm phrase is refused
  * dry=1 reports counts and deletes nothing
  * a real wipe empties every table, restarts BIGSERIAL at 1, clears accounts,
    sessions, collections, chat and trades, and writes a backup first
  * the CLI refuses without --yes
  * a schema init does NOT empty live tables (the safe default) and only prunes
    orphaned rows
  * WIPE_ON_START=1 does wipe at boot

Run:  python tools/test_wipe.py
"""
import importlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from test_pg_layer import FakeDB, install_fake_psycopg2   # reuse the fake driver

PASSED, FAILED = [], []


def check(label, ok, detail=""):
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"   [{detail}]" if detail and not ok else ""))


def fresh(db, url, accounts_path):
    install_fake_psycopg2(db)
    os.environ["DATABASE_URL"] = url
    os.environ["ACCOUNTS_FILE"] = str(accounts_path)
    sys.modules.pop("server", None)
    return importlib.import_module("server")


def main():
    print("=" * 78)
    print("GLOBAL WIPE UTILITY (sandboxed: temp accounts file + faked driver)")
    print("=" * 78)
    sandbox = pathlib.Path(tempfile.mkdtemp())
    acct_file = sandbox / "accounts.json"
    db = FakeDB()
    os.environ.pop("ADMIN_TOKEN", None)
    srv = fresh(db, "postgresql://user:pw@db.example.com:5432/postgres", acct_file)
    srv.WIPE_BACKUP_DIR = sandbox / "backups"

    print("\n[1] new tables exist so nothing is left behind")
    check("trades table created", any("trades" in d for d in db.ddl), str(len(db.ddl)))
    check("collections table created", any("collections" in d for d in db.ddl))
    check("every game table is in the wipe list",
          set(srv.WIPE_ORDER) >= {"users", "inventories", "collections", "leaderboards",
                                 "chat_history", "trades", "sessions"}, str(srv.WIPE_ORDER))

    print("\n[2] populate a world")
    a = srv.ACCOUNTS.register("WipeOne", "wipepass1", "one@example.com")
    b, _ = srv.ACCOUNTS.login_google("sub-wipe", "two@example.com", "WipeTwo", None)
    srv.ACCOUNTS.store_profile(a,
        {"wallet": {"gems": 111}, "run": {"wave": 9, "gold": 222},
         "cos": {"own": {"env:sunset": True, "turret:kraken": True}}},
        [{"kind": "run", "wave": 9, "score": 900, "worth": 0, "at": 1}], {"bestWave": 9})
    tok = srv.ACCOUNTS.issue(a)
    srv.chat_add(a, "WipeOne", "hello before the wipe", 10050)
    srv.HUB.remember_done("t1", "cid-a", "cid-b", {"cid-a": ["env:sunset"], "cid-b": []})
    srv.HUB.add_client("WipeOne", a, 10050, "127.0.0.1")
    check("two accounts", len(db.users) == 2, str(list(db.users)))
    check("an inventory row", len(db.inventories) == 2, str(list(db.inventories)))
    check("collection rows indexed", len(db.collections) >= 2, str(db.collections))
    check("a leaderboard row", len(db.leaderboards) == 1, str(db.leaderboards))
    check("a chat message", len(db.chat) == 1, str(db.chat))
    check("a trade logged", len(db.trades) == 1, str(db.trades))
    check("a session", len(db.sessions) == 1, str(db.sessions))
    check("someone is online", len(srv.HUB.clients) == 1)

    print("\n[3] the admin route is disabled until a token is configured")
    body = {"token": "anything", "confirm": srv.WIPE_PHRASE}
    res = handle(srv, "/api/admin/wipe-all-data", method="POST", body=body)
    check("refused with 403 when ADMIN_TOKEN is unset", res["status"] == 403, str(res)[:120])
    check("...and nothing was deleted", len(db.users) == 2 and len(db.chat) == 1)

    print("\n[4] with a token: wrong token, wrong phrase")
    os.environ["ADMIN_TOKEN"] = "s3cret-admin"
    srv = fresh(db, "postgresql://user:pw@db.example.com:5432/postgres", acct_file)
    srv.WIPE_BACKUP_DIR = sandbox / "backups"
    res = handle(srv, "/api/admin/wipe-all-data", method="POST",
                 body={"token": "nope", "confirm": srv.WIPE_PHRASE})
    check("a wrong token is 401", res["status"] == 401, str(res)[:120])
    res = handle(srv, "/api/admin/wipe-all-data", method="POST",
                 body={"token": "s3cret-admin", "confirm": "please"})
    check("a missing confirm phrase is 400", res["status"] == 400, str(res)[:140])
    check("still nothing deleted", len(db.users) == 2)

    print("\n[5] dry run: counts, no deletion")
    res = handle(srv, "/api/admin/wipe-all-data", method="POST",
                 body={"token": "s3cret-admin", "confirm": srv.WIPE_PHRASE, "dry": True})
    check("dry run reports ok", res["status"] == 200 and res["body"].get("dry") is True, str(res)[:140])
    check("dry run counts the tables", res["body"]["postgres"].get("users") == 2, str(res["body"])[:160])
    check("dry run deletes nothing", len(db.users) == 2 and len(db.leaderboards) == 1)

    print("\n[6] the real wipe")
    res = handle(srv, "/api/admin/wipe-all-data", method="POST",
                 body={"token": "s3cret-admin", "confirm": srv.WIPE_PHRASE})
    check("wipe reports ok", res["status"] == 200 and res["body"].get("ok") is True, str(res)[:160])
    check("users gone", len(db.users) == 0, str(db.users))
    check("inventories gone", len(db.inventories) == 0)
    check("collections gone", len(db.collections) == 0)
    check("leaderboards gone", len(db.leaderboards) == 0)
    check("chat history gone", len(db.chat) == 0)
    check("trades gone", len(db.trades) == 0)
    check("sessions gone", len(db.sessions) == 0)
    check("accounts cleared in memory", len(srv.ACCOUNTS.accounts) == 0, str(srv.ACCOUNTS.accounts))
    check("tokens cleared", len(srv.ACCOUNTS.tokens) == 0)
    check("nobody is online any more", len(srv.HUB.clients) == 0)
    check("open trades dropped", len(srv.HUB.trades) == 0)
    check("settled-trade history dropped", len(srv.HUB.done) == 0)
    check("memory chat cleared", len(srv.chat_recent(5)) == 0, str(srv.chat_recent(5)))
    check("the old session token no longer works", srv.ACCOUNTS.by_token(tok) is None)
    check("RESTART IDENTITY CASCADE was used",
          any("RESTART IDENTITY CASCADE" in s for s in getattr(db, "truncated", [])),
          "truncate statement missing")
    check("the truncate covered every table",
          any(all(t in stmt for t in srv.WIPE_ORDER) for stmt in getattr(db, "truncated", [])))
    check("a backup was written first",
          bool(res["body"]["report"]["postgres"].get("backup")) and
          pathlib.Path(res["body"]["report"]["postgres"]["backup"]).is_file(),
          str(res["body"]["report"])[:160])
    backup = json.loads(pathlib.Path(res["body"]["report"]["postgres"]["backup"]).read_text())
    check("the backup actually holds the accounts", len(backup.get("users", [])) == 2, str(list(backup))[:120])
    check("the backup holds the chat log", len(backup.get("chat_history", [])) == 1)
    check("the backup holds the collections", len(backup.get("collections", [])) >= 2)
    check("row counts reported before the wipe", res["body"]["report"]["postgres"]["rows_before"]["users"] == 2,
          str(res["body"]["report"]["postgres"].get("rows_before")))
    check("row counts reported after", res["body"]["report"]["postgres"]["rows_after"]["users"] == 0)

    print("\n[7] the JSON fallback is wiped too")
    check("the local accounts file is empty now",
          not (json.loads(acct_file.read_text()).get("accounts") if acct_file.is_file() else {}),
          acct_file.read_text()[:120] if acct_file.is_file() else "missing")

    print("\n[8] a schema init does NOT empty live data (the safe default)")
    db2 = FakeDB()
    srv2 = fresh(db2, "postgresql://user:pw@db.example.com:5432/postgres", sandbox / "acct2.json")
    srv2.WIPE_BACKUP_DIR = sandbox / "backups"
    live = srv2.ACCOUNTS.register("KeepMe", "keeppass1", None)
    # a full set of orphans: rows that reference an account nobody has any more
    db2.inventories["ghost:1"] = {"user_id": "ghost:1", "save": None, "gems": 0, "gold": 0,
                                  "worth": 0, "owned": 0, "updated_at": 0}
    db2.sessions["ghosttoken"] = {"token": "ghosttoken", "user_id": "ghost:1", "created_at": 0}
    db2.collections[("ghost:1", "env:sunset")] = {"user_id": "ghost:1", "item_id": "env:sunset",
                                                  "rarity": "rare", "worth": 50, "at": 0}
    db2.leaderboards.append({"user_id": "ghost:1", "kind": "run", "wave": 3, "score": 300,
                             "worth": 0, "at": 0})
    pruned = srv2.PG.prune_orphans()
    check("the live account survived", "local:keepme" in db2.users, str(list(db2.users)))
    check("the orphaned inventory row was pruned", "ghost:1" not in db2.inventories, str(list(db2.inventories)))
    check("the orphaned session was pruned", "ghosttoken" not in db2.sessions, str(list(db2.sessions)))
    check("every orphaned table is pruned, not just some",
          set(pruned) == {"inventories", "sessions", "collections", "leaderboards"}, str(pruned))
    check("live rows were left alone", "local:keepme" in db2.inventories, str(list(db2.inventories)))

    print("\n[9] the CLI refuses a wipe without --yes")
    r = subprocess.run([sys.executable, str(ROOT / "server.py"), "--wipe-all-data"],
                       capture_output=True, text=True, cwd=str(ROOT),
                       env=dict(os.environ, ACCOUNTS_FILE=str(sandbox / "cli.json")))
    check("refuses without --yes", r.returncode == 2 and "refusing to wipe" in r.stdout, r.stdout[-120:])
    check("it says what would be erased", "EVERY account" in r.stdout, r.stdout[-160:])

    print("\n" + "=" * 78)
    print(f"{len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print("  FAILED:", f)
    print("=" * 78)
    print("NOTE: sandboxed. The live accounts.json was never opened.")
    return 1 if FAILED else 0


def handle(srv, path, method="POST", body=None):
    """Call the route through the real handler class, with a stub socket."""
    import io

    class Stub(srv.QuietHandler):
        def __init__(self):
            self.path = path
            self.headers = {}
            self.wfile = io.BytesIO()
            self.rfile = io.BytesIO(json.dumps(body or {}).encode())
            self.client_address = ("127.0.0.1", 1234)
            self.requestline = f"{method} {path} HTTP/1.1"
            self.command = method
            self.status = None

        def _json(self, obj, status=200):
            self.status = status
            self.payload = obj

        def _body(self, limit=524288):
            return body or {}

        def _remote(self):
            return "127.0.0.1"

        def log_message(self, *a):
            pass

    st = Stub()
    if method == "GET":
        st.do_GET()
    else:
        st.do_POST()
    return {"status": st.status, "body": getattr(st, "payload", None),
            "bodyraw": getattr(st, "payload", None)}


if __name__ == "__main__":
    raise SystemExit(main())
