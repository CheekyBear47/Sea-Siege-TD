# Server side of Global Chat + PFP: a persistent chat log, live broadcast, and an
# avatar setter on the account API.
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


# --- reading the log ---------------------------------------------------------
sub("""        if path == "/api/health":""",
    """        if path == "/api/chat":
            # The permanent log (Postgres when configured, memory otherwise).
            return self._json({"ok": True, "at": int(time.time() * 1000),
                               "messages": chat_recent(80)})
        if path == "/api/health":""", "GET /api/chat")

# --- sending a message -------------------------------------------------------
sub("""        if path == "/api/join":""",
    """        if path == "/api/chat/send":
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
        if path == "/api/join":""", "POST /api/chat/send")

# --- the avatar setter -------------------------------------------------------
sub("""            if action in ("session", "username", "save"):""",
    """            if action in ("session", "username", "save", "avatar"):""", "account group")

sub("""                if action == "username":
                    return self._acct_ok(ACCOUNTS.set_username(acct["id"], body.get("username")),
                                         token=body.get("token"))""",
    """                if action == "username":
                    return self._acct_ok(ACCOUNTS.set_username(acct["id"], body.get("username")),
                                         token=body.get("token"))
                if action == "avatar":
                    return self._acct_ok(ACCOUNTS.set_avatar(acct["id"], body.get("avatar")),
                                         token=body.get("token"))""", "avatar route")

# --- Accounts.set_avatar -----------------------------------------------------
sub("""    def set_username(self, acct_id: str, username) -> dict:""",
    """    def set_avatar(self, acct_id: str, avatar) -> dict:
        \"\"\"Choose the player's profile picture (a glyph, or Google's image URL).\"\"\"
        avatar = str(avatar or "").strip()[:200] or None
        with self.lock:
            acct = self.accounts.get(acct_id)
            if not acct:
                raise ValueError("No such account.")
            acct["avatar"] = avatar
            acct["lastSeen"] = int(time.time() * 1000)
        self.flush()
        return acct

    def set_username(self, acct_id: str, username) -> dict:""", "set_avatar")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
