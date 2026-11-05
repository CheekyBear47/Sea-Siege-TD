# The admin wipe route, the CLI switch, and startup safety (orphan pruning by
# default; a full wipe only when explicitly asked for).
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


# ------------------------------------------------------------------ admin token
sub("""WIPE_PHRASE = "WIPE ALL DATA"        # the admin route insists on this exact string""",
    """WIPE_PHRASE = "WIPE ALL DATA"        # the admin route insists on this exact string
# The admin wipe is DISABLED until a token is configured: an open endpoint that erases
# every account is a worse failure than forgetting to set a variable.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()""", "admin token")

# ------------------------------------------------------------------ the route
sub("""        if path == "/api/join":""",
    """        if path == "/api/admin/wipe-all-data":
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
        if path == "/api/join":""", "wipe route")

# ------------------------------------------------------- startup: safe by default
sub("""    print("=" * 66)
    print("  SEA SIEGE TOWER DEFENSE")
    print("=" * 66)""",
    """    # A schema init must NEVER silently empty the tables: that would erase every player
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
    print("=" * 66)""", "startup safety")

# ---------------------------------------------------------------- CLI switches
sub("""    p.add_argument("--no-verify-google", action="store_true", help="skip Google token verification (dev only)")""",
    """    p.add_argument("--no-verify-google", action="store_true", help="skip Google token verification (dev only)")
    p.add_argument("--wipe-all-data", action="store_true",
                   help="erase every account, inventory, collection, leaderboard, chat log, trade, "
                        "gem and gold record, then exit. Requires --yes.")
    p.add_argument("--wipe-on-start", action="store_true",
                   help="wipe everything at boot before serving (same as WIPE_ON_START=1)")
    p.add_argument("--yes", action="store_true", help="confirm a destructive command")""",
    "cli flags")

sub("""    if args.no_verify_google:""",
    """    if args.wipe_all_data:
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
        print("\\n  every player is back to a blank slate. Backups are in ./backups/")
        return 0

    if args.no_verify_google:""", "cli wipe")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
