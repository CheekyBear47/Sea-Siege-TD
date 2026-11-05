# Mythics: dearer, weaker, and on a 2-on / 2-off wave cycle. Bosses keep pace with the
# fleet late game. Mythic and Secret become genuinely rare pulls.
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


# ==================================================== 1. mythic cost / power / cycle
sub("""  trident: {
    name: "Poseidon's Trident Battery", glyph: "🔱", cost: 2000, rank: 7, mythic: true, kind: "Mythic",
    dmg: 130, rate: 0.42, range: 340, projSpeed: 1050, projType: "bolt", volley: 3,
    pierceBase: 3, color: "#6fe3ff", desc: "Triple tidal bolts pierce whole fleets",""",
    """  trident: {
    name: "Poseidon's Trident Battery", glyph: "🔱", cost: 7000, rank: 7, mythic: true, kind: "Mythic",
    dmg: 78, rate: 0.42, range: 340, projSpeed: 1050, projType: "bolt", volley: 3,
    pierceBase: 3, waveCycle: { active: 2, cooldown: 2 },
    color: "#6fe3ff", desc: "Triple tidal bolts pierce whole fleets", """, "trident")

sub("""  kraken: {
    name: "Kraken Abyss Mortar", glyph: "🐙", cost: 2400, rank: 7, mythic: true, kind: "Mythic",
    dmg: 320, rate: 2.30, range: 470, projSpeed: 240, projType: "stone",
    splash: 210, minRange: 130, color: "#9d7bff", desc: "Abyssal shell that drags ships under",""",
    """  kraken: {
    name: "Kraken Abyss Mortar", glyph: "🐙", cost: 8000, rank: 7, mythic: true, kind: "Mythic",
    dmg: 195, rate: 2.55, range: 470, projSpeed: 240, projType: "stone",
    splash: 175, minRange: 130, waveCycle: { active: 2, cooldown: 2 },
    color: "#9d7bff", desc: "Abyssal shell that drags ships under",""", "kraken")

sub("""  sunfire: {
    name: "Sunfire Ray Engine", glyph: "☀️", cost: 2900, rank: 7, mythic: true, kind: "Mythic",
    dmg: 255, rate: 0.75, range: 400, projType: "ray", burnOn: true,""",
    """  sunfire: {
    name: "Sunfire Ray Engine", glyph: "☀️", cost: 9500, rank: 7, mythic: true, kind: "Mythic",
    dmg: 155, rate: 0.75, range: 400, projType: "ray", burnOn: true,
    waveCycle: { active: 2, cooldown: 2 },""", "sunfire")

sub("""  leviathan: {
    name: "Leviathan Chains", glyph: "⛓️", cost: 3500, rank: 7, mythic: true, kind: "Mythic",
    dmg: 95, rate: 0.85, range: 268, projType: "tesla",
    chain: 5, slow: 0.60, slowDur: 3.0, reveal: 300, color: "#7dffc4", desc: "Chains drag six ships at once",""",
    """  leviathan: {
    name: "Leviathan Chains", glyph: "⛓️", cost: 11000, rank: 7, mythic: true, kind: "Mythic",
    dmg: 58, rate: 0.85, range: 268, projType: "tesla",
    chain: 4, slow: 0.48, slowDur: 3.0, reveal: 300, waveCycle: { active: 2, cooldown: 2 },
    color: "#7dffc4", desc: "Chains drag four ships at once",""", "leviathan")

sub("""// Mythic turret cards are collectibles too: worth 10,000 pts, tradable, and the only
// way to unlock the turret itself. They come out of crates and nowhere else.""",
    """// Mythic turret cards are collectibles too: the only way to unlock the turret itself,
// and they come out of crates and nowhere else. The turrets are expensive to build and
// run on a 2-waves-on / 2-waves-off cycle, so they are strong utility pieces rather than
// a permanent win button (the Secret tier is stricter still: 1 on, 3 off).""", "mythic note")

# ==================================================== 2. bosses keep pace late game
sub("""function bossGrowth() {
  const k = Math.max(1, Math.floor(G.wave / 25)) - 1;
  return 1 + 0.18 * k + 0.05 * k * k;
}""",
    """// How many 25-wave steps in we are: the ladder every boss tier climbs.
function bossStep() { return Math.max(1, Math.floor(G.wave / 25)) - 1; }
function bossGrowth() {
  const k = bossStep();
  return 1 + 0.18 * k + 0.05 * k * k;
}""", "bossStep")

sub("""function enemyHp(type) {
  const m = enemyHpMul();
  if (type === "boss") {
    if (G.wave === BOSS_100_WAVE) return BOSS_100_HP;   // exactly 500,000, as briefed
    const tier = BOSS_TIERS[bossTierNow()] || BOSS_TIERS[1];
    return Math.round(ENEMIES.boss.hp * (1 + (m - 1) * 0.55) * bossGrowth() * tier.hp);
  }
  return Math.round(ENEMIES[type].hp * m);
}""",
    """function enemyHp(type) {
  const m = enemyHpMul();
  if (type === "boss") {
    if (G.wave === BOSS_100_WAVE) return BOSS_100_HP;   // exactly 500,000, as briefed
    const tier = BOSS_TIERS[bossTierNow()] || BOSS_TIERS[1];
    // Two changes keep bosses a threat late: they ride the fleet curve harder (0.70
    // instead of 0.55), and every tier also climbs with each 25-wave step - otherwise a
    // late mini-boss or Elder falls behind a fleet that is growing polynomially, which
    // is exactly why the Leviathans felt toothless in the deep waves.
    const stepBonus = 1 + 0.10 * bossStep();
    return Math.round(ENEMIES.boss.hp * (1 + (m - 1) * 0.70) * bossGrowth() * tier.hp * stepBonus);
  }
  return Math.round(ENEMIES[type].hp * m);
}""", "boss hp pace")

sub("""  1: { name: "Raider Leviathan", hp: 0.30, r: 0.72, gems: 6 },
  2: { name: "Leviathan",        hp: 1.00, r: 1.00, gems: 12 },
  3: { name: "Elder Leviathan",  hp: 2.40, r: 1.20, gems: 22 },
  4: { name: "Dread Leviathan",  hp: 4.00, r: 1.55, gems: 45 }""",
    """  1: { name: "Raider Leviathan", hp: 0.34, r: 0.72, gems: 6 },
  2: { name: "Leviathan",        hp: 1.15, r: 1.00, gems: 12 },
  3: { name: "Elder Leviathan",  hp: 2.80, r: 1.20, gems: 22 },
  4: { name: "Dread Leviathan",  hp: 4.60, r: 1.55, gems: 45 }""", "boss tier bump")

# ==================================================== 3. rarer mythic & secret pulls
sub("""  supply: { name: "Supply Crate", glyph: "📦", tier: 1, gems: 10,
    desc: "the cheap roll — commons, with a rare sighting",
    odds: { common: 55, rare: 29, epic: 13.6, legendary: 2.0, mythic: 0.4 } },
  royal:  { name: "Royal Chest",  glyph: "🎁", tier: 2, gems: 30,
    desc: "no commons at all",
    odds: { common: 30, rare: 38, epic: 24, legendary: 7.1, mythic: 0.9 } },
  admiral: { name: "Admiral's Vault", glyph: "⚜️", tier: 4, gems: 80,
    desc: "rare or better, every time",
    odds: { common: 0, rare: 26, epic: 46, legendary: 26.5, mythic: 1.5 } },
  reliquary: { name: "Mythic Reliquary", glyph: "🔮", tier: 5, gems: 220,
    desc: "epic floor · the only real mythic odds",
    odds: { common: 0, rare: 0, epic: 34, legendary: 62, mythic: 3.6, secret: 0.4 } },
  relic:  { name: "Relic Coffer", glyph: "🗃️", tier: 3, gems: 45,
    desc: "rare floor · a taste of legendary, nothing above it",
    odds: { common: 0, rare: 62, epic: 31, legendary: 7, mythic: 0, secret: 0 } },
  void:   { name: "Void Cache", glyph: "⬛", tier: 6, gems: 600,
    desc: "the only crate with real Secret odds",
    odds: { common: 0, rare: 0, epic: 22, legendary: 62, mythic: 14.5, secret: 1.5 } }
};""",
    """  supply: { name: "Supply Crate", glyph: "📦", tier: 1, gems: 10,
    desc: "the cheap roll — commons, with a rare sighting",
    odds: { common: 55, rare: 29, epic: 13.5, legendary: 2.25, mythic: 0.25 } },
  royal:  { name: "Royal Chest",  glyph: "🎁", tier: 2, gems: 30,
    desc: "no commons at all",
    odds: { common: 30, rare: 38, epic: 24, legendary: 7.4, mythic: 0.6 } },
  admiral: { name: "Admiral's Vault", glyph: "⚜️", tier: 4, gems: 80,
    desc: "rare or better, every time",
    odds: { common: 0, rare: 26, epic: 46.4, legendary: 27.0, mythic: 0.6 } },
  reliquary: { name: "Mythic Reliquary", glyph: "🔮", tier: 5, gems: 220,
    desc: "epic floor · the best mythic odds on the cheap end",
    odds: { common: 0, rare: 0, epic: 34, legendary: 64.45, mythic: 1.5, secret: 0.05 } },
  relic:  { name: "Relic Coffer", glyph: "🗃️", tier: 3, gems: 45,
    desc: "rare floor · a faint mythic chance, nothing above it",
    odds: { common: 0, rare: 62, epic: 31, legendary: 6.9, mythic: 0.1, secret: 0 } },
  void:   { name: "Void Cache", glyph: "⬛", tier: 6, gems: 600,
    desc: "the only crate with meaningful Secret odds — still about 1 in 200",
    odds: { common: 0, rare: 0, epic: 22, legendary: 73.9, mythic: 3.6, secret: 0.5 } }
};""", "crate odds")

sub("""const CRATE_REFUND = { common: 1, rare: 2, epic: 3, legendary: 6, mythic: 0, secret: 25 };""",
    """// Duplicates of the top two tiers pay a real consolation now that they are this rare
// (mythic seemed to refund nothing at all before).
const CRATE_REFUND = { common: 1, rare: 2, epic: 3, legendary: 6, mythic: 60, secret: 150 };""",
    "crate refund")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
