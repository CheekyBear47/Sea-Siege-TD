# One-off migration: make authentication Google-only and add username onboarding.
# Run from the project root:  python tools/patch_google_only_auth.py
import pathlib

p = pathlib.Path("index.html")
s = p.read_text(encoding="utf-8")
miss = []


def sub(old, new, why=""):
    global s
    if old not in s:
        miss.append(why or old[:60])
        return
    s = s.replace(old, new, 1)


# 1. drop the PBKDF2 constant (there are no passwords any more)
sub("const PBKDF2_ITER = 120000;\n", "", "PBKDF2_ITER")

# 2. replace the hashing helpers with the username / onboarding-state helpers
old_hash = s[s.index("// --- password hashing"):s.index("// --- avatar helpers")]
sub(old_hash, """// --- display name, onboarding state -------------------------------------------
// Sign-in is Google-only, so there is no password hashing here at all. An account is
// identified by its Google `sub`; the in-game name is the username chosen on first run.
const PENDING_KEY = "seaSiege.pending.v1";
function displayName(acct) { return (acct && (acct.username || acct.name)) || "Captain"; }
function setPending(id) {
  try {
    if (id) localStorage.setItem(PENDING_KEY, JSON.stringify({ id: id, at: Date.now() }));
    else localStorage.removeItem(PENDING_KEY);
  } catch (e) {}
}
function readPending() {
  try { const raw = localStorage.getItem(PENDING_KEY); return raw ? JSON.parse(raw) : null; }
  catch (e) { return null; }
}
function usernameExists(name, exceptId) {
  const db = loadAccounts();
  return Object.keys(db.accounts).some(id => id !== exceptId &&
    String(db.accounts[id].username || "").toLowerCase() === String(name).toLowerCase());
}
""", "hash helpers")

# 3. replace local account creation / sign-in with the username onboarding screen
start = s.index("// --- signing in / out")
end = s.index("// Hand a profile over to the running game.")
sub(s[start:end], """// --- username onboarding -------------------------------------------------------
// Shown once per Google account: sign-in identifies the player, this names them.
function showUsernamePane(acct) {
  const pane = document.getElementById("pane-username");
  const who = document.getElementById("un-who");
  if (who) {
    who.textContent = "";
    const av = el("span", "avatar sm");
    paintAvatar(av, acct);
    who.appendChild(av);
    who.appendChild(el("span", null, (acct.email || acct.name || "Google account") +
      " — pick the name other captains will see"));
  }
  const gbtn = document.getElementById("google-play");
  if (gbtn) gbtn.hidden = true;                      // already signed in with Google
  const slot = document.getElementById("gsi-slot");
  if (slot) slot.hidden = true;
  if (pane) pane.hidden = false;
  setAuthError("un", "");
  const input = document.getElementById("un-name");
  if (input) { input.value = ""; input.focus(); }
}
function confirmUsername() {
  const pend = readPending();
  const db = loadAccounts();
  const acct = pend && db.accounts[pend.id];
  if (!acct) { setAuthError("un", "Your Google session expired — sign in with Google again."); return; }
  const input = document.getElementById("un-name");
  const name = (input ? input.value : "").trim();
  if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) {
    setAuthError("un", "3-16 characters: letters, numbers and underscores only (no spaces).");
    return;
  }
  if (usernameExists(name, acct.id)) {
    setAuthError("un", "That username is already taken on this device — pick another.");
    return;
  }
  acct.username = name;
  acct.name = name;                    // the in-game name IS the chosen username
  acct.namedAt = Date.now();
  db.accounts[acct.id] = acct;
  saveAccounts(db);
  setPending(null);
  sfx("gem");
  toast("Welcome, " + name + " — username set. Loading your harbour...");
  enterProfile(acct);                  // reload: gate opens, gameplay + trading unlock
}

""", "local account block")

# 4. a Google credential now either fast-passes a returning player or asks for a username
old_oc = s[s.index("function onGoogleCredential(resp) {"):s.index("// --- auth UI ---")]
sub(old_oc, """function onGoogleCredential(resp) {
  const claims = decodeJwt(resp && resp.credential);
  if (!claims || !claims.sub) { setAuthError("un", "Google returned an unreadable token. Try again."); return; }
  const db = loadAccounts();
  const id = "google:" + claims.sub;
  let acct = db.accounts[id];
  if (!acct) {
    acct = db.accounts[id] = {
      id, provider: "google", username: null,
      name: claims.name || claims.email || "Captain",
      user: claims.email || null, email: claims.email || null, avatar: claims.picture || null,
      createdAt: Date.now(), lastSeen: Date.now(),
      stats: statsDefaults(), save: null, boards: null
    };
    db.order = (db.order || []).concat(id);
  } else {
    // keep the username they chose; Google only refreshes identity details
    acct.name = acct.username || acct.name;
    acct.email = claims.email || acct.email;
    acct.avatar = claims.picture || acct.avatar;
  }
  saveAccounts(db);
  if (!acct.username) {
    // first time with this Google account: the gate stays locked until they name themselves
    setPending(acct.id);
    gateLock(true);
    showUsernamePane(acct);
    return;
  }
  setPending(null);
  enterProfile(acct);                  // returning player: straight in
}
""", "onGoogleCredential")

# 5. errors, and remove the pane switcher + local-account picker entirely
sub("""function setAuthError(which, msg) {
  const el2 = document.getElementById(which === "su" ? "su-err" : "si-err");
  if (el2) el2.textContent = msg || "";
}""", """function setAuthError(which, msg) {
  const el2 = document.getElementById(which === "un" ? "un-err" : "google-note");
  if (el2) el2.textContent = msg || "";
}""", "setAuthError")
sub(s[s.index("function showAuthPane(name) {"):s.index("function openAuthModal() {")], "", "pane switcher + known accounts")
sub("""function openAuthModal() {
  renderKnownAccounts();
  initGoogle();""", """function openAuthModal() {
  initGoogle();""", "openAuthModal")
sub("""function authGate() {
  const acct = activeAccount();
  gateLock(!acct);
  if (!acct) renderKnownAccounts();
  return acct;
}""", """function authGate() {
  const acct = activeAccount();
  if (acct) { setPending(null); gateLock(false); return acct; }
  gateLock(true);
  // mid-onboarding after a reload?  Resume it (or finish it if the name was chosen).
  const pend = readPending();
  const p = pend && loadAccounts().accounts[pend.id];
  if (p && p.username) { enterProfile(p); return null; }
  if (p) showUsernamePane(p);
  return null;
}""", "authGate")

# 6. profile wording: Google is the only provider now
sub('    ? (acct.provider === "google" ? "Google account" : "Local account") +',
    '    ? "Google account" +', "pf-id provider")
sub('  if (acct && !acct.hash && acct.provider === "local") addBadge("no password set");\n', "", "local badge")
sub("""  addBadge(acct ? (acct.provider === "google" ? "🔐 Google sign-in" : "🔐 Local account")
                : "🔒 Account required");""",
    """  addBadge(acct ? "🔐 Google sign-in" : "🔒 Google sign-in required");""", "profile badge")
sub('  document.getElementById("chip-name").textContent = acct ? acct.name : "Sign in required";',
    '  document.getElementById("chip-name").textContent = acct ? displayName(acct) : "Sign in required";', "chip name")
sub('  document.getElementById("pf-name").textContent = acct ? acct.name : "Captain";',
    '  document.getElementById("pf-name").textContent = acct ? displayName(acct) : "Captain";', "pf name")

# 7. the hub identity is the chosen in-game username
sub('    name: me ? me.name : "Captain",\n    prof: me ? me.id : "solo",',
    '    name: displayName(me),\n    prof: me ? me.id : "none",', "netJoin name")
sub('netPost("/api/ping", { id: NET.id, token: NET.token, name: me ? me.name : "Captain", worth: worthTotal() })',
    'netPost("/api/ping", { id: NET.id, token: NET.token, name: displayName(me), worth: worthTotal() })', "ping name")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
