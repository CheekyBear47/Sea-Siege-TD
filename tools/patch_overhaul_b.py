# Pass B: tooltips + stat grid, single-tab inventory with dropdowns and rarity
# sorting, crate tiers with a rolling animation, and trading rules + item preview.
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


# ================================================================= HTML + CSS
sub("""      <div class="tabs" id="inv-tabs"></div>""",
    """      <div class="inv-selects">
        <label>View<select class="mini-sel" id="inv-cat"></select></label>
        <label>Show<select class="mini-sel" id="inv-filter"></select></label>
        <label>Sort<select class="mini-sel" id="inv-sort"></select></label>
      </div>""", "inventory selects")

sub("""<div id="invites"></div>""",
    """<div id="invites"></div>

<!-- Crate rolling animation: a spray of possible drops that settles on the real one -->
<div id="roll">
  <div class="roll-box">
    <div class="roll-card r-common" id="roll-card">📦</div>
    <div class="roll-label" id="roll-label">Rolling…</div>
  </div>
</div>""", "roll overlay")

sub("""  /* onboarding identity strip: avatar + the Google account being named */""",
    """  /* ---- core stat grid (armoury cards): the prose lives in the tooltip ---- */
  .stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:5px 0 4px}
  .stat-cell{background:rgba(12,22,36,.55);border:1px solid var(--stroke);border-radius:8px;
    padding:3px 5px;text-align:center;line-height:1.15}
  .stat-cell b{display:block;font-size:11.5px;color:#eaf6ff;font-weight:800}
  .stat-cell small{display:block;font-size:7.5px;letter-spacing:.7px;color:var(--dim);text-transform:uppercase}
  .card.mini .sp{display:block;font-size:9px;color:#8fd6ff;font-weight:700;margin-top:2px}
  .card.mini{cursor:help}
  /* ---- inventory: one list, three sleek dropdowns ---- */
  .inv-selects{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px}
  .inv-selects label{display:flex;align-items:center;gap:5px;font-size:9px;letter-spacing:1px;
    text-transform:uppercase;color:var(--dim);font-weight:800}
  .inv-selects select{max-width:190px}
  /* ---- crate rolling ---- */
  #roll{position:absolute;inset:0;display:none;justify-items:center;align-items:center;z-index:9;
    border-radius:16px;background:radial-gradient(600px 400px at 50% 40%, rgba(10,24,40,.88), rgba(3,6,11,.96));
    backdrop-filter:blur(4px)}
  #roll.on{display:grid}
  .roll-box{text-align:center}
  .roll-card{width:118px;height:118px;margin:0 auto 16px;display:grid;place-items:center;font-size:54px;
    border-radius:22px;border:2px solid var(--stroke);background:rgba(12,22,36,.85);
    box-shadow:0 18px 40px rgba(0,0,0,.6)}
  .roll-card.spin{animation:rollspin .16s linear}
  .roll-card.win{animation:rollwin .5s cubic-bezier(.2,1.5,.4,1) 1;animation-fill-mode:forwards}
  @keyframes rollspin{from{transform:translateY(-9px) scale(.94);opacity:.55}to{transform:none;opacity:1}}
  @keyframes rollwin{0%{transform:scale(.72) rotate(-6deg)}60%{transform:scale(1.12) rotate(3deg)}100%{transform:scale(1)}}
  .roll-card.r-rare{border-color:rgba(105,184,255,.75)}
  .roll-card.r-epic{border-color:rgba(195,155,255,.8)}
  .roll-card.r-legendary{border-color:rgba(255,209,102,.85);box-shadow:0 0 28px rgba(255,209,102,.35)}
  .roll-card.r-mythic{border-color:rgba(255,122,217,.9);box-shadow:0 0 34px rgba(255,122,217,.45)}
  .roll-label{font-size:13px;font-weight:800;color:#eaf6ff}
  /* ---- crate tiers + trade preview ---- */
  .crate-card.t4{border-color:rgba(195,155,255,.5)}
  .crate-card.t5{border-color:rgba(255,122,217,.55);background:linear-gradient(150deg,rgba(80,40,90,.4),rgba(24,14,34,.5))}
  .trade-preview{display:flex;gap:11px;align-items:center;margin:9px 0 4px;padding:10px 12px;border-radius:13px;
    background:rgba(143,214,255,.05);border:1px solid var(--stroke)}
  .trade-preview .cos-swatch{width:54px;height:54px;font-size:22px;flex:0 0 auto}
  .trade-preview .cos-meta{flex:1;min-width:0;text-align:left}
  .trade-preview .cos-name{font-size:13px}
  .tv-detail{display:block;font-size:10px;color:var(--dim);line-height:1.45;margin-top:2px}
  .pick .rarity{margin-left:5px}
  #repair-panel{margin-top:8px;padding:9px 10px;border-radius:12px;background:rgba(87,224,138,.06);
    border:1px solid rgba(87,224,138,.28)}
  #repair-panel .sect2{color:#8ee6b0}
  #repair-panel .sect2 span{color:var(--dim);font-weight:700;float:right}
  /* onboarding identity strip: avatar + the Google account being named */""", "overhaul CSS")

# ==================================================================== armoury
sub("""  if (b.mythic) card.title = b.name + " — unlocked. Costs " + b.cost + " gold to build in a run.";
  card.appendChild(el("div", "glyph", b.glyph));
  const meta = el("div", "meta");
  meta.appendChild(el("b", null, b.name));
  meta.appendChild(el("span", null, b.desc));
  if (b.mythic) meta.appendChild(el("span", "mystats", turretStatLine(type) + " · " + b.cost + " 🪙 in a run"));
  card.appendChild(meta);
  card.appendChild(el("div", "cost", b.cost + " 🪙"));
  card.onclick = () => toggleBuild(type);
  return card;
}""",
    """  card.appendChild(el("div", "glyph", b.glyph));
  const meta = el("div", "meta");
  meta.appendChild(el("b", null, b.name));
  meta.appendChild(statGrid(b));
  meta.appendChild(el("span", "sp", b.special.name));
  card.appendChild(meta);
  // the long prose is a hover tooltip, not a wall of text on the card
  card.title = turretTooltip(type);
  card.onclick = () => toggleBuild(type);
  return card;
}
// Core numbers in one tidy grid: damage, range, fire rate, cost.
function statGrid(b) {
  const g = el("div", "stat-grid");
  [["DMG", String(b.dmg)], ["RANGE", String(Math.round(b.range))],
   ["RATE", fmtRate(b.rate)], ["COST", b.cost + "🪙"]].forEach(pair => {
    const c = el("div", "stat-cell");
    c.appendChild(el("b", null, pair[1]));
    c.appendChild(el("small", null, pair[0]));
    g.appendChild(c);
  });
  return g;
}
function turretTooltip(type) {
  const b = TOWERS[type];
  const lines = [
    b.name + (b.mythic ? " · mythic (crate drop only)" : " · armory rank " + b.rank),
    b.desc,
    "Damage " + b.dmg + " · Range " + Math.round(b.range) + " · " + fmtRate(b.rate),
    "Special: " + b.special.name + (b.special.desc ? " — " + b.special.desc : ""),
    "Builds for " + b.cost + " gold in a run" + (b.mythic ? " once unlocked." : ".")
  ];
  return lines.join("\\n");
}""", "armoryCard")

# ============================================================ crate tiers/roll
sub("""const CRATES = {
  supply: { name: "Supply Crate", glyph: "📦", gems: 3, desc: "3 💎, or free from every boss wave",
    odds: { common: 55, rare: 29, epic: 13.6, legendary: 2.0, mythic: 0.4 } },
  royal:  { name: "Royal Chest",  glyph: "🎁", gems: 6, desc: "buy with gems",
    odds: { common: 30, rare: 38, epic: 24, legendary: 7.1, mythic: 0.9 } }
};""",
    """// Four tiers, steep price tags, and mythic odds still tiny on the cheap two.
const CRATES = {
  supply: { name: "Supply Crate", glyph: "📦", gems: 6, tier: 1,
    desc: "6 💎, or free from every boss wave",
    odds: { common: 55, rare: 29, epic: 13.6, legendary: 2.0, mythic: 0.4 } },
  royal:  { name: "Royal Chest",  glyph: "🎁", gems: 18, tier: 2, desc: "no commons at all",
    odds: { common: 30, rare: 38, epic: 24, legendary: 7.1, mythic: 0.9 } },
  admiral: { name: "Admiral's Vault", glyph: "⚜️", gems: 45, tier: 4, desc: "rare or better, every time",
    odds: { common: 0, rare: 26, epic: 46, legendary: 26.5, mythic: 1.5 } },
  reliquary: { name: "Mythic Reliquary", glyph: "🔮", gems: 120, tier: 5, desc: "epic floor · the only real mythic odds",
    odds: { common: 0, rare: 0, epic: 34, legendary: 62, mythic: 4 } }
};
function cratesHeld() { let n = 0; Object.keys(CRATES).forEach(k => { n += G.crates[k] || 0; }); return n; }
const CRATE_ORDER = ["supply", "royal", "admiral", "reliquary"];""", "CRATES")

sub("""function rollCrate(kind) {
  const crate = CRATES[kind];
  if (!crate) return null;""",
    """function rollCrate(kind, silent) {
  const crate = CRATES[kind];
  if (!crate) return null;""", "rollCrate sig")

sub("""  G.lastDrop = { cat: pick.cat, id: pick.id, r: rar, dup: duplicate, at: Date.now() };
  banner(crate.glyph + " " + pick.item.name + (rar === "mythic" ? " — MYTHIC!" : ""), rr.col);
  toast(crate.glyph + " " + crate.name + " opened → " + detail);
  if (!duplicate) sfx(rar === "mythic" || rar === "legendary" ? "win" : "gem");
  sfx("coin");
  queueSave();
  ui();
  renderInventory();
  return pick;
}""",
    """  G.lastDrop = { cat: pick.cat, id: pick.id, r: rar, dup: duplicate, at: Date.now() };
  queueSave();
  const announce = () => {
    banner(crate.glyph + " " + pick.item.name + (rar === "mythic" ? " — MYTHIC!" : ""), rr.col);
    toast(crate.glyph + " " + crate.name + " opened → " + detail);
    if (!duplicate) sfx(rar === "mythic" || rar === "legendary" ? "win" : "gem");
    sfx("coin");
    ui();
    renderInventory();
  };
  // one crate at a time gets the rolling animation; bulk opens just report
  if (silent || rolling) { announce(); return pick; }
  playRoll(pick, crate, duplicate, announce);
  return pick;
}
// The rolling animation: a spray of possible drops that settles on the real one.
let rolling = false;
function playRoll(pick, crate, duplicate, done) {
  const host = document.getElementById("roll");
  const card = document.getElementById("roll-card");
  const label = document.getElementById("roll-label");
  const reveal = () => {
    if (card) {
      card.textContent = pick.item.glyph || "🎁";
      card.className = "roll-card win r-" + (pick.item.r || "common");
    }
    if (label) {
      label.textContent = rarityOf(pick.item).name + " · " + pick.item.name +
        (duplicate ? " (duplicate)" : " · +" + itemWorth(pick.item) + " pts");
    }
    sfx(pick.item.r === "mythic" || pick.item.r === "legendary" ? "win" : "gem");
  };
  if (!host || !card) { reveal(); setTimeout(done, 900); return; }
  rolling = true;
  const pool = [];
  RARITY_ORDER.forEach(r => cratePool(r).forEach(x => pool.push(x)));
  if (label) label.textContent = crate.glyph + " " + crate.name + " — rolling…";
  host.classList.add("on");
  let ticks = 0;
  const total = 24 + Math.floor(Math.random() * 10);
  const timer = setInterval(() => {
    const it = pool[(Math.random() * pool.length) | 0];
    if (it) {
      card.textContent = it.item.glyph || "🎁";
      card.className = "roll-card spin r-" + (it.item.r || "common");
    }
    ticks++;
    if (ticks < total) return;
    clearInterval(timer);
    reveal();
    setTimeout(() => {
      host.classList.remove("on");
      rolling = false;
      done();
    }, 1500);
  }, 70);
}""", "rollCrate body")

sub("""  Object.entries(CRATES).forEach(([kind, crate]) => {
    const card = el("div", "crate-card" + (kind === "royal" ? " royal" : ""));""",
    """  CRATE_ORDER.forEach(kind => {
    const crate = CRATES[kind];
    const card = el("div", "crate-card t" + (crate.tier || 1) + (kind === "royal" ? " royal" : ""));""",
    "renderCrates loop")

sub("""  const held = (G.crates.supply || 0) + (G.crates.royal || 0);
  if (held > 1) {
    const row = el("div", "inv-bar-row");
    const all = el("button", "pick on", "Open all " + held + " crates in the hold");
    all.onclick = () => {
      let n = 0;
      while (((G.crates.supply || 0) + (G.crates.royal || 0)) > 0 && n < 20) {
        rollCrate((G.crates.supply || 0) > 0 ? "supply" : "royal");
        n++;
      }
      if (n) toast("Opened " + n + " crates.");
      renderInventory();
    };""",
    """  const held = cratesHeld();
  if (held > 1) {
    const row = el("div", "inv-bar-row");
    const all = el("button", "pick on", "Open all " + held + " crates in the hold");
    all.onclick = () => {
      let n = 0;
      while (cratesHeld() > 0 && n < 20) {
        const kind = CRATE_ORDER.slice().reverse().find(k => (G.crates[k] || 0) > 0) || "supply";
        rollCrate(kind, true);
        n++;
      }
      if (n) toast("Opened " + n + " crates.");
      renderInventory();
    };""", "open all")

sub("""  const note = el("div", "crate-note",
    "Mythic turret cards are under 1% from both crate types. Supply Crates drop from every boss wave. " +
    "Duplicates refund gems, so a crate is never wasted.");""",
    """  const note = el("div", "crate-note",
    "Mythic turret cards stay under 1% on the Supply Crate and Royal Chest; the Admiral's Vault and the " +
    "Mythic Reliquary are the only places the odds really move. Supply Crates still drop from boss waves, " +
    "and duplicates refund gems, so a crate is never wasted.");""", "crate note")

# ======================================================= inventory (single tab)
sub("""let invFilter = "all";      // all | locked | owned
let invSort = "value";      // value | rarity | name""",
    """let invFilter = "all";      // all | locked | owned
let invSort = "rarity";     // rarity (rarest first) | value | name
let invCat = "all";         // all | <category id> | crate""", "inv vars")

sub("""  const rank = id => RARITY_ORDER.indexOf(cat.items[id].r || "common");
  const sorters = {
    value: (a, b) => itemWorth(b[1]) - itemWorth(a[1]),
    rarity: (a, b) => rank(a[0]) - rank(b[0]),
    name: (a, b) => a[1].name.localeCompare(b[1].name)
  };""",
    """  const rank = id => RARITY_ORDER.indexOf(cat.items[id].r || "common");
  const sorters = {
    value: (a, b) => itemWorth(b[1]) - itemWorth(a[1]),
    rarity: (a, b) => rank(b[0]) - rank(a[0]),      // Mythic first, Common last
    name: (a, b) => a[1].name.localeCompare(b[1].name)
  };""", "inv sort")

# the bar loses its filter/sort buttons (the dropdowns own them now)
sub("""  const bar = el("div", "inv-bar");
  const eq = el("div", "inv-bar-row");
  eq.appendChild(el("span", "inv-bar-label", "Show"));
  ["all", "locked", "owned"].forEach(f => {
    const b = el("button", "pick" + (invFilter === f ? " on" : ""), f === "all" ? "All" : f === "locked" ? "Locked" : "Owned");
    b.onclick = () => { invFilter = f; renderInventory(); };
    eq.appendChild(b);
  });
  eq.appendChild(el("span", "inv-bar-label", "Sort"));
  [["value", "Value"], ["rarity", "Rarity"], ["name", "Name"]].forEach(([s, label]) => {
    const b = el("button", "pick" + (invSort === s ? " on" : ""), label);
    b.onclick = () => { invSort = s; renderInventory(); };
    eq.appendChild(b);
  });
  bar.appendChild(eq);
  const info = el("div", "inv-bar-row");""",
    """  const bar = el("div", "inv-bar");
  const info = el("div", "inv-bar-row");""", "inv bar buttons")

sub("""function renderInventory() {
  document.getElementById("inv-wallet").textContent = "💎 " + G.gems + " gems";
  const c = cosCount();
  const crates = (G.crates.supply || 0) + (G.crates.royal || 0);
  document.getElementById("inv-sub").textContent =
    c.own + " of " + c.total + " collectibles · ⭐ " + fmtNum(worthTotal()) + " worth points · " +
    G.gems + " gems to spend · " + crates + " crate" + (crates === 1 ? "" : "s");
  const tabs = document.getElementById("inv-tabs");
  tabs.textContent = "";
  const tabDefs = COSMETIC_CATS.concat([{ id: "crate", label: "🎁 Crates" }]);
  tabDefs.forEach(cat => {
    const label = cat.id === "crate" && crates ? cat.label + " (" + crates + ")" : cat.label;
    const b = el("button", "tab" + (invTab === cat.id ? " on" : ""), label);
    b.onclick = () => { invTab = cat.id; renderInventory(); };
    tabs.appendChild(b);
  });
  const body = document.getElementById("inv-body");
  body.textContent = "";
  if (invTab === "crate") { renderCrates(body); return; }
  const cat = COSMETIC_CATS.find(x => x.id === invTab) || COSMETIC_CATS[0];
  renderInvBar(body, cat);
  const grid = el("div", "cos-grid");
  for (const [id, item] of invItems(cat)) {""",
    """function fillSelect(id, pairs, value) {
  const sel = document.getElementById(id);
  if (!sel) return;
  sel.textContent = "";
  pairs.forEach(pair => {
    const o = document.createElement("option");
    o.value = pair[0];
    o.textContent = pair[1];
    sel.appendChild(o);
  });
  sel.value = value;
}
// One list, not tabs: pick a category from the dropdown and everything is sorted
// rarest-first by default.
function renderInventory() {
  document.getElementById("inv-wallet").textContent = "💎 " + G.gems + " gems";
  const c = cosCount();
  const crates = cratesHeld();
  document.getElementById("inv-sub").textContent =
    c.own + " of " + c.total + " collectibles · ⭐ " + fmtNum(worthTotal()) + " worth points · " +
    G.gems + " gems to spend · " + crates + " crate" + (crates === 1 ? "" : "s");
  fillSelect("inv-cat",
    [["all", "All categories"]].concat(COSMETIC_CATS.map(cat => [cat.id, cat.label]))
      .concat([["crate", crates ? "🎁 Crates (" + crates + ")" : "🎁 Crates"]]), invCat);
  fillSelect("inv-filter", [["all", "All items"], ["owned", "Owned only"], ["locked", "Not yet owned"]], invFilter);
  fillSelect("inv-sort", [["rarity", "Rarity (Mythic → Common)"], ["value", "Worth points"],
    ["name", "Name"]], invSort);
  const bind = (id, fn) => { const e = document.getElementById(id); if (e) e.onchange = fn; };
  bind("inv-cat", e => { invCat = e.target.value; renderInventory(); });
  bind("inv-filter", e => { invFilter = e.target.value; renderInventory(); });
  bind("inv-sort", e => { invSort = e.target.value; renderInventory(); });
  const body = document.getElementById("inv-body");
  body.textContent = "";
  if (invCat === "crate") { renderCrates(body); return; }
  if (invCat === "all") {
    COSMETIC_CATS.forEach(cat => {
      body.appendChild(el("div", "sect2", cat.label));
      renderInvBar(body, cat);
      body.appendChild(cosGrid(cat));
    });
    return;
  }
  const cat = COSMETIC_CATS.find(x => x.id === invCat) || COSMETIC_CATS[0];
  renderInvBar(body, cat);
  body.appendChild(cosGrid(cat));
}
// One category's cards (rarest first), including sealed crate-only mythics.
function cosGrid(cat) {
  const grid = el("div", "cos-grid");
  for (const [id, item] of invItems(cat)) {""", "renderInventory head")

sub("""    card.appendChild(btn);
    grid.appendChild(card);
  }
  body.appendChild(grid);
}
function showInv(on) {""",
    """    card.appendChild(btn);
    grid.appendChild(card);
  }
  return grid;
}
function showInv(on) {""", "renderInventory tail")

# =================================================================== trading
sub("""function tradableItems() {
  const list = [];
  COSMETIC_CATS.forEach(cat => {
    Object.entries(cat.items).forEach(([id, item]) => {
      if (unlocked(cat.id, id)) list.push({ key: cosId(cat.id, id), cat: cat.id, id: id, item: item });
    });
  });
  return list;
}""",
    """// Basic starter gear is not tradable: only Rare and above can change hands.
const TRADE_MIN = RARITY_ORDER.indexOf("rare");
function isTradeable(item) { return RARITY_ORDER.indexOf(item.r || "common") >= TRADE_MIN; }
function tradableItems() {
  const list = [];
  COSMETIC_CATS.forEach(cat => {
    Object.entries(cat.items).forEach(([id, item]) => {
      if (unlocked(cat.id, id) && isTradeable(item)) {
        list.push({ key: cosId(cat.id, id), cat: cat.id, id: id, item: item });
      }
    });
  });
  return list.sort((a, b) => itemWorth(b.item) - itemWorth(a.item));
}
function rarityChip(item) {
  return el("span", "rarity " + (item.r || "common"), rarityOf(item).name);
}
// The inspect panel: exact sprite, stats and rarity before anything is committed.
let tradePeek = null;
function tradeDetail(it) {
  if (it.cat === "turret") return turretStatLine(it.id) + " · builds for " + TOWERS[it.id].cost + " 🪙 in a run";
  if (it.cat === "env") return "Re-bakes the whole map — " + it.item.name + " terrain, water and weather.";
  if (it.cat === "fleet") return "Recolours every enemy vessel in the " + it.item.name + " livery.";
  if (it.cat === "wrap") return "Finishes your turret pads in " + it.item.name + ".";
  if (it.cat === "banner") return "Hangs " + it.item.name + " over the harbour.";
  if (it.cat === "fx") return "Recolours your bolts, shells and beams.";
  return "";
}
function tradePreviewBox() {
  const box = el("div", "trade-preview");
  const it = tradePeek ? itemByKey(tradePeek) : null;
  if (!it) {
    box.appendChild(el("span", "hint",
      "Select an item on either side to inspect its sprite, stats and rarity before you commit."));
    return box;
  }
  const sw = el("div", "cos-swatch");
  sw.style.background = cosSwatch(it.cat, it.id);
  if (it.cat === "turret") sw.textContent = it.item.glyph || "🔱";
  box.appendChild(sw);
  const meta = el("div", "cos-meta");
  meta.appendChild(el("span", "cos-name", it.item.name));
  const chipRow = el("span", null, "");
  chipRow.appendChild(rarityChip(it.item));
  chipRow.appendChild(el("span", "rarity", "⭐ " + itemWorth(it.item) + " pts"));
  meta.appendChild(chipRow);
  meta.appendChild(el("span", "tv-detail", tradeDetail(it)));
  box.appendChild(meta);
  return box;
}""", "tradableItems")

sub("""    for (let i = 0; i < OFFER_SLOTS; i++) {
      const key = keys[i];
      const s = el("div", "slot" + (key ? " filled" : ""));
      if (key) {
        const it = itemByKey(key);
        s.textContent = it ? (it.item.glyph ? it.item.glyph + " " : "") + it.item.name.slice(0, 14) : key;
        if (it) { s.style.borderColor = rarityOf(it.item).col; s.title = it.item.name + " · " +
          rarityOf(it.item).name + " · " + itemWorth(it.item) + " pts"; }
        if (mine && !t.mineLocked) { s.title += " (click to remove)"; s.onclick = () => tradeRemove(key); }
      }
      slots.appendChild(s);
    }""",
    """    for (let i = 0; i < OFFER_SLOTS; i++) {
      const key = keys[i];
      const s = el("div", "slot" + (key ? " filled" : ""));
      if (key) {
        const it = itemByKey(key);
        s.textContent = it ? (it.item.glyph ? it.item.glyph + " " : "") + it.item.name.slice(0, 14) : key;
        if (it) {
          s.style.borderColor = rarityOf(it.item).col;
          s.appendChild(rarityChip(it.item));
          s.title = it.item.name + " · " + rarityOf(it.item).name + " · " + itemWorth(it.item) + " pts" +
            (mine && !t.mineLocked ? " (click to inspect, shift-click to remove)" : " (click to inspect)");
          s.onclick = ev => {
            tradePeek = key;
            if (mine && !t.mineLocked && ev && ev.shiftKey) { tradeRemove(key); return; }
            renderTradeRoom();
          };
        }
      }
      slots.appendChild(s);
    }""", "offer slots")

sub("""      tradableItems().forEach(o => {
        const b = el("button", "pick", (o.item.glyph ? o.item.glyph + " " : "") + o.item.name +
          " (" + itemWorth(o.item) + ")");
        b.disabled = t.mineLocked || t.mine.includes(o.key);
        b.onclick = () => tradeAdd(o.key);
        picks.appendChild(b);
      });""",
    """      const mineList = tradableItems();
      if (!mineList.length) {
        picks.appendChild(el("div", "hint",
          "Nothing tradable yet — only Rare, Epic, Legendary and Mythic items can change hands."));
      }
      mineList.forEach(o => {
        const b = el("button", "pick", (o.item.glyph ? o.item.glyph + " " : "") + o.item.name);
        b.appendChild(rarityChip(o.item));
        b.disabled = t.mineLocked || t.mine.includes(o.key);
        b.title = o.item.name + " · " + rarityOf(o.item).name + " · " + itemWorth(o.item) + " worth pts";
        b.onclick = () => { tradePeek = o.key; tradeAdd(o.key); };
        picks.appendChild(b);
      });
      const blocked = Object.keys(G.cosOwn).filter(k => {
        const it = itemByKey(k);
        return it && !isTradeable(it.item);
      }).length;
      if (blocked) {
        picks.appendChild(el("div", "hint", blocked + " basic item(s) in your hold cannot be traded at all."));
      }""", "pick list")

sub("""  host.appendChild(cols);

  const bar = el("div", "trade-bar");""",
    """  host.appendChild(cols);
  host.appendChild(tradePreviewBox());

  const bar = el("div", "trade-bar");""", "preview placement")

# save/restore must carry every crate tier
sub("""    if (save.crates) G.crates = { supply: save.crates.supply || 0, royal: save.crates.royal || 0 };""",
    """    if (save.crates) {
      G.crates = {};
      Object.keys(CRATES).forEach(k => { G.crates[k] = save.crates[k] || 0; });
    }""", "crates restore")

sub("""    crates: { supply: G.crates.supply || 0, royal: G.crates.royal || 0 },""",
    """    crates: (function () { const c = {}; Object.keys(CRATES).forEach(k => { c[k] = G.crates[k] || 0; }); return c; })(),""",
    "crates save")

sub("""    crates: { supply: 0, royal: 0 },""",
    """    crates: { supply: 0, royal: 0, admiral: 0, reliquary: 0 },""", "newGame crates")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
