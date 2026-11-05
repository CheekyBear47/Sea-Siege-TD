# Client: never drop a signed-in player on a transient error, let them link a
# username/password to the account they already have, and sync progress immediately.
import pathlib

p = pathlib.Path("index.html")
s = p.read_text(encoding="utf-8")
miss = []


def sub(old, new, why=""):
    global s
    if old not in s:
        miss.append(why or old[:70])
        return
    s = s.replace(old, new, 1)


# ============================================ 1. only a real rejection logs you out
sub("""    .catch(e => {
      if (serverDown(e)) return;          // offline: the local mirror carries on
      resetLocalAccount("Your account is no longer on the server (the harbour was reset) — " +
                        "create a fresh captain below.");
    });""",
    """    .catch(e => {
      // Careful: only an explicit rejection should ever cost a player their session.
      // A timeout, a 500 or a half-read reply must NOT sign anyone out.
      if (serverDown(e)) return;          // offline: the local mirror carries on
      if (!sessionRejected(e)) return;    // anything else: leave the session alone
      resetLocalAccount("Your account is no longer on the server (the harbour was reset) — " +
                        "create a fresh captain below.");
    });""", "validateSession guard")

sub("""function validateSession(token) {""",
    """// Does this error mean the server refused the session (as opposed to failing)? Only
// "session expired" / 401-style replies count.
function sessionRejected(e) {
  const msg = String((e && e.message) || e);
  return /session expired|not signed in|unauthor|401|no such (account|token)/i.test(msg) &&
         !/did not answer|unreadable|Failed to fetch|NetworkError|network/i.test(msg);
}
function validateSession(token) {""", "sessionRejected helper")

# ============================================ 2. link username/password to an account
sub("""      <div class="sect2">Profile picture</div>
      <div class="pfp-row" id="pfp-row"></div>""",
    """      <div class="sect2">Profile picture</div>
      <div class="pfp-row" id="pfp-row"></div>
      <div class="sect2" id="link-head">Sign-in credentials</div>
      <div id="link-box"></div>""", "link markup")

sub("""/* ------------------------ profile pictures -------------------------------- */""",
    """/* ------------------- linking a second way in ------------------------------- */
// One profile per player. A Google account can attach a username and password to the
// SAME account, so signing in the other way lands on the same gems and turrets instead
// of quietly creating a second, empty profile.
function renderLink() {
  const box = document.getElementById("link-box");
  const head = document.getElementById("link-head");
  if (!box) return;
  const acct = activeAccount();
  box.textContent = "";
  if (!acct) {
    if (head) head.hidden = true;
    box.hidden = true;
    return;
  }
  box.hidden = false;
  if (head) head.hidden = false;
  const hasLocal = !!acct.hash;
  if (hasLocal) {
    const row = el("div", "link-note on");
    row.appendChild(el("b", null, "✓ Username &amp; password set"));
    row.appendChild(el("span", null, " You can sign in as " + (acct.username || "your username") +
      (acct.provider === "google" ? ", or with Google." : ".") +
      " Both open this same profile."));
    box.appendChild(row);
    return;
  }
  const row = el("div", "link-note");
  row.appendChild(el("b", null, "Add a username &amp; password"));
  row.appendChild(el("span", null, acct.provider === "google"
    ? " So you can sign in without Google — same profile, same gems."
    : " Set a password so you can sign in from anywhere."));
  box.appendChild(row);
  const form = el("div", "link-form");
  const user = document.createElement("input");
  user.id = "link-user";
  user.maxLength = 16;
  user.placeholder = "pick a username";
  user.spellcheck = false;
  const pass = document.createElement("input");
  pass.id = "link-pass";
  pass.type = "password";
  pass.placeholder = "password (6+ chars)";
  const go = el("button", "btn primary tiny", "Link it");
  go.onclick = () => linkCredentials(user.value.trim(), pass.value);
  [user, pass, go].forEach(x => form.appendChild(x));
  box.appendChild(form);
}
function linkCredentials(username, password) {
  const acct = activeAccount();
  if (!acct) { toast("Sign in first."); return; }
  if (!/^[A-Za-z0-9_]{3,16}$/.test(username)) {
    toast("Username: 3-16 letters, numbers or underscores.");
    return;
  }
  if ((password || "").length < 6) { toast("Password must be at least 6 characters."); return; }
  api("/api/account/link", { token: (readSession() || {}).token, username: username, password: password }, 15000)
    .then(j => {
      if (j && j.account) {
        const db = loadAccounts();
        db.accounts[j.account.id] = Object.assign({}, db.accounts[j.account.id] || {}, j.account);
        saveAccounts(db);
      }
      renderProfile();
      toast("Linked — you can now sign in as " + username + " (same profile).");
      syncNow();
    })
    .catch(e => toast("Could not link that: " + (e.message || e)));
}
/* ------------------------ profile pictures -------------------------------- */""",
    "link js")

sub("""  paintAvatar(document.getElementById("pf-avatar"), acct);
  renderPfp();""",
    """  paintAvatar(document.getElementById("pf-avatar"), acct);
  renderPfp();
  renderLink();""", "render link in profile")

sub("""  .pfp-row{display:flex;flex-wrap:wrap;gap:7px;margin:2px 0 4px}""",
    """  .pfp-row{display:flex;flex-wrap:wrap;gap:7px;margin:2px 0 4px}
  .link-note{display:flex;flex-direction:column;gap:3px;padding:9px 11px;border-radius:11px;
    font-size:11px;color:var(--dim);background:var(--glass-2);border:1px solid var(--stroke);margin-bottom:7px}
  .link-note b{font-size:11.5px;color:#eaf6ff}
  .link-note.on{border-color:rgba(87,224,138,.4);background:rgba(30,70,50,.3)}
  .link-form{display:flex;gap:7px;flex-wrap:wrap}
  .link-form input{flex:1 1 130px;min-width:0;padding:9px 11px;border-radius:10px;font:inherit;font-size:12px;
    color:var(--txt);background:rgba(8,16,28,.7);border:1px solid var(--stroke)}
  .link-form .btn{flex:0 0 auto}""", "link css")

sub("""    .catch(e => { restore(); setAuthError("lo", e.message || "Could not sign in."); });""",
    """    .catch(e => {
      restore();
      let msg = e.message || "Could not sign in.";
      if (localMode === "register" && /already taken/i.test(msg)) {
        msg += " If that account is yours, sign in with the way you made it (Google or your password) " +
               "and add a username from your profile — it stays the same profile.";
      }
      setAuthError("lo", msg);
    });""", "taken-username hint")

# ============================================ 3. sync progress immediately
sub("""  pushTimer = setTimeout(pushProfile, 5000);""",
    """  pushTimer = setTimeout(pushProfile, 1500);      // was 5s: progress should land fast""",
    "push debounce")

sub("""function queuePush() {
  const sess = readSession();
  if (!sess || !sess.token) return;
  if (pushTimer) clearTimeout(pushTimer);""",
    """// Fire a push almost immediately, for the moments that matter (a crate roll, an
// unlock, a purchase). The 15-second heartbeat still covers everything else.
function pushSoon(delay) {
  const sess = readSession();
  if (!sess || !sess.token) return;
  if (pushTimer) clearTimeout(pushTimer);
  pushTimer = setTimeout(pushProfile, Math.max(250, delay || 400));
}
function queuePush() {
  const sess = readSession();
  if (!sess || !sess.token) return;
  if (pushTimer) clearTimeout(pushTimer);""", "pushSoon")

sub("""    ui();
    renderInventory();
    if (overlayOpen("crates")) renderCratesPanel();
  };""",
    """    ui();
    renderInventory();
    if (overlayOpen("crates")) renderCratesPanel();
    pushSoon(250);          // a crate roll is exactly the sort of thing that must not be lost
  };""", "push on roll")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
