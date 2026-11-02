# One-off migration: server-backed accounts + dual sign-in on the client.
# Run from the project root:  python tools/patch_dual_auth_client.py
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


# 1. the accounts section is no longer local-only
sub("""// Local-only accounts. Passwords are salted and stretched with PBKDF2 in the
// browser and never leave this device — this gates a local profile, it is NOT a
// server login. Google sign-in is real OAuth via Google Identity Services and
// needs a Client ID whose origin list includes this page.
const ACCOUNTS_KEY = "seaSiege.accounts.v1";
const AUTH_KEY = "seaSiege.auth.v1";""",
    """// Accounts are owned by the game server (server.py -> accounts.json) and keyed by a
// STABLE identity: the Google `sub` for OAuth players, `local:<username>` for
// username/password players. The browser keeps a mirror of the signed-in account so
// the game still loads if the server is briefly unreachable, plus a session token
// that gets a returning player straight back in. Passwords never live in the
// browser: they are sent to the server, salted and stretched there with PBKDF2
// (120k rounds), and only the hash is kept.
const ACCOUNTS_KEY = "seaSiege.accounts.v1";
const AUTH_KEY = "seaSiege.auth.v1";
const SESSION_KEY = "seaSiege.session.v1";""", "accounts header")

# 2. session helpers + the server API, right after writeAuth
sub("""function writeAuth(v) { try { localStorage.setItem(AUTH_KEY, JSON.stringify(v)); } catch (e) {} }""",
    """function writeAuth(v) { try { localStorage.setItem(AUTH_KEY, JSON.stringify(v)); } catch (e) {} }
function readSession() {
  try { const raw = localStorage.getItem(SESSION_KEY); return raw ? JSON.parse(raw) : null; }
  catch (e) { return null; }
}
function writeSession(v) {
  try {
    if (v) localStorage.setItem(SESSION_KEY, JSON.stringify(v));
    else localStorage.removeItem(SESSION_KEY);
  } catch (e) {}
}
// --- server API ----------------------------------------------------------------
// Every account call goes to the game server, which owns the accounts file and is
// the only thing that decides who a player is. The token it returns is the session:
// that is what carries a profile to another device and lets a returning player in
// without signing in again.
async function api(path, body, ms) {
  const ctl = typeof AbortController === "function" ? new AbortController() : null;
  const timer = ctl ? setTimeout(() => ctl.abort(), ms || 9000) : null;
  try {
    const res = await fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}), signal: ctl ? ctl.signal : undefined
    });
    let j = null;
    try { j = await res.json(); } catch (e) { j = null; }
    if (!j) throw new Error("the server sent an unreadable reply");
    if (!res.ok || j.ok === false) throw new Error(j.error || ("the server said " + res.status));
    return j;
  } catch (e) {
    if (e && e.name === "AbortError") throw new Error("the server did not answer in time");
    throw e;
  } finally { if (timer) clearTimeout(timer); }
}
function serverDown(e) {
  return /Failed to fetch|NetworkError|did not answer|unreadable reply|Load failed|network/i
    .test(String((e && e.message) || ""));
}
// Adopt a server reply: mirror the account locally and remember the session token.
function adoptSession(j) {
  const acct = Object.assign({}, j.account);
  writeSession({ token: j.token, id: acct.id, at: Date.now() });
  const db = loadAccounts();
  db.accounts[acct.id] = acct;
  db.order = db.order || [];
  if (db.order.indexOf(acct.id) < 0) db.order.push(acct.id);
  saveAccounts(db);
  return acct;
}
// Push the live profile to the server, debounced; localStorage is the offline mirror.
let pushTimer = null;
function queuePush() {
  const sess = readSession();
  if (!sess || !sess.token) return;
  if (pushTimer) clearTimeout(pushTimer);
  pushTimer = setTimeout(pushProfile, 5000);
}
function profilePayload() {
  const auth = readAuth();
  const a = auth && auth.mode === "account" ? loadAccounts().accounts[auth.current] : null;
  return {
    save: a && a.save ? a.save : readSave(),
    boards: a && a.boards ? a.boards : loadBoard(),
    stats: a ? Object.assign(statsDefaults(), a.stats || {}) : null,
  };
}
function pushProfile() {
  const sess = readSession();
  const auth = readAuth();
  if (!sess || !sess.token || !auth || auth.mode !== "account") return Promise.resolve();
  return api("/api/account/save", Object.assign({ token: sess.token }, profilePayload()), 15000)
    .catch(() => { /* offline: the local mirror still has everything */ });
}
// Last-ditch save on the way out - sendBeacon survives the page unloading.
window.addEventListener("beforeunload", () => {
  const sess = readSession(), auth = readAuth();
  if (!sess || !sess.token || !auth || auth.mode !== "account") return;
  try {
    const blob = new Blob([JSON.stringify(Object.assign({ token: sess.token }, profilePayload()))],
      { type: "application/json" });
    if (navigator.sendBeacon) navigator.sendBeacon("/api/account/save", blob);
  } catch (e) {}
});""", "session + api")

# 3. syncing a profile also queues a server push
sub("""  a.stats = Object.assign(statsDefaults(), a.stats || {});
  a.lastSeen = Date.now();
  saveAccounts(db);
}
function bumpAccountStats(patch) {""",
    """  a.stats = Object.assign(statsDefaults(), a.stats || {});
  a.lastSeen = Date.now();
  saveAccounts(db);
  queuePush();
}
function bumpAccountStats(patch) {""", "syncProfile push")

sub("""    else s[k] = (s[k] || 0) + (v || 0);
  }
  a.lastSeen = Date.now();
  saveAccounts(db);
}""",
    """    else s[k] = (s[k] || 0) + (v || 0);
  }
  a.lastSeen = Date.now();
  saveAccounts(db);
  queuePush();
}""", "bumpAccountStats push")

# 4. username onboarding: server-enforced uniqueness, then in
sub("""function confirmUsername() {
  setAuthError("un", "");                  // never leave a stale error on a good submit
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
}""",
    """function confirmUsername() {
  setAuthError("un", "");                  // never leave a stale error on a good submit
  const input = document.getElementById("un-name");
  const name = (input ? input.value : "").trim();
  if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) {
    setAuthError("un", "3-16 characters: letters, numbers and underscores only (no spaces).");
    return;
  }
  const sess = readSession();
  if (!sess || !sess.token) { setAuthError("un", "Your session expired — sign in again."); return; }
  const restore = armBusy(document.getElementById("un-go"), "Saving…");
  api("/api/account/username", { token: sess.token, username: name })
    .then(j => {
      const acct = adoptSession(j);        // the server is the judge of "already taken"
      setPending(null);
      sfx("gem");
      toast("Welcome, " + displayName(acct) + " — username set. Loading your harbour...");
      enterProfile(acct);                  // reload: gate opens, gameplay + trading unlock
    })
    .catch(e => { restore(); setAuthError("un", e.message || "Could not save that username."); });
}""", "confirmUsername")

# 5. one place that applies a profile's stored data to the browser
sub("""function reloadForProfile(label) {""",
    """// Put an account's run/boards into this browser's save slots (no reload).
function applyProfileToStorage(acct) {
  if (acct && acct.save) writeSave(Object.assign({}, acct.save, { owner: acct.id }));
  else clearSave();
  saveBoard((acct && acct.boards) || []);
}
function reloadForProfile(label) {""", "applyProfileToStorage")

sub("""  const auth = readAuth();
  if (auth && auth.mode === "account") {
    const a = loadAccounts().accounts[auth.current];
    if (a) {
      if (a.save) { const blob = Object.assign({}, a.save, { owner: auth.current }); writeSave(blob); }
      else clearSave();
      saveBoard(a.boards || []);
    }
  }""",
    """  const auth = readAuth();
  if (auth && auth.mode === "account") applyProfileToStorage(loadAccounts().accounts[auth.current]);""",
    "reloadForProfile body")

# 6. sign-out tells the server the token is finished
sub("""function signOut() {
  try { if (NET && NET.trade) netSignal("trade-cancel", { tradeId: NET.trade.id }); } catch (e) {}
  try { netLeave(); } catch (e) {}
  switchingProfile = true;
  writeAuth({ mode: null, current: null, at: Date.now() });
  location.reload();
}""",
    """function signOut() {
  try { if (NET && NET.trade) netSignal("trade-cancel", { tradeId: NET.trade.id }); } catch (e) {}
  try { netLeave(); } catch (e) {}
  const sess = readSession();
  if (sess && sess.token) api("/api/account/logout", { token: sess.token }).catch(() => {});
  switchingProfile = true;
  writeSession(null);
  writeAuth({ mode: null, current: null, at: Date.now() });
  location.reload();
}""", "signOut")

# 7. Google sign-in now hands the raw ID token to the server to verify
sub("""function onGoogleCredential(resp) {
  const claims = decodeJwt(resp && resp.credential);
  if (!claims || !claims.sub) { setAuthError("un", "Google returned an unreadable token. Try again."); return; }
  googleSignIn(claims);
}
function googleSignIn(claims) {
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
}""",
    """function onGoogleCredential(resp) {
  googleSignIn(resp && resp.credential);
}
// The ID token goes to the game server, which asks Google whether it is genuine and
// keys the account on its `sub`. The same Google account therefore resolves to the
// same record on every device, browser, origin and IP.
function googleSignIn(credential) {
  if (!credential) { setAuthError("google", "Google did not return a sign-in token."); return; }
  setAuthError("google", "Checking that with Google…");
  api("/api/account/google", { credential: credential }, 20000)
    .then(j => {
      const acct = adoptSession(j);
      setAuthError("google", "");
      if (j.needsUsername) {
        // first time with this Google account: still locked until they pick a name
        setPending(acct.id);
        gateLock(true);
        showUsernamePane(acct);
        return;
      }
      setPending(null);
      toast((j.created ? "Welcome aboard, " : "Welcome back, ") + displayName(acct) +
            " — loading your harbour…");
      enterProfile(acct);              // returning player: straight in, save and all
    })
    .catch(e => setAuthError("google", e.message || "Google sign-in failed."));
}""", "googleSignIn")

# 8. errors now live in three panes
sub("""function setAuthError(which, msg) {
  const el2 = document.getElementById(which === "un" ? "un-err" : "google-note");
  if (el2) el2.textContent = msg || "";
}""",
    """function setAuthError(which, msg) {
  const id = which === "un" ? "un-err" : which === "lo" ? "lo-err" : "google-note";
  const el2 = document.getElementById(id);
  if (el2) el2.textContent = msg || "";
}""", "setAuthError")

# 9. modal switching: one function owns which pane is visible
sub("""function openAuthModal() {
  initGoogle();
  document.getElementById("auth").classList.remove("hidden");
  promptGoogle();
}""",
    """// --- modal switching ---------------------------------------------------------
// ONE function decides which pane is visible, so Google / username-password / the
// username onboarding screen can never stack, half-hide or leave a dead button.
let localMode = "signin";
function showAuthPane(name) {
  const panes = { google: "pane-google", local: "pane-local", username: "pane-username" };
  for (const key of Object.keys(panes)) {
    const el2 = document.getElementById(panes[key]);
    if (el2) el2.hidden = key !== name;
  }
  const gbtn = document.getElementById("google-play");
  if (gbtn) gbtn.hidden = name !== "google";
  const slot = document.getElementById("gsi-slot");
  if (slot) slot.hidden = name !== "google";
  document.querySelectorAll("#auth-tabs .atab").forEach(t =>
    t.classList.toggle("on", t.dataset.pane === name));
  setAuthError("un", "");
  setAuthError("lo", "");
  if (name === "google") { setAuthError("google", ""); initGoogle(); }
  if (name === "local") setLocalMode(localMode);
  if (name === "username") {
    const input = document.getElementById("un-name");
    if (input) { input.value = ""; input.focus(); }
  }
}
function setLocalMode(mode) {
  localMode = mode === "register" ? "register" : "signin";
  document.querySelectorAll("#local-tabs .atab").forEach(t =>
    t.classList.toggle("on", t.dataset.lmode === localMode));
  const wrap = document.getElementById("lo-pass2-wrap");
  if (wrap) wrap.hidden = localMode !== "register";
  const go = document.getElementById("lo-go");
  if (go) go.textContent = localMode === "register" ? "Create account" : "Sign in";
  const pass = document.getElementById("lo-pass");
  if (pass) pass.setAttribute("autocomplete", localMode === "register" ? "new-password" : "current-password");
  setAuthError("lo", "");
}
// Disable a button for the duration of a request and hand back an undo.
function armBusy(btn, label) {
  if (!btn) return () => {};
  const was = btn.textContent, off = btn.disabled;
  btn.disabled = true;
  if (label) btn.textContent = label;
  return () => { btn.disabled = off; btn.textContent = was; };
}
// Option B: a username and password account, registered or checked by the server.
function localSubmit() {
  const val = id => { const e = document.getElementById(id); return e ? e.value : ""; };
  const name = val("lo-user").trim();
  const pass = val("lo-pass"), pass2 = val("lo-pass2");
  setAuthError("lo", "");
  if (localMode === "register") {
    if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) {
      setAuthError("lo", "Username: 3-16 letters, numbers or underscores.");
      return;
    }
    if (pass.length < 6) { setAuthError("lo", "Password must be at least 6 characters."); return; }
    if (pass !== pass2) { setAuthError("lo", "Those passwords do not match."); return; }
  } else if (!name || !pass) {
    setAuthError("lo", "Enter your username and password.");
    return;
  }
  const restore = armBusy(document.getElementById("lo-go"),
                          localMode === "register" ? "Creating…" : "Signing in…");
  api("/api/account/" + (localMode === "register" ? "register" : "login"),
      { username: name, password: pass }, 20000)
    .then(j => {
      const acct = adoptSession(j);
      setPending(null);
      toast((localMode === "register" ? "Account created — welcome, " : "Welcome back, ") +
            displayName(acct) + " — loading your harbour…");
      enterProfile(acct);
    })
    .catch(e => { restore(); setAuthError("lo", e.message || "Could not sign in."); });
}
function openAuthModal() {
  initGoogle();
  document.getElementById("auth").classList.remove("hidden");
  showAuthPane("google");
  promptGoogle();
}""", "showAuthPane")

# 10. the gate: a stored session token is enough to get back in
sub("""function authGate() {
  const acct = activeAccount();
  if (acct) { setPending(null); gateLock(false); return acct; }
  gateLock(true);
  // mid-onboarding after a reload?  Resume it (or finish it if the name was chosen).
  const pend = readPending();
  const p = pend && loadAccounts().accounts[pend.id];
  if (p && p.username) { enterProfile(p); return null; }
  if (p) showUsernamePane(p);
  return null;
}""",
    """function authGate() {
  const acct = activeAccount();
  if (acct) { setPending(null); gateLock(false); return acct; }
  gateLock(true);
  // mid-onboarding after a reload?  Resume it where the player left off.
  const pend = readPending();
  const p = pend && loadAccounts().accounts[pend.id];
  if (p && !p.username) { showAuthPane("username"); showUsernamePane(p); return null; }
  // A stored session token means this device has signed in before: unlock from it
  // rather than asking again. This is also the cross-device path - the server hands
  // back the profile, inventory and stats that belong to that account.
  const sess = readSession();
  if (sess && sess.token) resumeSession(sess.token);
  return null;
}
function resumeSession(token) {
  api("/api/account/session", { token: token })
    .then(j => {
      const acct = adoptSession(j);
      if (j.needsUsername) { setPending(acct.id); gateLock(true); showAuthPane("username"); showUsernamePane(acct); return; }
      setPending(null);
      applyProfileToStorage(acct);
      writeAuth({ mode: "account", current: acct.id, at: Date.now() });
      switchingProfile = true;              // stop the outgoing page saving over it
      gateLock(false);
      toast("Welcome back, " + displayName(acct) + " — loading your harbour…");
      setTimeout(() => location.reload(), 220);
    })
    .catch(e => {
      if (!serverDown(e)) writeSession(null);   // a rejected token is worthless
      // unreachable or expired: the gate stays up with both sign-in methods offered
    });
}""", "authGate")

# 11. the gate's error reset targets the new panes
sub("""  if (on) {
    const e1 = document.getElementById("si-err"), e2 = document.getElementById("su-err");
    if (e1) e1.textContent = "";
    if (e2) e2.textContent = "";
  }""",
    """  if (on) { setAuthError("un", ""); setAuthError("lo", ""); setAuthError("google", ""); }""",
    "gateLock errors")

# 12. Google note mentions the second method
sub("""  note.textContent = googleReady
    ? "Google prompt not showing? Use the button above — it runs the same Google sign-in."
    : "Google Identity Services could not load here (client ID, network or browser). Sign-in " +
      "requires Google, so try again in a normal window without tracking blockers.";""",
    """  note.textContent = googleReady
    ? "Google prompt not showing? Use the button above — it runs the same Google sign-in."
    : "Google Identity Services could not load here (client ID, network or browser), so use " +
      "the Username & password tab instead — same accounts, same progress.";""", "googleNote")

# 13. the profile panel describes both providers and the sync state
sub("""  document.getElementById("pf-id").textContent = acct
    ? "Google account" +
      " · " + (acct.email || acct.user || acct.id) + " · id " + acct.id
    : "signed out — sign in to play. Guest play has been removed, and the harbour stays locked until an account is active.";""",
    """  document.getElementById("pf-id").textContent = acct
    ? (acct.provider === "google" ? "Google account" : "Username & password account") +
      (acct.email ? " · " + acct.email : "") + " · id " + acct.id +
      (readSession() ? " · synced to the game server" : " · this device only")
    : "signed out — sign in to play. Guest play has been removed, and the harbour stays locked until an account is active.";""",
    "pf-id")

sub("""  addBadge(acct ? "🔐 Google sign-in" : "🔒 Google sign-in required");""",
    """  addBadge(acct ? (acct.provider === "google" ? "🔐 Google sign-in" : "🔑 Username & password")
                : "🔒 Sign in required");
  if (acct && readSession()) addBadge("☁ synced", "g");""", "profile badge")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
