# Boss schedule (mini / medium / stepped / major), a swarm nerf, Flak Cutter damage 0,
# and a Max All upgrade button.
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


# ============================================================ 1. boss schedule
sub("""  // one Leviathan, every 15th wave: 15, 30, 45 ... up to the 10,000 cap - and always on
  // wave 100, which is the briefed set-piece (100 is not a multiple of 15).
  if (n % 15 === 0 || n === BOSS_100_WAVE) list.push("boss");""",
    """  // The Leviathan schedule: a mini-boss every 5 waves, a medium at 15, a stepped-up one
  // every 25, and the two majors at 50 and 100.
  if (bossTier(n)) list.push("boss");""", "waveComp boss")

sub("""// Which Leviathan this is: the first at wave 15, the second at 30, and so on.
function bossIndex() { return Math.max(1, Math.floor(G.wave / 15)); }
function bossName() {
  if (G.wave === 100) return "The Drowned Colossus";     // its own thing entirely
  const k = bossIndex();
  return k === 1 ? "Leviathan" : k === 2 ? "Elder Leviathan" : k === 3 ? "Dread Leviathan"
    : "Leviathan Mk " + k;
}""",
    """// The boss ladder. Type 0 means an ordinary wave:
//   1  mini-boss    every 5 waves
//   2  medium       wave 15
//   3  stepped-up   every 25 waves (25, 75, 125 ...)
//   4  major        waves 50 and 100
function bossTier(n) {
  if (n === BOSS_100_WAVE || n === 50) return 4;
  if (n % 25 === 0) return 3;
  if (n === 15) return 2;
  if (n % 5 === 0) return 1;
  return 0;
}
const BOSS_TIERS = {
  1: { name: "Raider Leviathan", hp: 0.30, r: 0.72, gems: 6 },
  2: { name: "Leviathan",        hp: 1.00, r: 1.00, gems: 12 },
  3: { name: "Elder Leviathan",  hp: 2.40, r: 1.20, gems: 22 },
  4: { name: "Dread Leviathan",  hp: 4.00, r: 1.55, gems: 45 }
};
function bossTierNow() { return bossTier(G.wave); }
function bossName(n) {
  const w = n === undefined ? G.wave : n;
  if (w === BOSS_100_WAVE) return "The Drowned Colossus";   // its own thing entirely
  return (BOSS_TIERS[bossTier(w)] || BOSS_TIERS[1]).name;
}""", "boss tiers")

sub("""// Bosses have their own scaling curve. They ride the wave curve like the fleet, but on
// top of that each Leviathan is a step up on the last - so the one at wave 150 is a
// different animal to the one at wave 15, and the end-game ones are genuine walls.
function bossGrowth() {
  const k = bossIndex() - 1;
  return 1 + 0.22 * k + 0.06 * k * k;
}
function enemyHp(type) {
  const m = enemyHpMul();
  if (type === "boss") {
    if (G.wave === BOSS_100_WAVE) return BOSS_100_HP;   // exactly 500,000, as briefed
    return Math.round(ENEMIES.boss.hp * (1 + (m - 1) * 0.55) * bossGrowth());
  }
  return Math.round(ENEMIES[type].hp * m);
}""",
    """// Bosses ride the wave curve like the fleet, then their tier multiplies on top, and
// the stepped-up tier climbs again every 25 waves - so a Levy at 125 is a different
// animal to the one at 25.
function bossGrowth() {
  const k = Math.max(1, Math.floor(G.wave / 25)) - 1;
  return 1 + 0.18 * k + 0.05 * k * k;
}
function enemyHp(type) {
  const m = enemyHpMul();
  if (type === "boss") {
    if (G.wave === BOSS_100_WAVE) return BOSS_100_HP;   // exactly 500,000, as briefed
    const tier = BOSS_TIERS[bossTierNow()] || BOSS_TIERS[1];
    return Math.round(ENEMIES.boss.hp * (1 + (m - 1) * 0.55) * bossGrowth() * tier.hp);
  }
  return Math.round(ENEMIES[type].hp * m);
}""", "boss hp by tier")

sub("""    r: b.r * (type === "boss" && G.wave === BOSS_100_WAVE ? 1.55 : 1),""",
    """    r: b.r * (type === "boss"
      ? (G.wave === BOSS_100_WAVE ? 1.55 : (BOSS_TIERS[bossTierNow()] || BOSS_TIERS[1]).r)
      : 1),""", "boss radius")

sub("""function bossSpeedMul() {
  const base = Math.min(1.9, 1 + 0.03 * Math.max(0, G.wave - 1));
  return G.wave === BOSS_100_WAVE ? base * 1.15 : base * 0.8;
}""",
    """function bossSpeedMul() {
  const t = bossTierNow();
  const base = Math.min(1.9, 1 + 0.03 * Math.max(0, G.wave - 1));
  if (G.wave === BOSS_100_WAVE) return base * 1.15;      // the colossus moves with purpose
  if (t === 4) return base * 1.0;                        // majors are not slow
  if (t === 1) return base * 0.72;                       // mini-bosses are nimble
  return base * 0.8;
}""", "boss speed by tier")

sub("""const GEM_REWARD_BOSS = 12;   // bosses land every 15th wave, so each one pays well""",
    """// Bosses pay by tier now: a raider is pocket change, a major milestone is a payday.
const GEM_REWARD_BOSS = 12;   // fallback when there is no boss tier (kept for old saves)""",
    "boss gem note")

sub("""  const gemGain = GEM_REWARD_WAVE + (G.waveHadBoss ? GEM_REWARD_BOSS : 0);""",
    """  const bossPaid = G.waveHadBoss
    ? ((BOSS_TIERS[bossTierNow()] || {}).gems || GEM_REWARD_BOSS) : 0;
  const gemGain = GEM_REWARD_WAVE + bossPaid;""", "boss gems by tier")

sub("""  toast(isBoss
    ? "🐋 " + bossName() + " incoming — " + fmtNum(enemyHp("boss")) + " HP. Boss waves land every 15."
    : "Wave " + G.wave + " incoming: " + comp.length + " ships");""",
    """  toast(isBoss
    ? "🐋 " + bossName() + " incoming — " + fmtNum(enemyHp("boss")) + " HP" +
      (bossTierNow() >= 4 ? " · MAJOR BOSS" : " · boss tier " + bossTierNow()) + "."
    : "Wave " + G.wave + " incoming: " + comp.length + " ships");""", "boss toast")

# ============================================================ 1b. swarm nerf
sub("""function enemyHpMul() {
  const w = Math.max(0, G.wave - 1);
  let m = 1 + Math.pow(w, 1.52) * 0.34 + w * 0.06;
  if (w > 50) m *= 1 + 0.055 * (w - 50);        // from wave 51: compounding, not creeping
  if (w > 100) m *= 1 + 0.13 * (w - 100);       // from wave 101: brutal
  return m * DIFFICULTY[G.diff].hp;
}""",
    """function enemyHpMul() {
  const w = Math.max(0, G.wave - 1);
  let m = 1 + Math.pow(w, 1.52) * 0.30 + w * 0.055;   // eased off: the swarm was brutal
  if (w > 50) m *= 1 + 0.045 * (w - 50);        // from wave 51: compounding, not creeping
  if (w > 100) m *= 1 + 0.11 * (w - 100);       // from wave 101: brutal
  return m * DIFFICULTY[G.diff].hp;
}""", "hp nerf")

sub("""  const skiffs = 5 + Math.round(n * 1.35);""",
    """  const skiffs = 4 + Math.round(n * 1.18);      // fewer hulls per wave: fairer, not easier""",
    "swarm nerf")

# ============================================================ 2. Flak Cutter = 0
sub("""  flakcutter: {
    name: "Flak Cutter", glyph: "🔫", cost: 160, rank: 1, kind: "Rapid",
    dmg: 11, rate: 1.35, range: 150, color: "#bfe3ff", desc: "cheap, quick, relentless",
    special: { name: "Flak Burst", text: "a snub fast-firer - more shots per coin than anything else." }
  },""",
    """  // Damage is 0 as requested. It still tracks and fires (so it works as a utility /
    // decoy and can be upgraded like anything else) but it destroys nothing on its own.
  flakcutter: {
    name: "Flak Cutter", glyph: "🔫", cost: 160, rank: 1, kind: "Rapid",
    dmg: 0, rate: 1.35, range: 150, color: "#bfe3ff", desc: "a fast hull that deals no damage",
    special: { name: "Flak Burst", text: "fires fast and often, but its shots carry no damage." }
  },""", "flak damage 0")

# ============================================================ 3. Max All button
sub("""      <button class="btn gold" id="up-tier">⬆ Upgrade Tier</button>""",
    """      <button class="btn gold" id="up-tier">⬆ Upgrade Tier</button>
      <button class="btn gold" id="up-max" title="Buy every upgrade you can afford, right now">⚡ Max All</button>""",
    "max all markup")

sub("""document.getElementById("up-tier").onclick = () => upgradeTower("tier");""",
    """document.getElementById("up-tier").onclick = () => upgradeTower("tier");
// Max All: buy everything affordable in one tap. upgradeTower() already refuses what
// cannot be paid for, so this loops until nothing more can be bought (and is bounded so
// a future upgrade type cannot spin forever).
function maxAllTower() {
  const t = G.sel;
  if (!t) return;
  const kinds = ["dmg", "rate", "range", "spec", "tier"];
  let spent = 0, bought = 0, guard = 80;
  while (guard-- > 0) {
    const before = Math.round(G.gold);
    kinds.forEach(k => upgradeTower(k));
    const after = Math.round(G.gold);
    if (after >= before) break;             // nothing was affordable this pass
    spent += before - after;
    bought++;
  }
  if (!bought) {
    sfx("deny");
    toast("Nothing affordable left on " + TOWERS[t.type].name + " — earn more gold.");
    return;
  }
  sfx("upgrade");
  banner("Maxed all it could", TOWERS[t.type].color);
  toast("⚡ Max All: spent " + fmtNum(spent) + " gold on " + TOWERS[t.type].name +
        " · " + fmtNum(G.gold) + " left.");
  ui();
}
document.getElementById("up-max").onclick = maxAllTower;""", "max all wiring")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
