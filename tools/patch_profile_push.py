# One-off: make profile pushes carry the LIVE run, and never lose the final push.
# Run from the project root:  python tools/patch_profile_push.py
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


# 1. the payload is built from the live game state, and refreshes the local mirror
sub("""function profilePayload() {
  const auth = readAuth();
  const a = auth && auth.mode === "account" ? loadAccounts().accounts[auth.current] : null;
  return {
    save: a && a.save ? a.save : readSave(),
    boards: a && a.boards ? a.boards : loadBoard(),
    stats: a ? Object.assign(statsDefaults(), a.stats || {}) : null,
  };
}""",
    """// Built from the LIVE game state every time. An earlier version sent the mirror's
// snapshot, which was captured at boot - so a run played afterwards synced as null.
function profilePayload() {
  const auth = readAuth();
  const db = loadAccounts();
  const a = auth && auth.mode === "account" ? db.accounts[auth.current] : null;
  if (a) {
    a.save = readSave();
    a.boards = loadBoard();
    a.stats = Object.assign(statsDefaults(), a.stats || {});
    a.lastSeen = Date.now();
    saveAccounts(db);
  }
  return {
    save: a ? a.save : readSave(),
    boards: a ? a.boards : loadBoard(),
    stats: a ? a.stats : null,
  };
}""", "profilePayload")

# 2. flush now / send on the way out, plus a slow heartbeat so progress lands server-side
sub("""function pushProfile() {
  const sess = readSession();
  const auth = readAuth();
  if (!sess || !sess.token || !auth || auth.mode !== "account") return Promise.resolve();
  return api("/api/account/save", Object.assign({ token: sess.token }, profilePayload()), 15000)
    .catch(() => { /* offline: the local mirror still has everything */ });
}""",
    """function pushProfile() {
  const sess = readSession();
  const auth = readAuth();
  if (!sess || !sess.token || !auth || auth.mode !== "account") return Promise.resolve();
  return api("/api/account/save", Object.assign({ token: sess.token }, profilePayload()), 15000)
    .catch(() => { /* offline: the local mirror still has everything */ });
}
// Push right now instead of waiting for the debounce (leaving, switching, hiding).
function flushPush() {
  if (pushTimer) { clearTimeout(pushTimer); pushTimer = null; }
  return pushProfile();
}
// sendBeacon survives a reload or a tab close, where a fetch would be cancelled.
function beaconProfile() {
  const sess = readSession(), auth = readAuth();
  if (!sess || !sess.token || !auth || auth.mode !== "account") return;
  try {
    const blob = new Blob([JSON.stringify(Object.assign({ token: sess.token }, profilePayload()))],
      { type: "application/json" });
    if (navigator.sendBeacon) navigator.sendBeacon("/api/account/save", blob);
    else pushProfile();
  } catch (e) { pushProfile(); }
}
// A slow heartbeat: whatever happens, the server copy is at most a minute behind.
setInterval(() => { if (activeAccount()) pushProfile(); }, 45000);
document.addEventListener("visibilitychange", () => { if (document.hidden) beaconProfile(); });""",
    "pushProfile + flush/beacon")

# 3. the unload handler uses the shared helper (it must see the live run too)
sub("""window.addEventListener("beforeunload", () => {
  const sess = readSession(), auth = readAuth();
  if (!sess || !sess.token || !auth || auth.mode !== "account") return;
  try {
    const blob = new Blob([JSON.stringify(Object.assign({ token: sess.token }, profilePayload()))],
      { type: "application/json" });
    if (navigator.sendBeacon) navigator.sendBeacon("/api/account/save", blob);
  } catch (e) {}
});""",
    """window.addEventListener("beforeunload", () => beaconProfile());""", "beforeunload")

# 4. signing out pushes first - the session is still valid at this point
sub("""  const sess = readSession();
  if (sess && sess.token) api("/api/account/logout", { token: sess.token }).catch(() => {});
  switchingProfile = true;
  writeSession(null);""",
    """  const sess = readSession();
  if (sess && sess.token) {
    beaconProfile();                      // last chance to sync before the token dies
    api("/api/account/logout", { token: sess.token }).catch(() => {});
  }
  switchingProfile = true;
  writeSession(null);""", "signOut push")

# 5. and so does a profile switch
sub("""  document.getElementById("auth").classList.add("hidden");
  toast("Loading " + label + "…");
  setTimeout(() => location.reload(), 220);""",
    """  beaconProfile();
  document.getElementById("auth").classList.add("hidden");
  toast("Loading " + label + "…");
  setTimeout(() => location.reload(), 220);""", "reloadForProfile push")

# 6. syncProfile refreshes the mirror from the live state before queueing
sub("""  a.save = readSave();
  a.boards = loadBoard();
  a.stats = Object.assign(statsDefaults(), a.stats || {});
  a.lastSeen = Date.now();
  saveAccounts(db);
  queuePush();
}""",
    """  a.save = readSave();
  a.boards = loadBoard();
  a.stats = Object.assign(statsDefaults(), a.stats || {});
  a.lastSeen = Date.now();
  saveAccounts(db);
  queuePush();
}""", "syncProfile (unchanged guard)")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
