# Global leaderboard, steeper economy, two new turret tiers, a 15s cloud auto-save with
# a HUD indicator, and manual login by username OR email.
import pathlib
import re

p = pathlib.Path("index.html")
s = p.read_text(encoding="utf-8")
miss = []
notes = []


def sub(old, new, why=""):
    global s
    if old not in s:
        miss.append(why or old[:70])
        return
    s = s.replace(old, new, 1)


# ===================================================================== HTML + CSS
sub("""      <div class="stat wave"><b id="ui-wave">0</b><small>Wave</small></div>
    </div>""",
    """      <div class="stat wave"><b id="ui-wave">0</b><small>Wave</small></div>
    </div>
    <div class="save-line" id="ui-save">☁ cloud save ready</div>""", "sidebar save line")

sub("""      <label>Username
        <input id="lo-user" maxlength="16" autocomplete="username" spellcheck="false" placeholder="Captain" />
      </label>
      <label>Password<input id="lo-pass" type="password" autocomplete="current-password" /></label>""",
    """      <label>Username or email
        <input id="lo-user" maxlength="64" autocomplete="username" spellcheck="false" placeholder="Captain or you@example.com" />
      </label>
      <label>Password<input id="lo-pass" type="password" autocomplete="current-password" /></label>
      <label id="lo-email-wrap" hidden>Email (optional, lets you sign in with either)
        <input id="lo-email" maxlength="64" autocomplete="email" spellcheck="false" placeholder="you@example.com" />
      </label>""", "login identifier field")

sub("""  .inv-selects{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px}""",
    """  .save-line{font-size:9.5px;color:var(--dim);margin-top:6px;text-align:center;letter-spacing:.3px}
  .save-line.ok{color:#8ee6b0}
  .save-line.busy{color:#8fd6ff}
  .save-line.bad{color:#ffb3b3}
  .lb-sorts{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 10px;align-items:center}
  .lb-sorts .inv-bar-label{margin-right:2px}
  .lb .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#3d4d60;margin-right:6px;
    vertical-align:middle}
  .lb .dot.on{background:#57e08a;box-shadow:0 0 7px rgba(87,224,138,.8)}
  .lb .me{color:#8fd6ff;font-weight:800}
  .lb .prov{font-size:9px;color:var(--dim);margin-left:5px}
  .inv-selects{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px}""", "overhaul css")

# ============================================================ two new turret tiers
sub("""  /* ---------- rank 5 — MYTHIC: crate drops only ---------- */
  trident: {""",
    """  /* ---------- rank 5 — 2,600..3,400 gold: end-game support ---------- */
  stormcaller: {
    name: "Stormcaller Battery", glyph: "🌩️", cost: 2600, rank: 5, kind: "Support",
    dmg: 205, rate: 0.62, range: 385, projType: "tesla",
    chain: 4, slow: 0.46, slowDur: 2.4, reveal: 220, color: "#a8c8ff",
    desc: "Storm chain that reveals and drags raiders",
    special: { name: "Chain Tempest", text: "storms jump two more times and pin everything they touch." }
  },
  wavebreak: {
    name: "Wavebreak Bastion", glyph: "🌊", cost: 3400, rank: 5, kind: "Artillery",
    dmg: 395, rate: 1.95, range: 520, projSpeed: 300, projType: "stone",
    splash: 195, minRange: 140, color: "#7fd0ff", desc: "Breaker shells, wide and relentless",
    special: { name: "Undertow", text: "the blast drags the survivors backwards down the channel." }
  },
  /* ---------- rank 6 — 5,200..7,000 gold: the endless-wave answers ---------- */
  sunforge: {
    name: "Sunforge Cathedral", glyph: "🔆", cost: 5200, rank: 6, kind: "Energy",
    dmg: 560, rate: 0.55, range: 470, projType: "ray", burnOn: true, color: "#ffd76a",
    desc: "Cathedral-scale solar lance, burns through armour",
    special: { name: "Corona Lance", text: "the lance widens and cooks a burning hole through the plating." }
  },
  dreadnought: {
    name: "Dreadnought Foundry", glyph: "⚙️", cost: 7000, rank: 6, kind: "Artillery",
    dmg: 980, rate: 3.05, range: 640, projSpeed: 240, projType: "stone",
    splash: 320, minRange: 175, color: "#ff9d4d",
    desc: "Foundry-forged shells that delete a squadron",
    special: { name: "Scrapstorm", text: "each shell leaves a burning killing field where it lands." }
  },
  /* ---------- rank 7 — MYTHIC: crate drops only ---------- */
  trident: {""", "new tiers")

for myth in ("trident", "kraken", "sunfire", "leviathan"):
    sub(f'cost: 2{"" if myth != "trident" else "000"}, rank: 5, mythic: true',
        f'cost: 2{"" if myth != "trident" else "000"}, rank: 7, mythic: true', "mythic rank") if False else None
# (the mythic entries differ per tower, so patch each one by its own cost line)
for old, new in [("cost: 2000, rank: 5, mythic: true", "cost: 2000, rank: 7, mythic: true"),
                 ("cost: 2400, rank: 5, mythic: true", "cost: 2400, rank: 7, mythic: true"),
                 ("cost: 2900, rank: 5, mythic: true", "cost: 2900, rank: 7, mythic: true"),
                 ("cost: 3500, rank: 5, mythic: true", "cost: 3500, rank: 7, mythic: true")]:
    sub(old, new, "mythic rank " + old)

sub("""const TOWER_ORDER = ["longbow", "slinger", "crossbow", "cannon", "harpoon",
                     "trebuchet", "tesla", "brazier", "mortar", "frostbite"];""",
    """const TOWER_ORDER = ["longbow", "slinger", "crossbow", "cannon", "harpoon",
                     "trebuchet", "tesla", "brazier", "mortar", "frostbite",
                     "stormcaller", "wavebreak", "sunforge", "dreadnought"];""", "TOWER_ORDER")

sub("""const RANK_BRACKETS = {
  1: "Tier I · 60–90 🪙", 2: "Tier II · 150–250 🪙", 3: "Tier III · 450–700 🪙",
  4: "Tier IV · 950–1,500 🪙", 5: "Mythic · crate drop only"
};""",
    """const RANK_BRACKETS = {
  1: "Tier I · 110–160 🪙", 2: "Tier II · 260–410 🪙", 3: "Tier III · 780–1,250 🪙",
  4: "Tier IV · 1,650–2,600 🪙", 5: "Tier V · 2,600–3,400 🪙 — end-game support",
  6: "Tier VI · 5,200–7,000 🪙 — endless answers", 7: "Mythic · crate drop only"
};""", "RANK_BRACKETS")

sub("""  [1, 2, 3, 4].forEach(rank => {""", """  [1, 2, 3, 4, 5, 6].forEach(rank => {""", "armory loop")

# ================================================================ economy rebalance
# Scale every purchasable turret's price in the table itself, so the numbers on the
# cards are the numbers the game charges (no hidden multiplier at load).
towers_at = s.index("const TOWERS = {")
towers_end = s.index("const TOWER_ORDER", towers_at)
block = s[towers_at:towers_end]
SCALE = 1.85


def scale_costs(text: str) -> tuple[str, list[tuple[str, int, int]]]:
    out = []
    changed = []

    def repl(m):
        old = int(m.group(2))
        new = int(round(old * SCALE / 5.0) * 5)
        changed.append((m.group(1), old, new))
        return f"{m.group(1)}{new}"
    # each entry looks like:  id: {\n ... cost: 60, rank: 1,
    pattern = re.compile(r"(cost: )(\d+)(, rank: [1-6],)")

    def repl2(m):
        old = int(m.group(2))
        new = int(round(old * SCALE / 5.0) * 5)
        changed.append(("", old, new))
        return f"{m.group(1)}{new}{m.group(3)}"
    return pattern.sub(repl2, text), changed


new_block, changed = scale_costs(block)
s = s[:towers_at] + new_block + s[towers_end:]
notes.append("tower prices x%.2f: " % SCALE + ", ".join(f"{o}->{n}" for _, o, n in changed))

# crates: steeper tags again (nominal gems, hard-earned at 1 gem/wave)
for old, new in [("glyph: \"📦\", gems: 6", "glyph: \"📦\", gems: 10"),
                 ("glyph: \"🎁\", gems: 18", "glyph: \"🎁\", gems: 30"),
                 ("glyph: \"⚜️\", gems: 45", "glyph: \"⚜️\", gems: 80"),
                 ("glyph: \"🔮\", gems: 120", "glyph: \"🔮\", gems: 220")]:
    sub(old, new, "crate price " + old)

sub("""  const bonus = Math.round((58 + G.wave * 21 + Math.round(G.globals.gold * 16)) * DIFFICULTY[G.diff].gold);""",
    """  const bonus = Math.round((44 + G.wave * 15 + Math.round(G.globals.gold * 12)) * DIFFICULTY[G.diff].gold);""",
    "wave bonus")

sub("""function enemyGoldMul() { return (1 + 0.022 * (G.wave - 1) + 0.04 * G.globals.gold) * DIFFICULTY[G.diff].gold; }""",
    """function enemyGoldMul() { return (1 + 0.016 * (G.wave - 1) + 0.03 * G.globals.gold) * DIFFICULTY[G.diff].gold; }""",
    "kill gold")

# ================================================== 15-second cloud auto-save + HUD
sub("""setInterval(() => { if (activeAccount()) pushProfile(); }, 20000);""",
    """// The auto-save loop: every 15 seconds, sync the run, wallet, inventory and stats to
// the account on the server. An unchanged profile is a no-op (see pushProfile), so this
// is cheap and an idle tab can never take the profile slot from an active device.
let saveState = { at: 0, ok: true, busy: false, err: "", count: 0 };
setInterval(() => { if (activeAccount()) syncNow("auto"); }, 15000);
function syncNow() {
  if (!activeAccount()) return Promise.resolve(null);
  saveState.busy = true;
  return pushProfile()
    .then(j => {
      saveState.busy = false;
      saveState.ok = true;
      saveState.err = "";
      saveState.at = Date.now();               // the data is on the server as of now
      if (j) saveState.count++;
      return j;
    })
    .catch(e => {
      saveState.busy = false;
      saveState.ok = false;
      saveState.err = String((e && e.message) || e);
      return null;
    });
}
function saveLine() {
  const age = saveState.at ? Math.round((Date.now() - saveState.at) / 1000) : null;
  if (!activeAccount()) return { text: "☁ sign in to sync your account", cls: "" };
  if (saveState.busy) return { text: "☁ saving to your account…", cls: "busy" };
  if (!saveState.ok) return { text: "☁ cloud save offline — retrying in 15s", cls: "bad" };
  if (age === null) return { text: "☁ cloud auto-save every 15s", cls: "" };
  return { text: "☁ saved " + (age < 5 ? "just now" : age < 60 ? age + "s ago" : Math.round(age / 60) + "m ago"),
           cls: "ok" };
}""", "autosave loop")

# mark the moment a sync lands (pushProfile may skip, and that still means "saved")
sub("""      if (sig === lastPushSig) return Promise.resolve();""",
    """      if (sig === lastPushSig) {
        saveState.at = Date.now();               // already up to date on the server
        return Promise.resolve(null);
      }""", "idle marks saved")

sub("""  // ---- bottom control bar ----""",
    """  // ---- auto-save indicator (row 3 of the readout) ----
  const sv = saveLine();
  ctx.textAlign = "left";
  ctx.font = "700 10px Segoe UI, sans-serif";
  ctx.fillStyle = sv.cls === "bad" ? "rgba(255,179,179,.9)"
    : sv.cls === "busy" ? "rgba(143,214,255,.9)" : "rgba(160,215,190,.72)";
  ctx.fillText(sv.text, hx + 24, hy + 100);

  // ---- bottom control bar ----""", "HUD save line")

sub("""  const hx = W - 418, hy = 14, hw = 404, hh = 92;""",
    """  const hx = W - 418, hy = 14, hw = 404, hh = 112;""", "HUD panel height")

# ============================================================== global leaderboard
sub("""const BOARD_TABS = [
  { id: "wave",    label: "🏆 Highest wave",   sort: (a, b) => (b.wave - a.wave) || (b.gold - a.gold) },""",
    """const BOARD_TABS = [
  { id: "global",  label: "🌍 Global captains", special: "global" },
  { id: "wave",    label: "🏆 Highest wave",   sort: (a, b) => (b.wave - a.wave) || (b.gold - a.gold) },""",
    "global tab")

sub("""let boardTab = "wave";""", """let boardTab = "global";
let globalSort = "wave";
let globalBoard = null;      // last /api/leaderboard reply
const GLOBAL_SORTS = [
  ["wave", "Best wave"], ["score", "Overall score"], ["wealth", "Total wealth"],
  ["gems", "Gems earned"], ["gold", "Gold earned"], ["worth", "Worth points"],
  ["kills", "Ships sunk"], ["collection", "Collections"]
];
function globalValue(r, key) {
  if (key === "wealth") return (r.gemsHeld || 0) * 1000 + (r.worth || 0);
  if (key === "collection") return r.owned || 0;
  return r[key] || 0;
}
// Fetch the server board (GET). Everything here is a registered profile, so offline
// captains stay on the board with their rank.
function apiGet(path, ms) {
  const ctl = typeof AbortController === "function" ? new AbortController() : null;
  const timer = ctl ? setTimeout(() => ctl.abort(), ms || 9000) : null;
  return fetch(path, { signal: ctl ? ctl.signal : undefined })
    .then(r => r.json())
    .then(j => { if (timer) clearTimeout(timer); return j; })
    .catch(e => { if (timer) clearTimeout(timer); throw e; });
}
function loadGlobalBoard(force) {
  if (loadingGlobal) return;
  if (globalBoard && !force && Date.now() - globalBoard.at < 20000) return;
  loadingGlobal = true;
  apiGet("/api/leaderboard")
    .then(j => {
      loadingGlobal = false;
      if (!j || !j.ok) return;
      globalBoard = { rows: j.rows || [], accounts: j.accounts || 0, at: Date.now() };
      if (boardTab === "global" && overlayOpen("board")) renderBoardOverlay();
      renderTopBar();
    })
    .catch(() => { loadingGlobal = false; });
}
let loadingGlobal = false;
function renderGlobalBoard(body) {
  loadGlobalBoard(false);
  if (!globalBoard) {
    body.appendChild(el("div", "lb-empty",
      "Loading the global board from the server… every registered captain appears here, online or off."));
    return;
  }
  const rows = globalBoard.rows.slice().sort((a, b) =>
    (globalValue(b, globalSort) - globalValue(a, globalSort)) ||
    (b.bestWave - a.bestWave) || (b.worth - a.worth) || (b.kills - a.kills));
  const sorts = el("div", "lb-sorts");
  sorts.appendChild(el("span", "inv-bar-label", "Rank by"));
  GLOBAL_SORTS.forEach(([k, label]) => {
    const b = el("button", "pick" + (globalSort === k ? " on" : ""), label);
    b.onclick = () => { globalSort = k; renderBoardOverlay(); };
    sorts.appendChild(b);
  });
  body.appendChild(sorts);
  if (!rows.length) {
    body.appendChild(el("div", "lb-empty", "No registered captains yet — be the first."));
    return;
  }
  const me = (activeAccount() || {}).id;
  const head = ["#", "Captain", "Best wave", "Waves", "💎", "🪙", "Sunk", "Worth", "Ships", "Last seen"];
  const t = el("table", "lb");
  const hr = el("tr");
  head.forEach(h => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);
  rows.slice(0, 50).forEach((r, i) => {
    const tr = el("tr");
    if (r.id === me) tr.className = "new";
    tr.appendChild(el("td", null, MEDALS[i] || String(i + 1)));
    const nameCell = el("td");
    const dot = el("span", "dot" + (r.online ? " on" : ""));
    dot.title = r.online ? "online now" : "offline";
    nameCell.appendChild(dot);
    nameCell.appendChild(el("span", r.id === me ? "me" : null, r.name + (r.id === me ? " (you)" : "")));
    nameCell.appendChild(el("span", "prov", (r.provider === "google" ? "🔐" : "🔑")));
    tr.appendChild(nameCell);
    tr.appendChild(el("td", "v", String(r.bestWave)));
    tr.appendChild(el("td", null, String(r.waves || 0)));
    tr.appendChild(el("td", "gem", String(r.gems || 0)));
    tr.appendChild(el("td", "g", String(r.gold || 0)));
    tr.appendChild(el("td", null, String(r.kills || 0)));
    tr.appendChild(el("td", null, fmtNum(r.worth || 0)));
    tr.appendChild(el("td", null, (r.owned || 0) + "/" + 29));
    tr.appendChild(el("td", null, r.lastSeen ? fmtWhen(r.lastSeen) : "—"));
    t.appendChild(tr);
  });
  body.appendChild(t);
  body.appendChild(el("div", "crate-note",
    globalBoard.accounts + " registered captain(s) on this server — offline players keep their rank. " +
    "The green dot marks who is connected right now; click Rank by to re-sort."));
}""", "global board")

sub("""  if (tab.special === "worth") { renderWorthBoard(body); return; }""",
    """  if (tab.special === "global") { renderGlobalBoard(body); return; }
  if (tab.special === "worth") { renderWorthBoard(body); return; }""", "global render hook")

sub("""  document.getElementById("board-sub").textContent =
    runs.length + " recorded run" + (runs.length === 1 ? "" : "s") +
    " · 💎 " + lifetimeGems + " gems banked all-time · saved in this browser";""",
    """  document.getElementById("board-sub").textContent =
    runs.length + " run" + (runs.length === 1 ? "" : "s") + " in this browser · 💎 " + lifetimeGems +
    " gems banked here" + (globalBoard ? " · 🌍 " + globalBoard.accounts + " registered captain(s) on the server" : "");""",
    "board sub")

sub("""  if (!runs.length) {
    body.appendChild(el("div", "lb-empty", "Nothing recorded yet — play a wave and it lands here automatically."));
    return;
  }""",
    """  if (!runs.length) {
    body.appendChild(el("div", "lb-empty",
      "No runs recorded in this browser yet — play a wave and it lands here, or open the Global captains tab " +
      "to see every registered captain."));
    return;
  }""", "empty board text")

# ============================================================ manual login by either
sub("""  if (localMode === "register") {
    if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) {
      setAuthError("lo", "Username: 3-16 letters, numbers or underscores.");
      return;
    }
    if (pass.length < 6) { setAuthError("lo", "Password must be at least 6 characters."); return; }
    if (pass !== pass2) { setAuthError("lo", "Those passwords do not match."); return; }
  } else if (!name || !pass) {
    setAuthError("lo", "Enter your username and password.");
    return;
  }""",
    """  const email = val("lo-email").trim();
  if (localMode === "register") {
    if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) {
      setAuthError("lo", "Username: 3-16 letters, numbers or underscores.");
      return;
    }
    if (pass.length < 6) { setAuthError("lo", "Password must be at least 6 characters."); return; }
    if (pass !== pass2) { setAuthError("lo", "Those passwords do not match."); return; }
    if (email && !/^[^@\\s]+@[^@\\s]+\\.[^@\\s]{2,}$/.test(email)) {
      setAuthError("lo", "That does not look like an email address.");
      return;
    }
  } else if (!name || !pass) {
    setAuthError("lo", "Enter your username or email, and your password.");
    return;
  }""", "local validation")

sub("""  api("/api/account/" + (localMode === "register" ? "register" : "login"),
      { username: name, password: pass }, 20000)""",
    """  // On sign-in the one field takes either identifier; on sign-up it is the username
  // (and the optional email, so the same field can be used next time).
  api("/api/account/" + (localMode === "register" ? "register" : "login"),
      localMode === "register"
        ? { username: name, password: pass, email: email || undefined }
        : { identifier: name, username: name, password: pass }, 20000)""", "local submit body")

sub("""  const wrap = document.getElementById("lo-pass2-wrap");
  if (wrap) wrap.hidden = localMode !== "register";""",
    """  const wrap = document.getElementById("lo-pass2-wrap");
  if (wrap) wrap.hidden = localMode !== "register";
  const emailWrap = document.getElementById("lo-email-wrap");
  if (emailWrap) emailWrap.hidden = localMode !== "register";""", "email wrap toggle")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
for n in notes:
    print(" ", n)
