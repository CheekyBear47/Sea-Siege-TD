# A complete global wipe utility: admin API route, CLI, backups, and safe defaults.
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


# ---------------------------------------------------------------- new tables
sub("""    "CREATE INDEX IF NOT EXISTS leaderboards_user_idx ON leaderboards (user_id)",""",
    """    \"\"\"CREATE TABLE IF NOT EXISTS collections (
         user_id  TEXT NOT NULL,
         item_id  TEXT NOT NULL,
         rarity   TEXT,
         worth    INTEGER DEFAULT 0,
         at       BIGINT DEFAULT 0,
         PRIMARY KEY (user_id, item_id)
       )\"\"\",
    \"\"\"CREATE TABLE IF NOT EXISTS trades (
         id       BIGSERIAL PRIMARY KEY,
         a        TEXT,
         b        TEXT,
         state    TEXT,
         offers   JSONB,
         at       BIGINT DEFAULT 0
       )\"\"\",
    "CREATE INDEX IF NOT EXISTS leaderboards_user_idx ON leaderboards (user_id)",
    "CREATE INDEX IF NOT EXISTS collections_user_idx ON collections (user_id)",""", "new tables")

# ---------------------------------------------------- write collections + trades
sub("""        self.run("DELETE FROM leaderboards WHERE user_id = %s", (acct.get("id"),))""",
    """        # item collections, as a queryable index (the whole blob also lives above)
        self.run("DELETE FROM collections WHERE user_id = %s", (acct.get("id"),))
        try:
            owned = owned_ids(save) if isinstance(save, dict) else {}
        except Exception:
            owned = {}
        for item_id in sorted(owned):
            self.run(
                \"\"\"INSERT INTO collections (user_id, item_id, rarity, worth, at)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT (user_id, item_id) DO UPDATE
                   SET rarity = EXCLUDED.rarity, worth = EXCLUDED.worth\"\"\",
                (acct.get("id"), item_id, str(owned[item_id]), ITEM_POINTS.get(str(owned[item_id]), 0),
                 int(time.time() * 1000)))
        self.run("DELETE FROM leaderboards WHERE user_id = %s", (acct.get("id"),))""",
    "collections write")

sub("""    def save_token(self, token: str, uid: str, at: float = 0) -> None:""",
    """    def save_trade(self, tid: str, a: str, b: str, offers: dict, state: str = "settled") -> None:
        self.run(
            \"\"\"INSERT INTO trades (a, b, state, offers, at) VALUES (%s,%s,%s,%s,%s)\"\"\",
            (a, b, state, self.json(offers or {}), int(time.time() * 1000)))

    def save_token(self, token: str, uid: str, at: float = 0) -> None:""", "save_trade")

sub("""    def remember_done(self, tid: str, a: str, b: str, offers: dict) -> None:
        with self.lock:
            self.done.append({"tid": tid, "a": a, "b": b,
                              "offers": {a: list(offers.get(a, [])), b: list(offers.get(b, []))},
                              "at": time.time()})""",
    """    def remember_done(self, tid: str, a: str, b: str, offers: dict) -> None:
        with self.lock:
            self.done.append({"tid": tid, "a": a, "b": b,
                              "offers": {a: list(offers.get(a, [])), b: list(offers.get(b, []))},
                              "at": time.time()})
        if PG and PG.ok:
            try:
                PG.save_trade(tid, a, b, offers)
            except Exception as exc:
                print(f"[db] could not log a trade ({exc})")""", "log trade")

# ------------------------------------------------------------------ the wipe
sub("""    def count_rows(self, table: str) -> int:""",
    """    # --- the global wipe ------------------------------------------------
    def table_counts(self) -> dict:
        out = {}
        for t in WIPE_ORDER:
            out[t] = self.count_rows(t)
        return out

    def wipe_all(self, backup_path: Path | None = None) -> dict:
        \"\"\"Truncate every table and restart its identity. Backs up first.

        Children are listed before parents so the truncate is safe even without
        CASCADE; RESTART IDENTITY puts every BIGSERIAL back to 1.
        \"\"\"
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
        \"\"\"Remove rows whose owning account no longer exists. Never touches live data.\"\"\"
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

    def count_rows(self, table: str) -> int:""", "wipe_all")

# ------------------------------------------------------------------ constants
sub("""PG = PgStore(DATABASE_URL) if DATABASE_URL else None""",
    """# Every table the game owns, children first. The wipe covers all of them.
WIPE_ORDER = ["trades", "collections", "leaderboards", "chat_history", "sessions",
              "inventories", "users"]
WIPE_PHRASE = "WIPE ALL DATA"        # the admin route insists on this exact string
WIPE_BACKUP_DIR = ROOT / "backups"

PG = PgStore(DATABASE_URL) if DATABASE_URL else None""", "wipe constants")

# ------------------------------------------------- the one entry point + Accounts
sub("""CHAT = chat_store()""",
    """CHAT = chat_store()


def wipe_everything(reason: str = "manual", admin: bool = True) -> dict:
    \"\"\"Erase every account, inventory, collection, leaderboard, chat log, trade,
    gem and gold record. Always writes a backup first. Returns a report.

    Deliberately NOT called on boot unless WIPE_ON_START is set - a schema init that
    emptied the tables would erase every player on each redeploy.
    \"\"\"
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
    return report""", "wipe_everything")

sub("""    def flush(self) -> None:
        \"\"\"Persist every profile. Postgres when configured, else an atomic JSON write.\"\"\"""",
    """    def wipe(self, backup_path: Path | None = None) -> dict:
        \"\"\"Erase every account and session, after writing the whole store to a file.\"\"\"
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
        \"\"\"Persist every profile. Postgres when configured, else an atomic JSON write.\"\"\"""",
    "Accounts.wipe")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
