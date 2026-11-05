# Account linking: one profile per human, whatever they sign in with. A Google player
# can attach a username/password to the SAME account instead of spawning a second one.
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


# --- Accounts.link_credentials ------------------------------------------------
sub("""    def set_avatar(self, acct_id: str, avatar) -> dict:""",
    """    def link_credentials(self, acct_id: str, username, password) -> dict:
        \"\"\"Attach a username/password to an EXISTING account (usually a Google one).

        This is what stops a second, empty profile appearing when somebody who signed
        in with Google later registers a username: the credential is added to the
        account they already have, so their gems, turrets and stats stay with them.
        \"\"\"
        username = str(username or "").strip()
        if not USERNAME_RE.match(username):
            raise ValueError("Username must be 3-16 characters: letters, numbers and underscores.")
        if len(str(password or "")) < 6:
            raise ValueError("Password must be at least 6 characters.")
        with self.lock:
            acct = self.accounts.get(acct_id)
            if not acct:
                raise ValueError("No such account.")
            taken = self.find_username(username)
            if taken and taken["id"] != acct_id:
                raise ValueError("That username belongs to another account - pick a different one.")
            salt = secrets.token_hex(16)
            acct["username"] = username
            acct["salt"] = salt
            acct["hash"] = self._hash(password, salt)
            # a linked account is reachable by both routes from now on
            acct["linked"] = True
            acct["lastSeen"] = int(time.time() * 1000)
        self.flush()
        return acct

    def set_avatar(self, acct_id: str, avatar) -> dict:""", "link_credentials")

# --- route --------------------------------------------------------------------
sub("""            if action in ("session", "username", "save", "avatar"):""",
    """            if action in ("session", "username", "save", "avatar", "link"):""", "account group")

sub("""                if action == "avatar":
                    return self._acct_ok(ACCOUNTS.set_avatar(acct["id"], body.get("avatar")),
                                         token=body.get("token"))""",
    """                if action == "avatar":
                    return self._acct_ok(ACCOUNTS.set_avatar(acct["id"], body.get("avatar")),
                                         token=body.get("token"))
                if action == "link":
                    return self._acct_ok(
                        ACCOUNTS.link_credentials(acct["id"], body.get("username"), body.get("password")),
                        token=body.get("token"))""", "link route")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
