# The Secret rarity (pitch black), two Secret launchers with a 1-wave/3-wave cycle,
# expanded crate tiers with pool restrictions, and a harder net-worth curve.
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


# ================================================== rarity table + worth tuning
sub("""const RARITY = {
  common:    { name: "Common",    pts: 10,    col: "#9fb4c7" },
  rare:      { name: "Rare",      pts: 50,    col: "#69b8ff" },
  epic:      { name: "Epic",      pts: 250,   col: "#c39bff" },
  legendary: { name: "Legendary", pts: 1200,  col: "#ffd166" },
  mythic:    { name: "Mythic",    pts: 10000, col: "#ff7ad9" }
};
const RARITY_ORDER = ["common", "rare", "epic", "legendary", "mythic"];""",
    """// Worth points are the ladder the leaderboard ranks on, so they are deliberately
// stingy: a full collection is a long grind, not a weekend.
// Secret sits above mythic: pitch black, two items only, the strongest things in the game.
const RARITY = {
  common:    { name: "Common",    pts: 4,     col: "#9fb4c7" },
  rare:      { name: "Rare",      pts: 18,    col: "#69b8ff" },
  epic:      { name: "Epic",      pts: 70,    col: "#c39bff" },
  legendary: { name: "Legendary", pts: 260,   col: "#ffd166" },
  mythic:    { name: "Mythic",    pts: 900,   col: "#ff7ad9" },
  secret:    { name: "Secret",    pts: 4000,  col: "#0a0a0c" }
};
const RARITY_ORDER = ["common", "rare", "epic", "legendary", "mythic", "secret"];""",
    "rarity table")

sub("""  .rarity.mythic{background:rgba(255,122,217,.2);color:#ffb3e6}""",
    """  .rarity.mythic{background:rgba(255,122,217,.2);color:#ffb3e6}
  /* Secret: pitch black, thin light edge - it should read as "you should not have this" */
  .rarity.secret{background:#050506;color:#e8e8ee;border:1px solid rgba(200,205,225,.35);
    box-shadow:0 0 0 1px rgba(0,0,0,.9) inset, 0 0 12px rgba(255,255,255,.06)}
  .rarity.secret::before{content:"◆ ";color:#cfd3e6}""", "secret rarity css")

# ================================================== the two Secret launchers
sub("""const MYTHIC_ORDER = ["trident", "kraken", "sunfire", "leviathan"];""",
    """const MYTHIC_ORDER = ["trident", "kraken", "sunfire", "leviathan"];
// The Secret tier: two crate-only launchers. They are active for ONE wave and then sit
// on cooldown for three, so a lucky drop is a burst of power rather than a permanent win.
const SECRET_ORDER = ["bear", "crontomelon"];""", "secret order")

sub("""  /* ---------- rank 7 — MYTHIC: crate drops only ---------- */""",
    """  /* ---------- SECRET (crate drops only): 1 wave on, 3 waves off ---------- */
  bear: {
    name: "Bear Launcher", glyph: "🐻", cost: 4000, rank: 8, mythic: true, r: "secret",
    kind: "Secret", dmg: 3000, rate: 2.1, range: 520, projSpeed: 300, projType: "stone",
    splash: 300, minRange: 90, color: "#e8e8ee", waveCycle: { active: 1, cooldown: 3 },
    desc: "lobs explosive bears. The best thing in the game — for one wave at a time.",
    special: { name: "Bear Barrage", text: "a bear lands with a 300-radius bang, then the launcher reloads for three waves." }
  },
  crontomelon: {
    name: "Crontomelon Launcher", glyph: "🍈", cost: 3400, rank: 8, mythic: true, r: "secret",
    kind: "Secret", dmg: 2400, rate: 2.6, range: 500, projSpeed: 280, projType: "stone",
    splash: 255, minRange: 90, color: "#dfe6d8", waveCycle: { active: 1, cooldown: 3 },
    desc: "a lighter melon launcher on the same one-on / three-off cycle.",
    special: { name: "Melon Volley", text: "less punch and a slower reload than the Bear, same strict cycle." }
  },
  /* ---------- rank 7 — MYTHIC: crate drops only ---------- */""", "secret turrets")

# the armory gets a Secret section, sealed like the mythics
sub("""  section("Mythic armory · crate drops only", MYTHIC_ORDER, "mythic-sect", "mythic", false);
}""",
    """  section("Mythic armory · crate drops only", MYTHIC_ORDER, "mythic-sect", "mythic", false);
  section("Secret armory · crate drops only", SECRET_ORDER, "mythic-sect secret-sect", "secret", false);
}""", "secret section")

sub("""function turretUnlocked(type) { return !TOWERS[type].mythic || G.cosOwn["turret:" + type] === true; }""",
    """function turretUnlocked(type) { return !TOWERS[type].mythic || G.cosOwn["turret:" + type] === true; }
// Secret launchers are charged for one wave in every four (1 active + 3 cooldown).
function towerCycle(type) {
  const b = TOWERS[type];
  return b && b.waveCycle ? b.waveCycle : null;
}
function towerCharged(t, wave) {
  const cyc = towerCycle(t.type);
  if (!cyc) return true;
  if (t.builtWave === undefined) t.builtWave = G.wave;      // legacy tower or fresh build
  const w = wave === undefined ? G.wave : wave;
  const since = w - t.builtWave;
  if (since <= 0) return true;
  return since % (cyc.active + cyc.cooldown) === 0;
}
function towerCycleText(type, t) {
  const cyc = towerCycle(type);
  if (!cyc) return "";
  if (!t) return cyc.active + " wave on · " + cyc.cooldown + " off";
  return towerCharged(t) ? "⚡ ACTIVE this wave" : "cooldown · " +
    ((cyc.active + cyc.cooldown) - ((G.wave - t.builtWave) % (cyc.active + cyc.cooldown))) + " wave(s)";
}""", "cycle helpers")

# the firing gate
sub("""  // towers
  for (const t of G.towers) {
    t.cd -= dt;
    t.recoil = Math.max(0, (t.recoil || 0) - dt * 4);
    const st = towerStats(t);""",
    """  // towers
  for (const t of G.towers) {
    // A Secret launcher only fires on its active wave; the rest of the time it sits there.
    if (!towerCharged(t)) { t.cd = Math.max(t.cd, 0.4); t.recoil = Math.max(0, (t.recoil || 0) - dt * 4); continue; }
    t.cd -= dt;
    t.recoil = Math.max(0, (t.recoil || 0) - dt * 4);
    const st = towerStats(t);""", "firing gate")

sub("""    document.getElementById("s-spec").textContent = st.spec ? b.special.name : "locked (Tier II)";""",
    """    document.getElementById("s-spec").textContent = st.spec ? b.special.name : "locked (Tier II)";
    const cycLine = document.getElementById("s-cycle");
    if (cycLine) {
      const txt = towerCycleText(t.type, t);
      cycLine.textContent = txt;
      cycLine.hidden = !txt;
      cycLine.classList.toggle("hot", !!txt && towerCharged(t));
    }""", "cycle ui")

sub("""        <button class="btn up tiny" id="up-spec">★ Special</button>""",
    """        <button class="btn up tiny" id="up-spec">★ Special</button>
        <div class="cycle-line" id="s-cycle" hidden></div>""", "cycle markup")

sub("""  .btn.danger{border-color:rgba(255,120,120,.45);color:#ffd7d7}""",
    """  .cycle-line{margin-top:6px;padding:6px 9px;border-radius:9px;font-size:10.5px;font-weight:800;
    text-align:center;color:#ffb3b3;background:rgba(60,20,20,.4);border:1px solid rgba(255,120,120,.3)}
  .cycle-line.hot{color:#bffbdc;background:rgba(20,60,40,.45);border-color:rgba(87,224,138,.4)}
  .btn.danger{border-color:rgba(255,120,120,.45);color:#ffd7d7}""", "cycle css")

# stat line mentions the cycle
sub("""  if (b.pierceBase) bits.push("pierces " + b.pierceBase);
  return bits.join(" · ") + " — " + b.special.name;""",
    """  if (b.pierceBase) bits.push("pierces " + b.pierceBase);
  if (b.waveCycle) bits.push(b.waveCycle.active + " wave on / " + b.waveCycle.cooldown + " off");
  return bits.join(" · ") + " — " + b.special.name;""", "stat line cycle")

# ================================================== crates: more tiers, restrictions
sub("""  reliquary: { name: "Mythic Reliquary", glyph: "🔮", tier: 5, gems: 220,
    desc: "epic floor — the only real mythic odds",
    odds: { common: 0, rare: 0, epic: 34, legendary: 62, mythic: 4 } }
};""",
    """  reliquary: { name: "Mythic Reliquary", glyph: "🔮", tier: 5, gems: 220,
    desc: "epic floor · the only real mythic odds",
    odds: { common: 0, rare: 0, epic: 34, legendary: 62, mythic: 3.6, secret: 0.4 } },
  relic:  { name: "Relic Coffer", glyph: "🗃️", tier: 3, gems: 45,
    desc: "rare floor · a taste of legendary, nothing above it",
    odds: { common: 0, rare: 62, epic: 31, legendary: 7, mythic: 0, secret: 0 } },
  void:   { name: "Void Cache", glyph: "⬛", tier: 6, gems: 600,
    desc: "the only crate with real Secret odds",
    odds: { common: 0, rare: 0, epic: 22, legendary: 62, mythic: 14.5, secret: 1.5 } }
};""", "crate tiers")

sub("""const CRATE_ORDER = ["supply", "royal", "admiral", "reliquary"];
const CRATE_REFUND = { common: 1, rare: 2, epic: 3, legendary: 6, mythic: 0 };""",
    """// The cheap crates are hard-locked out of the top two rarities (odds of 0), so the only
// route to a Mythic or a Secret is the expensive end of the shelf.
const CRATE_ORDER = ["supply", "royal", "relic", "admiral", "reliquary", "void"];
const CRATE_REFUND = { common: 1, rare: 2, epic: 3, legendary: 6, mythic: 0, secret: 25 };""",
    "crate order")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
