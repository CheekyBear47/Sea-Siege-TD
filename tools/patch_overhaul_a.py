# Pass A: single hard difficulty, endless-to-10000, slashed economy, harbour HP bar,
# inter-wave repair phase, and screen shake removed entirely.
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


# ---------------------------------------------------------------- settings HTML
sub("""    <div class="opts" style="margin-top:6px">
      <label class="switch"><input type="checkbox" id="auto" /> Auto-start waves</label>
      <label class="switch"><input type="checkbox" id="grid" checked /> Show grid</label>
      <label class="switch"><input type="checkbox" id="ranges" /> Show all ranges</label>
      <label class="switch"><input type="checkbox" id="endless" /> Endless (no lives)</label>
      <label class="switch"><input type="checkbox" id="muted" /> Mute sound</label>
      <label class="switch"><input type="checkbox" id="shake" checked /> Screen shake</label>
    </div>
    <div style="margin-top:6px">
      <select class="mini-sel" id="diff">
        <option value="relaxed">Difficulty: Relaxed — extra gold, softer fleet</option>
        <option value="normal" selected>Difficulty: Normal — balanced siege</option>
        <option value="brutal">Difficulty: Brutal — tough, fast, cheap kills</option>
      </select>
    </div>""",
    """    <div class="opts" style="margin-top:6px">
      <label class="switch"><input type="checkbox" id="auto" /> Auto-start waves</label>
      <label class="switch"><input type="checkbox" id="grid" checked /> Show grid</label>
      <label class="switch"><input type="checkbox" id="ranges" /> Show all ranges</label>
      <label class="switch"><input type="checkbox" id="muted" /> Mute sound</label>
    </div>

    <div id="repair-panel" hidden>
      <div class="sect2">🛠 Repair phase <span id="rep-live">hull 12/12</span></div>
      <button class="btn primary" id="repair-btn">Repair hull</button>
      <div class="hint" id="repair-hint"></div>
    </div>""", "settings HTML")

sub("""      <div class="stat lives"><b id="ui-lives">20</b><small>Lives</small></div>""",
    """      <div class="stat lives"><b id="ui-lives">12</b><small>Hull HP</small></div>""", "sidebar stat label")

# ------------------------------------------------------------- difficulty table
sub("""const DIFFICULTY = {
  relaxed: { hp: 0.80, speed: 0.92, gold: 1.30, startGold: 900, lives: 25, label: "Relaxed" },
  normal:  { hp: 1.00, speed: 1.00, gold: 1.00, startGold: 750, lives: 20, label: "Normal" },
  brutal:  { hp: 1.32, speed: 1.08, gold: 0.85, startGold: 600, lives: 15, label: "Brutal" }
};""",
    """// One siege, no easy mode. Early gold is deliberately scarce and the fleet scales
// steeply, so a placement or an upgrade that does nothing is a wave you lose.
const DIFFICULTY = {
  siege: { hp: 1.18, speed: 1.04, gold: 0.62, startGold: 320, lives: 12, label: "Siege" }
};
const WAVE_CAP = 10000;      // endless, but the run is capped here
const REPAIR_HP = 6;         // hull restored per repair
function repairCost() {
  // Steep, compounding, and it grows with the wave - repairing is a real sacrifice.
  return Math.round(38 * Math.pow(1.34, G.repairs || 0) * (1 + 0.05 * G.wave));
}""", "DIFFICULTY")

# --------------------------------------------------------------- scaling curves
sub("""function enemyHpMul() { return (1 + Math.pow(Math.max(0, G.wave - 1), 1.32) * 0.20) * DIFFICULTY[G.diff].hp; }
function enemySpeedMul() { return (1 + 0.028 * (G.wave - 1)) * DIFFICULTY[G.diff].speed; }
function enemyGoldMul() { return (1 + 0.05 * (G.wave - 1) + 0.10 * G.globals.gold) * DIFFICULTY[G.diff].gold; }""",
    """// Steep and unforgiving: HP compounds polynomially, hull armour climbs with the wave
// so plain damage stops being enough, and the fleet slowly outruns cheap turrets.
function enemyHpMul() {
  const w = Math.max(0, G.wave - 1);
  return (1 + Math.pow(w, 1.52) * 0.34 + w * 0.06) * DIFFICULTY[G.diff].hp;
}
function enemySpeedMul() {
  return Math.min(2.45, 1 + 0.034 * (G.wave - 1)) * DIFFICULTY[G.diff].speed;
}
function enemyArmorBonus() { return Math.min(0.32, 0.0068 * Math.max(0, G.wave - 1)); }
// Gold is scarce on purpose: kill money barely keeps up with the fleet's HP growth.
function enemyGoldMul() { return (1 + 0.022 * (G.wave - 1) + 0.04 * G.globals.gold) * DIFFICULTY[G.diff].gold; }""",
    "scaling")

sub("""    speed: b.speed * enemySpeedMul(), armor: b.armor, r: b.r,""",
    """    speed: b.speed * enemySpeedMul(), armor: Math.min(0.72, b.armor + enemyArmorBonus()), r: b.r,""",
    "armor scaling")

# ----------------------------------------------------------- state + options
sub("""  const diff = document.getElementById("diff").value;
  const d = DIFFICULTY[diff];
  G = {
    diff, gold: d.startGold, lives: d.lives, wave: 0, over: false, won: false, paused: false,""",
    """  const diff = "siege";
  const d = DIFFICULTY[diff];
  G = {
    diff, gold: d.startGold, lives: d.lives, baseMax: d.lives, wave: 0, over: false, won: false, paused: false,""",
    "newGame head")

sub("""    speed: 1, shake: 0, shakeAmp: document.getElementById("shake").checked,
    endless: document.getElementById("endless").checked,
    showGrid:""",
    """    speed: 1,
    phase: "build",                       // build | repair | battle
    showGrid:""", "newGame flags")

sub("""      G.endless = !!o.endless;
      G.shakeAmp = !!o.shake;
      Audio_.muted = !!o.muted;
      if (o.diff && DIFFICULTY[o.diff]) G.diff = o.diff;
      // mirror onto the panel controls so the UI matches the save
      const set = (id, v) => { const e = document.getElementById(id); if (e) e.checked = !!v; };
      set("auto", o.auto); set("grid", o.grid); set("ranges", o.ranges);
      set("endless", o.endless); set("shake", o.shake); set("muted", o.muted);
      const dsel = document.getElementById("diff");
      if (dsel && o.diff) dsel.value = o.diff;""",
    """      Audio_.muted = !!o.muted;
      G.diff = "siege";
      // mirror onto the panel controls so the UI matches the save
      const set = (id, v) => { const e = document.getElementById(id); if (e) e.checked = !!v; };
      set("auto", o.auto); set("grid", o.grid); set("ranges", o.ranges); set("muted", o.muted);""",
    "options restore")

sub("""    auto: val("auto"), grid: val("grid"), ranges: val("ranges"), endless: val("endless"),
    muted: val("muted"), shake: val("shake"), diff: diff ? diff.value : "normal\"""",
    """    auto: val("auto"), grid: val("grid"), ranges: val("ranges"),
    muted: val("muted"), diff: "siege\"""", "currentOptions")

# ------------------------------------------------------------------- leak / HP
sub("""  G.leaked++;
  if (G.endless) {
    sfx("leak");
    floatText(BASE[0], BASE[1] - 90, "BREACH " + G.leaked, "#ff8f9a");
    banner("Breach! (Endless — lives ignored)", "#ff8f9a");
    return;
  }
  G.lives -= cost;""",
    """  G.leaked++;
  G.lives -= cost;""", "leakEnemy")

# ------------------------------------------------------- wave payout + wave cap
sub("""  const bonus = Math.round((240 + G.wave * 90 + Math.round(G.globals.gold * 70)) * DIFFICULTY[G.diff].gold);""",
    """  // Slashed hard: a wave pays a fraction of what it used to, so upgrades are earned.
  const bonus = Math.round((58 + G.wave * 21 + Math.round(G.globals.gold * 16)) * DIFFICULTY[G.diff].gold);""",
    "wave bonus")

sub("""  if (!G.endless && G.wave >= 20 && !G.won) { endGame(true); return; }""",
    """  if (G.wave >= WAVE_CAP && !G.won) { endGame(true); return; }
  G.phase = "repair";                      // the structured inter-wave repair window""",
    "win condition + repair phase")

sub("""function startWave() {
  if (G.over || G.waveActive) return;
  G.wave++;""",
    """function startWave() {
  if (G.over || G.waveActive) return;
  G.phase = "battle";
  G.wave++;""", "startWave phase")

# -------------------------------------------------------------- wave composition
sub("""  if (n >= 3) for (let i = 0; i < 1 + Math.floor((n - 3) / 2); i++) list.push("galleon");
  if (n >= 5) for (let i = 0; i < 1 + Math.floor((n - 5) / 3); i++) list.push("sub");
  if (n % 5 === 0) list.push("boss");""",
    """  if (n >= 3) for (let i = 0; i < 1 + Math.floor((n - 3) / 1.6); i++) list.push("galleon");
  if (n >= 4) for (let i = 0; i < 1 + Math.floor((n - 4) / 2.2); i++) list.push("sub");
  if (n % 5 === 0) list.push("boss");
  if (n % 7 === 0) list.push("boss");      // double Leviathan from wave 7 on""", "wave comp")

sub("""  const gap = Math.max(0.34, 0.95 - G.wave * 0.022);""",
    """  const gap = Math.max(0.26, 0.90 - G.wave * 0.024);""", "spawn gap")

# ------------------------------------------------------------- HUD: hull bar
sub("""  // row 1 — lives as hearts
  const hearts = Math.max(0, G.lives);
  const shown = Math.min(hearts, 9);
  for (let i = 0; i < shown; i++) {
    const pulse = hearts <= 5 ? .65 + .35 * Math.sin(t * 5 + i) : 1;
    drawHeart(hx + 24 + i * 24, hy + 28, 18, "rgba(255,95,110," + pulse.toFixed(2) + ")", "rgba(255,200,210,.6)");
  }
  ctx.fillStyle = "#ffdfe4"; ctx.font = "800 17px Segoe UI, sans-serif"; ctx.textAlign = "left";
  ctx.fillText(hearts > shown ? "×" + hearts : String(hearts), hx + 30 + shown * 24, hy + 34);
  ctx.fillStyle = "rgba(255,200,210,.7)"; ctx.font = "700 10px Segoe UI, sans-serif";
  ctx.fillText(G.endless ? "LIVES · ENDLESS (IGNORED)" : "LIVES", hx + 24, hy + 48);""",
    """  // row 1 — the harbour hull bar: the base the fleet is trying to breach
  const hull = Math.max(0, G.lives);
  const hullMax = Math.max(1, G.baseMax || hull || 1);
  const frac = clamp(hull / hullMax, 0, 1);
  const low = frac <= 0.34;
  ctx.textAlign = "left";
  ctx.fillStyle = low ? "#ff9f9f" : "rgba(200,225,250,.85)";
  ctx.font = "800 10.5px Segoe UI, sans-serif";
  ctx.fillText("HARBOUR HULL", hx + 24, hy + 27);
  ctx.textAlign = "right";
  ctx.fillStyle = low ? "#ffc0c0" : "#eaf6ff";
  ctx.font = "800 15px Segoe UI, sans-serif";
  ctx.fillText(hull + " / " + hullMax, hx + hw - 16, hy + 29);
  const bx = hx + 24, bw = hw - 48, byy = hy + 36, bhh = 12;
  ctx.fillStyle = "rgba(0,0,0,.45)";
  ctx.beginPath(); ctx.roundRect(bx, byy, bw, bhh, 6); ctx.fill();
  const hg = ctx.createLinearGradient(bx, 0, bx + bw, 0);
  if (low) { hg.addColorStop(0, "#ff5f6e"); hg.addColorStop(1, "#ffb3b3"); }
  else { hg.addColorStop(0, "#35a86f"); hg.addColorStop(1, "#8ee6b0"); }
  ctx.fillStyle = hg;
  ctx.beginPath(); ctx.roundRect(bx, byy, Math.max(3, bw * frac), bhh, 6); ctx.fill();
  ctx.strokeStyle = "rgba(140,200,255,.22)"; ctx.lineWidth = 1; ctx.stroke();
  if (frac < 1) {
    ctx.fillStyle = "rgba(255,200,210,.22)";
    ctx.beginPath(); ctx.roundRect(bx + bw * frac, byy, Math.max(2, bw * (1 - frac)), bhh, 6); ctx.fill();
  }""", "HUD hull bar")

sub("""  ctx.fillText("WAVE " + G.wave + (G.endless ? "" : "/20"), hx + hw - 16, hy + 74);
  ctx.fillStyle = "rgba(160,210,255,.7)"; ctx.font = "700 10px Segoe UI, sans-serif";
  ctx.fillText(diff.label.toUpperCase() + (G.endless ? " · ENDLESS" : ""), hx + hw - 16, hy + 88);""",
    """  ctx.fillText("WAVE " + G.wave, hx + hw - 16, hy + 74);
  ctx.fillStyle = "rgba(160,210,255,.7)"; ctx.font = "700 10px Segoe UI, sans-serif";
  ctx.fillText(diff.label.toUpperCase() + " · MAX " + fmtNum(WAVE_CAP), hx + hw - 16, hy + 88);""",
    "HUD wave line")

# ------------------------------------------------------------------ shake gone
sub("""        if (G.shakeAmp) G.shake += big ? 9 : 5;
""", "", "shake trigger")
sub("""  if (G.shake > 0) G.shake = Math.max(0, G.shake - dt * 26);
""", "", "shake decay")
sub("""  const sh = G.shake > 0 ? G.shake : 0;
  ctx.save();
  if (sh) ctx.translate(rnd(-sh, sh), rnd(-sh, sh));
  ctx.clearRect(-24, -24, W + 48, H + 48);""",
    """  ctx.save();
  ctx.clearRect(-24, -24, W + 48, H + 48);""", "shake apply")

# ------------------------------------------------------------- run blob + restore
sub("""      diff: G.diff, endless: G.endless, gold: Math.floor(G.gold), lives: G.lives, wave: G.wave,""",
    """      diff: G.diff, baseMax: G.baseMax, repairs: G.repairs || 0, phase: G.phase || "build",
      gold: Math.floor(G.gold), lives: G.lives, wave: G.wave,""", "save blob run")

sub("""function applySavedRun(run) {
  G.diff = run.diff || "normal";
  G.endless = !!run.endless;
  G.gold = run.gold || 0;
  G.lives = run.lives != null ? run.lives : DIFFICULTY[G.diff].lives;""",
    """function applySavedRun(run) {
  G.diff = "siege";
  G.baseMax = run.baseMax || DIFFICULTY[G.diff].lives;
  G.repairs = run.repairs || 0;
  G.phase = run.phase || "build";
  G.gold = run.gold || 0;
  G.lives = run.lives != null ? Math.min(run.lives, G.baseMax) : G.baseMax;""", "applySavedRun")

# --------------------------------------------------------- leaderboard record/row
sub("""    at: Date.now(), diff: G.diff, endless: G.endless,""",
    """    at: Date.now(), diff: G.diff, repairs: G.repairs || 0,""", "recordRun")
sub("""    tr.appendChild(el("td", null, (DIFFICULTY[r.diff] ? DIFFICULTY[r.diff].label : r.diff) + (r.endless ? " · endless" : "")));""",
    """    tr.appendChild(el("td", null, "Siege" + (r.repairs ? " · " + r.repairs + " repairs" : "")));""",
    "leaderboard row")

# ------------------------------------------------------------------------ ui()
sub("""  const rb = document.getElementById("g-repair");
  const rcost = 900 + 600 * (G.repairs || 0);
  rb.textContent = "🛠 +2 Lives · " + rcost + "🪙";
  rb.disabled = G.gold < rcost;""",
    """  renderRepairPanel();""", "ui repair")

sub("""    "</b>" + (G.endless ? " · <b>Endless</b>" : "") +""", """""", "ui log endless")

# ------------------------------------------------------------------ handlers
sub("""document.getElementById("endless").onchange = e => {
  G.endless = e.target.checked;
  toast(G.endless ? "Endless mode: breaches no longer cost lives." : "Endless mode off — lives count again.");
};""", """document.getElementById("repair-btn").onclick = () => buyRepair();""", "endless handler")

sub("""document.getElementById("shake").onchange = e => { G.shakeAmp = e.target.checked; if (!G.shakeAmp) G.shake = 0; };
""", "", "shake handler")

sub("""document.getElementById("diff").onchange = e => {
  G.diff = e.target.value;
  const d = DIFFICULTY[G.diff];""",
    """function buyRepair() {
  if (G.over || G.waveActive) return;
  const cost = repairCost();
  if (G.lives >= G.baseMax) { sfx("deny"); toast("The harbour hull is already at full strength."); return; }
  if (G.gold < cost) { sfx("deny"); toast("Need " + Math.ceil(cost - G.gold) + " more gold to repair the hull."); return; }
  G.gold -= cost;
  G.repairs = (G.repairs || 0) + 1;
  G.lives = Math.min(G.baseMax, G.lives + REPAIR_HP);
  sfx("coin");
  banner("+" + REPAIR_HP + " hull", "#8ee6b0");
  floatText(BASE[0], BASE[1] - 70, "+" + REPAIR_HP + " hull", "#8ee6b0");
  toast("Hull repaired to " + G.lives + "/" + G.baseMax + " for " + cost + " gold. Next repair costs more.");
  queueSave(); ui();
}
function renderRepairPanel() {
  const panel = document.getElementById("repair-panel");
  if (!panel) return;
  const open = G.phase === "repair" && !G.over && !G.waveActive && G.wave > 0;
  panel.hidden = !open;
  if (!open) return;
  const cost = repairCost();
  const full = G.lives >= G.baseMax;
  const live = document.getElementById("rep-live");
  if (live) live.textContent = "hull " + G.lives + "/" + G.baseMax + " · repair #" + ((G.repairs || 0) + 1);
  const btn = document.getElementById("repair-btn");
  if (btn) {
    btn.textContent = full ? "Hull at full strength" : "Repair +" + REPAIR_HP + " HP · " + cost + " 🪙";
    btn.disabled = full || G.gold < cost;
  }
  const hint = document.getElementById("repair-hint");
  if (hint) {
    hint.textContent = full
      ? "Nothing to patch — spend the gold on guns instead."
      : (G.gold < cost
          ? "Not enough gold. This window is the only time you can repair."
          : "Every repair costs more than the last, and the price climbs with the wave. Choose.");
  }
}
""", "diff handler -> repair")

# snapshot
sub("""    fires: G.fires.length, paused: G.paused, speed: G.speed, diff: G.diff, endless: G.endless,""",
    """    fires: G.fires.length, paused: G.paused, speed: G.speed, diff: G.diff,
    baseMax: G.baseMax, phase: G.phase, repairs: G.repairs || 0,""", "snapshot")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
