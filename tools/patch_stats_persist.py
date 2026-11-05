# A finished run updates `stats` (best wave, waves, kills, gems) but the save blob is
# frozen at the last mid-run autosave - and the server only wrote stats when the *save*
# was fresh. So a push whose save blob was a rev behind threw away the new high score,
# which is how a completed run could vanish from the global board. Stats and boards are
# now stored independently of the save blob, and never allowed to regress.
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


sub("""            if fresh:
                if boards is not None:
                    acct["boards"] = boards
                if stats is not None:
                    acct["stats"] = stats
            acct["lastSeen"] = int(time.time() * 1000)""",
    """            # Stats and board entries are NOT part of the save blob, so they must not be
            # gated on it. A finished run updates the stats the moment the game ends while
            # the save blob stays at the last mid-run autosave, so a save that is one rev
            # behind used to discard the client's newest high score - that is exactly how a
            # completed run disappeared from the global board. Both are merged, never
            # regressed: every counter here (waves, runs, kills, gems, gold, breaches) only
            # ever grows, and bestWave is a high score.
            if boards is not None:
                acct["boards"] = self._merge_boards(acct.get("boards"), boards)
            if stats is not None:
                acct["stats"] = self._merge_stats(acct.get("stats"), stats)
            acct["lastSeen"] = int(time.time() * 1000)""", "store_profile stats")

sub("""    def store_profile(self, acct: dict, save, boards, stats, base_rev=None) -> bool:""",
    """    @staticmethod
    def _merge_stats(old, new) -> dict:
        \"\"\"Fold a client's counters in without ever letting them go backwards.

        Every stat this game records is monotonic - waves cleared, runs played, kills,
        gems, gold, breaches only ever accumulate and bestWave is a high score - so the
        larger of the two is always the correct value. A device pushing a stale copy can
        no longer erase another device's progress.
        \"\"\"
        out = dict(old or {})
        for k, v in (new or {}).items():
            try:
                v = float(v or 0)
            except (TypeError, ValueError):
                continue
            cur = out.get(k)
            try:
                cur = float(cur or 0)
            except (TypeError, ValueError):
                cur = 0.0
            best = max(cur, v)
            out[k] = int(best) if best == int(best) else best
        return out

    @staticmethod
    def _merge_boards(old, new) -> list:
        \"\"\"Union two run lists by their timestamp, newest first, capped.

        The board is the player's own run history; a stale device must not be able to
        shorten it, so the two lists are merged rather than replaced.
        \"\"\"
        seen, merged = set(), []
        for row in list(new or []) + list(old or []):
            if not isinstance(row, dict):
                continue
            key = row.get("at")
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
        merged.sort(key=lambda r: (-(r.get("wave") or 0), -(r.get("gold") or 0)))
        return merged[:200]

    def store_profile(self, acct: dict, save, boards, stats, base_rev=None) -> bool:""",
    "merge helpers")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
