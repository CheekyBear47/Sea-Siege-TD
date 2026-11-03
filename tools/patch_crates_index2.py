# Dedicated Crates tab, no gem cash-shop anywhere, and the inventory reframed as a
# pure collection index. Crates now come from boss waves + wave milestones.
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


# ================================================================ 1. Crates tab
sub("""    <button class="top-btn" id="top-board">🏆 <span>Leaderboard</span></button>
    <button class="top-btn" id="top-inv">🎒 <span>Inventory &amp; Skins</span></button>""",
    """    <button class="top-btn" id="top-board">🏆 <span>Leaderboard</span></button>
    <button class="top-btn" id="top-crates">🎁 <span>Crates</span></button>
    <button class="top-btn" id="top-inv">📖 <span>Collection index</span></button>""", "top bar buttons")

sub("""<div class="top-wallet" id="top-wallet" title="Gems are earned by clearing waves and spent on cosmetics">""",
    """<div class="top-wallet" id="top-wallet" title="Gems are earned by clearing waves — a score, not a shop">""",
    "wallet tooltip")

sub("""    <div id="inv"><div class="box">
      <div class="board-head">
        <h2>Collection</h2>""",
    """    <div id="crates"><div class="box">
      <div class="board-head">
        <div class="pf-head">
          <h2>🎁 Crates</h2>
          <div class="pf-id" id="crates-status">milestone rewards — spin them here</div>
        </div>
        <button class="btn tiny" id="crates-x" style="width:auto;padding:5px 10px">✕ Close</button>
      </div>
      <div id="crates-body"></div>
      <div class="board-foot">
        <span class="hint" style="flex:1;align-self:center">Crates are never sold — win them from boss waves and wave milestones, then spin them for collectibles.</span>
        <button class="btn primary" id="crates-close">Done</button>
      </div>
    </div></div>
    <div id="inv"><div class="box">
      <div class="board-head">
        <h2>Collection index</h2>""", "crates overlay")

sub("""        <span class="hint" style="flex:1;align-self:center">Gems come only from clearing waves — cosmetics never change how the battle plays.</span>""",
    """        <span class="hint" style="flex:1;align-self:center">An index of what you have found: every item is earned in play and nothing here changes how the battle plays.</span>""",
    "inv footer hint")

sub("""const OVERLAY_IDS = ["board", "inv", "trade", "profile"];""",
    """const OVERLAY_IDS = ["board", "crates", "inv", "trade", "profile"];""", "OVERLAY_IDS")

sub("""  [["top-board", "board"], ["top-inv", "inv"], ["top-trade", "trade"], ["top-profile", "profile"]]""",
    """  [["top-board", "board"], ["top-crates", "crates"], ["top-inv", "inv"], ["top-trade", "trade"],
   ["top-profile", "profile"]]""", "syncTopTabs")

sub("""  if (id === "board") showBoard(!open);
  else if (id === "inv") showInv(!open);""",
    """  if (id === "board") showBoard(!open);
  else if (id === "crates") showCrates(!open);
  else if (id === "inv") showInv(!open);""", "toggleOverlay")

sub("""document.getElementById("top-trade").onclick = () => toggleOverlay("trade");""",
    """document.getElementById("top-trade").onclick = () => toggleOverlay("trade");
document.getElementById("top-crates").onclick = () => toggleOverlay("crates");
document.getElementById("crates-x").onclick = () => showCrates(false);
document.getElementById("crates-close").onclick = () => showCrates(false);""", "crates wiring")

# ============================================ 2. no gems as a cash shop anywhere
sub("""  supply: { name: "Supply Crate", glyph: "📦", gems: 10, tier: 1,
    desc: "10 💎, or free from every boss wave",""",
    """  supply: { name: "Supply Crate", glyph: "📦", tier: 1, from: "it drops from every boss wave",
    desc: "every boss wave",""", "crate supply")

sub("""  royal:  { name: "Royal Chest",  glyph: "🎁", gems: 30, tier: 2, desc: "no commons at all",""",
    """  royal:  { name: "Royal Chest",  glyph: "🎁", tier: 2, from: "it drops every 10th wave cleared",
    desc: "every 10 waves",""", "crate royal")

sub("""  admiral: { name: "Admiral's Vault", glyph: "⚜️", gems: 80, tier: 4, desc: "rare or better, every time",""",
    """  admiral: { name: "Admiral's Vault", glyph: "⚜️", tier: 4, from: "it drops every 25th wave cleared",
    desc: "every 25 waves · rare or better",""", "crate admiral")

sub("""  reliquary: { name: "Mythic Reliquary", glyph: "🔮", gems: 220, tier: 5, desc: "epic floor · the only real mythic odds",""",
    """  reliquary: { name: "Mythic Reliquary", glyph: "🔮", tier: 5, from: "it drops every 100th wave cleared",
    desc: "every 100 waves · epic floor",""", "crate reliquary")

sub("""// Both crate types roll a rarity first""", """// Crates are never sold - every one of them is won in play.
// A crate rolls a rarity first""", "crate comment")

sub("""  const have = G.crates[kind] || 0;
  if (have <= 0) {
    if (!crate.gems) {
      sfx("deny");
      toast("No " + crate.name + " in the hold — clear a boss wave to earn one.");
      return null;
    }
    if (G.gems < crate.gems) {
      sfx("deny");
      toast("Need " + (crate.gems - G.gems) + " more 💎 for a " + crate.name + ".");
      return null;
    }
    G.gems -= crate.gems;
    sfx("coin");
    toast("Bought a " + crate.name + " for " + crate.gems + " 💎.");
  } else {
    G.crates[kind] = have - 1;
  }""",
    """  const have = G.crates[kind] || 0;
  if (have <= 0) {
    // No shop: crates are earned in play (see the milestone drops in waveCleared).
    sfx("deny");
    toast("No " + crate.name + " in the hold — " + (crate.from || "earn one in play") + ".");
    return null;
  }
  G.crates[kind] = have - 1;""", "rollCrate purchase")

sub("""    const btn = el("button", "btn tiny", (G.crates[kind] || 0) > 0 ? "Open" : (crate.gems ? "Buy · " + crate.gems + " 💎" : "None"));
    btn.disabled = (G.crates[kind] || 0) <= 0 && (!crate.gems || G.gems < crate.gems);""",
    """    const btn = el("button", "btn tiny", (G.crates[kind] || 0) > 0 ? "Spin it" : "Not in the hold");
    btn.disabled = (G.crates[kind] || 0) <= 0;""", "crate button")

sub("""    meta.appendChild(el("span", null, "in the hold: " + (G.crates[kind] || 0) + " · " + crate.desc));""",
    """    meta.appendChild(el("span", null, "in the hold: " + (G.crates[kind] || 0) + " · " + crate.from));""",
    "crate meta line")

sub("""    worths.appendChild(el("span", "rarity " + rk, RARITY[rk].name + " = " + fmtNum(RARITY[rk].pts) +
      " pts" + (rk === "mythic" ? " (turret card)" : " · " + RARITY[rk].gems + "💎")));""",
    """    worths.appendChild(el("span", "rarity " + rk, RARITY[rk].name + " = " + fmtNum(RARITY[rk].pts) +
      " pts" + (rk === "mythic" ? " (turret card)" : "")));""", "crate legend")

sub("""  const note = el("div", "crate-note",
    "Mythic turret cards stay under 1% on the Supply Crate and Royal Chest; the Admiral's Vault and the " +
    "Mythic Reliquary are the only places the odds really move. Supply Crates still drop from boss waves, " +
    "and duplicates refund gems, so a crate is never wasted.");""",
    """  const note = el("div", "crate-note",
    "Nothing here is for sale. Supply Crates drop from every boss wave, Royal Chests every 10 waves, " +
    "Admiral's Vaults every 25 and a Mythic Reliquary every 100. Mythic turret cards stay under 1% on the " +
    "cheap two; the Vault and the Reliquary are where the odds really move. A duplicate refunds gems, so a " +
    "crate is never wasted.");""", "crate note")

sub("""function buyOrEquip(cat, id) {
  const info = COSMETIC_CATS.find(c => c.id === cat);
  const item = info.items[id];
  if (item.crateOnly) {
    sfx("deny");
    toast(item.name + " only drops from a crate — " +
      (G.crates.supply > 0 ? "open your Supply Crate 📦" : "clear a boss wave for a Supply Crate 📦") +
      " or buy a Royal Chest 🎁 with gems.");
    return;
  }
  if (info.noEquip) return;
  if (!unlocked(cat, id)) {
    const price = cosCost(item);
    if (G.gems < price) {
      sfx("deny");
      toast("Need " + (price - G.gems) + " more 💎 gems for " + item.name + " (" + rarityOf(item).name +
            ", " + price + " 💎) — clear more waves or open a crate.");
      renderInventory();
      return;
    }
    G.gems -= price;
    G.cosOwn[cosId(cat, id)] = true;
    sfx("gem");
    banner(item.name + " unlocked!", rarityOf(item).col);
    toast("Unlocked " + rarityOf(item).name + " " + item.name + " for " + price + " 💎 — equipped.");
    equipCosmetic(cat, id);
    return;
  }
  equipCosmetic(cat, id);
}""",
    """// Nothing is purchasable any more: this only equips what the collection already holds.
function equipOwned(cat, id) {
  const info = COSMETIC_CATS.find(c => c.id === cat);
  const item = info.items[id];
  if (!info || info.noEquip) return;
  if (!unlocked(cat, id)) {
    sfx("deny");
    toast(item.name + " is a " + rarityOf(item).name + " collectible you have not found yet — it rolls " +
          "out of a crate, and crates come from boss waves and wave milestones.");
    return;
  }
  equipCosmetic(cat, id);
}""", "buyOrEquip")

sub("""  // bulk unlock: spend gems on everything affordable, most valuable first
  if (!cat.noEquip) {
    const affordable = Object.entries(cat.items)
      .filter(([id, it]) => !unlocked(cat.id, id) && !it.crateOnly && cosCost(it) <= G.gems)
      .sort((a, b) => itemWorth(b[1]) - itemWorth(a[1]));
    const bulk = el("button", "pick on", affordable.length ? "Unlock " + affordable.length + " affordable" : "Nothing affordable");
    bulk.disabled = !affordable.length;
    bulk.onclick = () => {
      let spent = 0;
      affordable.forEach(([id, it]) => {
        if (G.gems < cosCost(it)) return;
        G.gems -= cosCost(it); spent += cosCost(it);
        G.cosOwn[cosId(cat.id, id)] = true;
      });
      sfx("gem");
      toast("Unlocked " + affordable.length + " item(s) for " + spent + " 💎 — " + cat.label.replace(/^\\S+\\s/, ""));
      queueSave(); ui(); renderInventory();
    };
    info.appendChild(bulk);
  }
  bar.appendChild(info);""", """  bar.appendChild(info);""", "bulk unlock")

sub("""    meta.appendChild(el("span", "cos-cost", own ? (equipped ? "Equipped ✓" : "Owned")
      : (item.crateOnly ? "📦 crate drop only" : "💎 " + cosCost(item) + " gems")));
    card.appendChild(meta);
    let btn;
    if (item.crateOnly) {
      btn = el("button", "btn tiny", own ? "Owned" : "Crate only");
      btn.disabled = true;
    } else if (cat.noEquip) {
      btn = el("button", "btn tiny", own ? "Owned" : "Locked");
      btn.disabled = true;
    } else {
      btn = el("button", "btn tiny" + (equipped ? " on" : ""), equipped ? "Equipped" : (own ? "Equip" : "Unlock"));
      btn.disabled = equipped || (!own && G.gems < cosCost(item));
      btn.onclick = () => buyOrEquip(cat.id, id);
    }
    card.appendChild(btn);""",
    """    // an index entry: what it is, what it is worth, and whether you have found it
    meta.appendChild(el("span", "cos-cost", own
      ? (equipped ? "In use ✓" : "In your collection ✓")
      : "Not found yet · 📦 rolls from a crate"));
    card.appendChild(meta);
    let btn;
    if (item.crateOnly || cat.noEquip) {
      btn = el("button", "btn tiny", own ? "Found" : "Not found");
      btn.disabled = true;
    } else {
      btn = el("button", "btn tiny" + (equipped ? " on" : ""), equipped ? "In use" : "Equip");
      btn.disabled = equipped || !own;
      btn.onclick = () => equipOwned(cat.id, id);
    }
    card.appendChild(btn);""", "index card")

sub("""    c.own + " of " + c.total + " collectibles · ⭐ " + fmtNum(worthTotal()) + " worth points · " +
    G.gems + " gems to spend · " + crates + " crate" + (crates === 1 ? "" : "s");""",
    """    c.own + " of " + c.total + " discovered · ⭐ " + fmtNum(worthTotal()) + " worth points · 💎 " +
    G.gems + " banked · 🎁 " + crates + " crate" + (crates === 1 ? "" : "s") + " to spin in the Crates tab";""",
    "inv sub")

sub("""    [["all", "All categories"]].concat(COSMETIC_CATS.map(cat => [cat.id, cat.label]))
      .concat([["crate", crates ? "🎁 Crates (" + crates + ")" : "🎁 Crates"]]), invCat);""",
    """    [["all", "All categories"]].concat(COSMETIC_CATS.map(cat => [cat.id, cat.label])), invCat);""",
    "inv dropdown")

# ================================================== 3. crates come from milestones
sub("""  if (G.waveHadBoss) {
    G.crates.supply = (G.crates.supply || 0) + 1;
    toast("📦 Supply Crate secured — " + G.crates.supply + " in the hold. Open it in Inventory & Skins → Crates.");
  }""",
    """  // Crates are milestone rewards, never purchases: boss waves, then every 10/25/100 waves.
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
  }""", "milestone drops")

# ==================================================== panel + crates-only rerender
sub("""function showInv(on) {""",
    """// The Crates tab: its own screen for the crates you have earned.
function showCrates(on) {
  const visible = on !== false;
  if (visible) closeOverlays("crates");
  document.getElementById("crates").classList.toggle("on", visible);
  if (visible) renderCratesPanel();
  syncTopTabs();
}
function renderCratesPanel() {
  const body = document.getElementById("crates-body");
  if (!body) return;
  body.textContent = "";
  const status = document.getElementById("crates-status");
  if (status) {
    const held = cratesHeld();
    status.textContent = held ? held + " in the hold — spin one below"
      : "empty hold · boss waves and every 10/25/100 waves refill it";
  }
  renderCrates(body);
}
function showInv(on) {""", "showCrates")

sub("""  const body = document.getElementById("inv-body");
  body.textContent = "";
  if (invCat === "crate") { renderCrates(body); return; }
  if (invCat === "all") {""",
    """  const body = document.getElementById("inv-body");
  body.textContent = "";
  if (invCat === "all") {""", "inv crate branch")

sub("""    sfx("coin");
    ui();
    renderInventory();
  };""",
    """    sfx("coin");
    ui();
    renderInventory();
    if (overlayOpen("crates")) renderCratesPanel();
  };""", "announce refresh")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
