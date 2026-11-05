# Permanent cloud persistence: a Postgres/Supabase backend driven by DATABASE_URL,
# with the JSON file kept as the offline fallback so the game always runs.
import pathlib

p = pathlib.Path("server.py")
s = p.read_text(encoding="utf-8")
miss = []


def sub(old, new, why=""):
    global s
    if old not in s:
        miss.append(why or old[:70])
        return
    s = s.replace(old, new, 1)


PG = '''

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
         stats       JSONB DEFAULT '{}'::jsonb
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
    "CREATE INDEX IF NOT EXISTS leaderboards_user_idx ON leaderboards (user_id)",
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
             rev, at, stats, save, gems, gold) in self.rows(
                """SELECT u.id, u.provider, u.username, u.name, u.email, u.avatar, u.sub,
                          u.created_at, u.last_seen, u.rev, u.at, u.stats,
                          i.save, i.gems, i.gold
                     FROM users u LEFT JOIN inventories i ON i.user_id = u.id"""):
            accounts[uid] = {
                "id": uid, "provider": provider, "username": username, "name": name,
                "email": email, "avatar": avatar, "sub": sub,
                "created": created or 0, "lastSeen": seen or 0, "rev": rev or 0, "at": at or 0,
                "stats": stats or {}, "save": save, "boards": [],
            }
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
        self.run(
            """INSERT INTO users (id, provider, username, name, email, avatar, sub,
                                 created_at, last_seen, rev, at, stats)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET
                 provider = EXCLUDED.provider, username = EXCLUDED.username, name = EXCLUDED.name,
                 email = EXCLUDED.email, avatar = EXCLUDED.avatar, sub = EXCLUDED.sub,
                 last_seen = EXCLUDED.last_seen, rev = EXCLUDED.rev, at = EXCLUDED.at,
                 stats = EXCLUDED.stats""",
            (acct.get("id"), acct.get("provider"), acct.get("username"), acct.get("name"),
             acct.get("email"), acct.get("avatar"), acct.get("sub"),
             int(acct.get("created") or 0), int(acct.get("lastSeen") or 0),
             int(acct.get("rev") or 0), int(acct.get("at") or 0),
             self.json(acct.get("stats") or {})))
        self.run(
            """INSERT INTO inventories (user_id, save, gems, gold, worth, owned, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id) DO UPDATE SET
                 save = EXCLUDED.save, gems = EXCLUDED.gems, gold = EXCLUDED.gold,
                 worth = EXCLUDED.worth, owned = EXCLUDED.owned, updated_at = EXCLUDED.updated_at""",
            (acct.get("id"), self.json(save), gems, gold,
             profile_worth(save) if save else 0, profile_owned(save) if save else 0,
             int(time.time() * 1000)))
        self.run("DELETE FROM leaderboards WHERE user_id = %s", (acct.get("id"),))
        for row in (acct.get("boards") or [])[-40:]:
            self.run(
                """INSERT INTO leaderboards (user_id, kind, wave, score, worth, at)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (acct.get("id"), str(row.get("kind") or "run"), int(row.get("wave") or 0),
                 int(row.get("score") or 0), int(row.get("worth") or 0), int(row.get("at") or 0)))

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


PG = PgStore(DATABASE_URL) if DATABASE_URL else None
CHAT = PG or MemoryChat()
'''

# insert the storage layer just above the Accounts class
sub("""class Accounts:
    \"\"\"Player accounts, persisted to a JSON file.""",
    PG.lstrip("\n") + """

class Accounts:
    \"\"\"Player accounts. Persisted to Postgres when DATABASE_URL is set, else a JSON file.""",
    "pg store insert")

# load: prefer the database
sub("""    # --- storage ---------------------------------------------------------
    def load(self) -> None:
        try:
            if self.path.is_file():
                blob = json.loads(self.path.read_text(encoding="utf-8") or "{}")
                self.accounts = blob.get("accounts") or {}
                self.tokens = blob.get("tokens") or {}
        except (OSError, ValueError) as exc:
            print(f"[auth] could not read {self.path.name} ({exc}) - starting empty")""",
    """    # --- storage ---------------------------------------------------------
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
            print(f"[auth] could not read {self.path.name} ({exc}) - starting empty")""",
    "accounts load")

# flush: write through to the database, and keep the JSON copy as a backup
sub("""    def flush(self) -> None:
        \"\"\"Write atomically - a half-written accounts.json would lose every profile.\"\"\"
        with self.lock:
            blob = {"accounts": self.accounts, "tokens": self.tokens, "saved": time.time()}
            tmp = self.path.with_name(self.path.name + ".tmp")
            try:
                tmp.write_text(json.dumps(blob, separators=(",", ":")), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError as exc:
                print(f"[auth] could not save {self.path.name} ({exc})")""",
    """    def flush(self) -> None:
        \"\"\"Persist every profile. Postgres when configured, else an atomic JSON write.\"\"\"
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
                tmp.write_text(json.dumps(blob, separators=(",", ":")), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError as exc:
                if not (PG and PG.ok):
                    print(f"[auth] could not save {self.path.name} ({exc})")""",
    "accounts flush")

# mark accounts dirty on mutation so the write-through stays cheap
sub("""    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lock = threading.RLock()
        self.accounts: dict[str, dict] = {}
        self.tokens: dict[str, dict] = {}
        self.load()""",
    """    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lock = threading.RLock()
        self.accounts: dict[str, dict] = {}
        self.tokens: dict[str, dict] = {}
        self._sig: dict[str, int] = {}       # content signature of what the DB last took
        self._tsig = None                    # signature of the token set
        self.load()""",
    "accounts init")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
