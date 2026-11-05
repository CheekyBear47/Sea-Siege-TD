# Crates are bought with gems again (no free handouts), and every 15th wave is a
# single massive Leviathan with its own scaling curve.
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


# ============================================== 2. boss every 15 waves, scaled hard
sub("""  if (n % 5 === 0) list.push("boss");
  if (n % 7 === 0) list.push("boss");      // double Leviathan from wave 7 on""",
    """  // one Leviathan, every 15th wave: 15, 30, 45 ... up to the 10,000 cap
  if (n % 15 === 0) list.push("boss");""", "boss every 15")

sub("""// Bosses scale far more gently than the escort fleet, so wave-5+ bosses stay killable.
function enemyHp(type) {
  const m = enemyHpMul();
  const scaled = type === "boss" ? 1 + (m - 1) * 0.55 : m;
  return Math.round(ENEMIES[type].hp * scaled);
}""",
    """// Which Leviathan this is: the first at wave 15, the second at 30, and so on.
function bossIndex() { return Math.max(1, Math.floor(G.wave / 15)); }
function bossName() {
  const k = bossIndex();
  return k === 1 ? "Leviathan" : k === 2 ? "Elder Leviathan" : k === 3 ? "Dread Leviathan"
    : "Leviathan Mk " + k;
}
// Bosses have their own scaling curve. They ride the wave curve like the fleet, but on
// top of that each Leviathan is a step up on the last - so the one at wave 150 is a
// different animal to the one at wave 15, and the end-game ones are genuine walls.
function bossGrowth() {
  const k = bossIndex() - 1;
  return 1 + 0.22 * k + 0.06 * k * k;
}
function enemyHp(type) {
  const m = enemyHpMul();
  if (type === "boss") return Math.round(ENEMIES.boss.hp * (1 + (m - 1) * 0.55) * bossGrowth());
  return Math.round(ENEMIES[type].hp * m);
}""", "boss scaling")

sub("""  const isBoss = comp.includes("boss");
  banner((isBoss ? "⚠ Wave " + G.wave + " — Leviathan!" : "Wave " + G.wave), isBoss ? "#ff9f9f" : "#8fd6ff");
  toast("Wave " + G.wave + " incoming: " + comp.length + " ships" + (isBoss ? " (BOSS)" : ""));""",
    """  const isBoss = comp.includes("boss");
  banner(isBoss ? "⚠ Wave " + G.wave + " — " + bossName() + "!" : "Wave " + G.wave,
         isBoss ? "#ff9f9f" : "#8fd6ff");
  toast(isBoss
    ? "🐋 " + bossName() + " incoming — " + fmtNum(enemyHp("boss")) + " HP. Boss waves land every 15."
    : "Wave " + G.wave + " incoming: " + comp.length + " ships");""", "boss announce")

# bosses are three times rarer now, so each one pays properly for the kill
sub("""const GEM_REWARD_BOSS = 3;""",
    """const GEM_REWARD_BOSS = 12;   // bosses land every 15th wave, so each one pays well""",
    "boss gems")

# ============================================ 1. crates cost gems, no free handouts
sub("""// Four tiers, all won in play (boss waves and 10/25/100-wave milestones) - none is for sale.
const CRATES = {
  supply: { name: "Supply Crate", glyph: "📦", tier: 1, from: "it drops from every boss wave",
    desc: "every boss wave",
    odds: { common: 55, rare: 29, epic: 13.6, legendary: 2.0, mythic: 0.4 } },
  royal:  { name: "Royal Chest",  glyph: "🎁", tier: 2, from: "it drops every 10th wave cleared",
    desc: "every 10 waves",
    odds: { common: 30, rare: 38, epic: 24, legendary: 7.1, mythic: 0.9 } },
  admiral: { name: "Admiral's Vault", glyph: "⚜️", tier: 4, from: "it drops every 25th wave cleared",
    desc: "every 25 waves · rare or better",
    odds: { common: 0, rare: 26, epic: 46, legendary: 26.5, mythic: 1.5 } },
  reliquary: { name: "Mythic Reliquary", glyph: "🔮", tier: 5, from: "it drops every 100th wave cleared",
    desc: "every 100 waves · epic floor",
    odds: { common: 0, rare: 0, epic: 34, legendary: 62, mythic: 4 } }
};""",
    """// Four tiers, bought with gems earned in play. There are no free crates: gems come
// from clearing waves (+1) and from sinking a Leviathan (+12), and every collectible
// in the game rolls out of one of these.
const CRATES = {
  supply: { name: "Supply Crate", glyph: "📦", tier: 1, gems: 10,
    desc: "the cheap roll — commons, with a rare sighting",
    odds: { common: 55, rare: 29, epic: 13.6, legendary: 2.0, mythic: 0.4 } },
  royal:  { name: "Royal Chest",  glyph: "🎁", tier: 2, gems: 30,
    desc: "no commons at all",
    odds: { common: 30, rare: 38, epic: 24, legendary: 7.1, mythic: 0.9 } },
  admiral: { name: "Admiral's Vault", glyph: "⚜️", tier: 4, gems: 80,
    desc: "rare or better, every time",
    odds: { common: 0, rare: 26, epic: 46, legendary: 26.5, mythic: 1.5 } },
  reliquary: { name: "Mythic Reliquary", glyph: "🔮", tier: 5, gems: 220,
    desc: "epic floor — the only real mythic odds",
    odds: { common: 0, rare: 0, epic: 34, legendary: 62, mythic: 4 } }
};""", "crate prices")

sub("""  const have = G.crates[kind] || 0;
  if (have <= 0) {
    // No shop: crates are earned in play (see the milestone drops in waveCleared).
    sfx("deny");
    toast("No " + crate.name + " in the hold — " + (crate.from || "earn one in play") + ".");
    return null;
  }
  G.crates[kind] = have - 1;""",
    """  const have = G.crates[kind] || 0;
  if (have > 0) {
    G.crates[kind] = have - 1;                 // spend one already in the hold
  } else {
    // Buy it: crates are the only thing gems are for.
    const price = crate.gems || 0;
    if (G.gems < price) {
      sfx("deny");
      toast("Need " + (price - G.gems) + " more 💎 for a " + crate.name + ". Gems come from " +
            "clearing waves (+1) and sinking a boss (+" + GEM_REWARD_BOSS + ").");
      return null;
    }
    G.gems -= price;
    G.gemsSpent = (G.gemsSpent || 0) + price;
    sfx("coin");
    toast("Bought a " + crate.name + " for " + price + " 💎.");
  }""", "rollCrate buy")

# no more milestone handouts
sub("""  // Crates are milestone rewards, never purchases: boss waves, then every 10/25/100 waves.
  const earned = [];
  const grant = kind => {
    G.crates[kind] = (G.crates[kind] || 0) + 1;
    earned.push(CRATES[kind].glyph + " " + CRATES[kind].name);
  };
  if (G.waveHadBoss) grant("supply");
  if (G.wave % 10 === 0) grant("royal");
  if (G.wave % 25 === 0) grant("admiral");
  if (G.wave % 100 === 0) grant("reliquary");
  if (earned.length) {
    toast("🏆 Wave " + G.wave + " reward: " + earned.join(" · ") + " — spin it in the Crates tab.");
    banner("Crate earned!", "#ffd166");
  }""",
    """  // No free crates: the gems banked here are what buys them in the Crates tab.""",
    "remove handouts")

sub("""    const btn = el("button", "btn tiny", (G.crates[kind] || 0) > 0 ? "Spin it" : "Not in the hold");
    btn.disabled = (G.crates[kind] || 0) <= 0;""",
    """    const held = G.crates[kind] || 0;
    const btn = el("button", "btn tiny", held > 0 ? "Spin it · " + held : "Buy · " + crate.gems + " 💎");
    btn.disabled = held <= 0 && G.gems < crate.gems;""", "crate button")

sub("""    meta.appendChild(el("span", null, "in the hold: " + (G.crates[kind] || 0) + " · " + crate.from));""",
    """    meta.appendChild(el("span", null, (G.crates[kind] || 0) > 0
      ? "in the hold: " + G.crates[kind] + " · " + crate.desc
      : crate.gems + " 💎 · " + crate.desc));""", "crate meta")

sub("""    status.textContent = held ? held + " in the hold — spin one below"
      : "empty hold · boss waves and every 10/25/100 waves refill it";""",
    """    status.textContent = held ? held + " in the hold — spin one below"
      : G.gems + " 💎 banked · spend them on a crate below";""", "crates status")

sub("""  const note = el("div", "crate-note",
    "Nothing here is for sale. Supply Crates drop from every boss wave, Royal Chests every 10 waves, " +
    "Admiral's Vaults every 25 and a Mythic Reliquary every 100. Mythic turret cards stay under 1% on the " +
    "cheap two; the Vault and the Reliquary are where the odds really move. A duplicate refunds gems, so a " +
    "crate is never wasted.");""",
    """  const note = el("div", "crate-note",
    "Gems are the crate currency: +" + GEM_REWARD_WAVE + " 💎 for every wave you clear and +" +
    GEM_REWARD_BOSS + " 💎 for sinking a Leviathan (every 15th wave), so a long run funds the good crates. " +
    "Mythic turret cards stay under 1% on the cheap two; the Vault and the Reliquary are where the odds " +
    "really move. A duplicate refunds gems, so a crate is never wasted.");""", "crate note")

sub("""        <span class="hint" style="flex:1;align-self:center">Crates are never sold — win them from boss waves and wave milestones, then spin them for collectibles.</span>""",
    """        <span class="hint" style="flex:1;align-self:center">Every crate is bought with gems you earn in play — spin it to roll for a collectible.</span>""",
    "crates footer")

sub("""<div class="top-wallet" id="top-wallet" title="Gems are earned by clearing waves — a score, not a shop">""",
    """<div class="top-wallet" id="top-wallet" title="Gems are earned by clearing waves and spent on crates">""",
    "wallet tooltip")

sub("""    G.gems + " banked · 🎁 " + crates + " crate" + (crates === 1 ? "" : "s") + " to spin in the Crates tab";""",
    """    G.gems + " 💎 to spend on crates · " + crates + " crate" + (crates === 1 ? "" : "s") + " in the hold";""",
    "inv sub")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
