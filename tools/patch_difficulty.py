# Steep difficulty after wave 50, brutal after 100, and the Wave 100 colossus:
# exactly 500,000 HP with its own speed curve.
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


sub("""// Steep and unforgiving: HP compounds polynomially, hull armour climbs with the wave
// so plain damage stops being enough, and the fleet slowly outruns cheap turrets.
function enemyHpMul() {
  const w = Math.max(0, G.wave - 1);
  return (1 + Math.pow(w, 1.52) * 0.34 + w * 0.06) * DIFFICULTY[G.diff].hp;
}""",
    """// Steep and unforgiving: HP compounds polynomially, hull armour climbs with the wave
// so plain damage stops being enough, and the fleet slowly outruns cheap turrets.
// On top of that the brief asks for two deliberate walls: a real spike past wave 50 and
// a brutal one past wave 100, where only strict min-maxing survives.
function enemyHpMul() {
  const w = Math.max(0, G.wave - 1);
  let m = 1 + Math.pow(w, 1.52) * 0.34 + w * 0.06;
  if (w > 50) m *= 1 + 0.055 * (w - 50);        // from wave 51: compounding, not creeping
  if (w > 100) m *= 1 + 0.13 * (w - 100);       // from wave 101: brutal
  return m * DIFFICULTY[G.diff].hp;
}""", "hp curve")

sub("""function enemyArmorBonus() { return Math.min(0.32, 0.0068 * Math.max(0, G.wave - 1)); }""",
    """// Armour keeps climbing past wave 100 - the late fleet shrugs off un-pierced damage.
function enemyArmorBonus() {
  const w = Math.max(0, G.wave - 1);
  return Math.min(w > 100 ? 0.42 : 0.32, 0.0068 * w);
}""", "armour cap")

sub("""function bossName() {
  const k = bossIndex();
  return k === 1 ? "Leviathan" : k === 2 ? "Elder Leviathan" : k === 3 ? "Dread Leviathan"
    : "Leviathan Mk " + k;
}""",
    """function bossName() {
  if (G.wave === 100) return "The Drowned Colossus";     // its own thing entirely
  const k = bossIndex();
  return k === 1 ? "Leviathan" : k === 2 ? "Elder Leviathan" : k === 3 ? "Dread Leviathan"
    : "Leviathan Mk " + k;
}
// The Wave 100 boss is a set-piece: exactly 500,000 health, no formula, so the number on
// screen is the number in the fight.
const BOSS_100_HP = 500000;
const BOSS_100_WAVE = 100;
// Bosses move on their own curve. A routine Leviathan plods (it is a damage race); the
// Wave 100 colossus advances with purpose and gains pace as the waves climb.
function bossSpeedMul() {
  const base = 1 + 0.028 * Math.max(0, G.wave - 1);
  return G.wave === BOSS_100_WAVE ? base * 1.75 : base * 0.85;
}""", "boss name + speed")

sub("""function enemyHp(type) {
  const m = enemyHpMul();
  if (type === "boss") return Math.round(ENEMIES.boss.hp * (1 + (m - 1) * 0.55) * bossGrowth());
  return Math.round(ENEMIES[type].hp * m);
}""",
    """function enemyHp(type) {
  const m = enemyHpMul();
  if (type === "boss") {
    if (G.wave === BOSS_100_WAVE) return BOSS_100_HP;   // exactly 500,000, as briefed
    return Math.round(ENEMIES.boss.hp * (1 + (m - 1) * 0.55) * bossGrowth());
  }
  return Math.round(ENEMIES[type].hp * m);
}""", "wave 100 hp")

sub("""    hpMax: hp, hp: hp,
    speed: b.speed * enemySpeedMul(), armor: Math.min(0.72, b.armor + enemyArmorBonus()), r: b.r,""",
    """    hpMax: hp, hp: hp,
    speed: b.speed * (type === "boss" ? bossSpeedMul() : enemySpeedMul()),
    armor: Math.min(0.72, b.armor + enemyArmorBonus()),
    r: b.r * (type === "boss" && G.wave === BOSS_100_WAVE ? 1.55 : 1),""", "boss speed + size")

sub("""    toast(isBoss
    ? "🐋 " + bossName() + " incoming — " + fmtNum(enemyHp("boss")) + " HP. Boss waves land every 15."
    : "Wave " + G.wave + " incoming: " + comp.length + " ships");""",
    """    toast(isBoss
    ? "🐋 " + bossName() + " incoming — " + fmtNum(enemyHp("boss")) + " HP. Boss waves land every 15."
    : "Wave " + G.wave + " incoming: " + comp.length + " ships");""", "toast (no-op guard)")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
