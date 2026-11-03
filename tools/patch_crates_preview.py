# Persistent session restore, a properly styled Crates screen, wrapped-safe odds
# badges, and a crate contents preview with locked mystery rarities.
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


# ================================================== 2a. the Crates screen is styled
# Overlay positioning is id-scoped, so #crates needs its own rules or it renders inline.
sub("""  #inv p{margin:0 0 10px;color:var(--dim);font-size:11.5px}""",
    """  #inv p{margin:0 0 10px;color:var(--dim);font-size:11.5px}
  #crates{
    position:absolute;inset:0;display:none;justify-items:center;align-items:start;border-radius:16px;z-index:6;
    background:radial-gradient(700px 460px at 50% 30%, rgba(10,24,40,.88), rgba(3,6,11,.96));
    backdrop-filter:blur(5px);padding:16px 0 20px;overflow:auto;
  }
  #crates.on{display:grid}
  #crates .box{
    text-align:left;padding:18px 22px 16px;border-radius:18px;max-width:1080px;width:min(94%,1080px);
    max-height:92%;overflow:auto;background:var(--glass);border:1px solid var(--stroke);
  }
  #crates h2{margin:0;font-size:20px;letter-spacing:3px;text-transform:uppercase}
  #crates .crate-note{max-width:820px}""", "crates overlay css")

# the cards themselves: a column layout, so nothing is squeezed into vertical letters
sub("""  .crate-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
  @media (max-width:640px){ .crate-grid{grid-template-columns:1fr} }
  .crate-card{display:flex;align-items:center;gap:11px;padding:11px 13px;border-radius:14px;
    background:linear-gradient(150deg, rgba(52,42,26,.55), rgba(16,20,30,.6));border:1px solid rgba(255,209,102,.3)}""",
    """  .crate-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
  @media (max-width:900px){ .crate-grid{grid-template-columns:1fr} }
  .crate-card{display:flex;flex-direction:column;gap:10px;padding:14px 16px;border-radius:16px;
    background:linear-gradient(150deg, rgba(52,42,26,.55), rgba(16,20,30,.6));border:1px solid rgba(255,209,102,.3)}
  .crate-top{display:flex;align-items:center;gap:12px;min-width:0}
  .crate-top .crate-meta{flex:1 1 auto;min-width:0}""", "crate card css")

sub("""  .crate-odds{color:#8fc7ff !important;letter-spacing:.2px}""",
    """  /* drop rates as a badge grid: never one letter per line */
  .crate-odds{display:flex;flex-wrap:wrap;gap:6px}
  .crate-odds span{white-space:nowrap;padding:3px 8px;border-radius:8px;font-size:10.5px;font-weight:700;
    color:#9fd6ff;background:rgba(30,60,96,.5);border:1px solid rgba(120,180,255,.22)}
  .crate-odds span.r-rare{color:#a8d8ff}
  .crate-odds span.r-epic{color:#d0b8ff;border-color:rgba(195,155,255,.3)}
  .crate-odds span.r-legendary{color:#ffd166;border-color:rgba(255,209,102,.32)}
  .crate-odds span.r-mythic{color:#ffb3e6;border-color:rgba(255,122,217,.35)}
  /* what can actually drop */
  .crate-contents{display:flex;flex-direction:column;gap:7px;border-top:1px solid var(--stroke);padding-top:10px}
  .crate-contents .cont-head{font-size:9.5px;letter-spacing:1.2px;text-transform:uppercase;color:var(--dim);font-weight:800}
  .cont-row{display:flex;align-items:flex-start;gap:8px;font-size:10.5px}
  .cont-row .rarity{flex:0 0 auto;white-space:nowrap}
  .cont-count{flex:0 0 auto;color:var(--dim);font-weight:700;white-space:nowrap;min-width:34px}
  .chips{display:flex;flex-wrap:wrap;gap:5px;min-width:0}
  .chips span{white-space:nowrap;padding:2px 7px;border-radius:8px;font-size:10px;color:var(--dim);
    background:rgba(255,255,255,.045);border:1px solid var(--stroke)}
  .chips span.have{color:#dfffee;border-color:rgba(87,224,138,.45);background:rgba(30,70,50,.45)}
  .crate-secret{flex:1;font-size:10.5px;color:#ffd166;background:rgba(60,45,15,.4);
    border:1px dashed rgba(255,209,102,.45);border-radius:10px;padding:6px 9px}""", "odds + contents css")

# ================================== 3. crate contents preview + mystery rarities
sub("""function renderCrates(body) {
  const grid = el("div", "crate-grid");
  CRATE_ORDER.forEach(kind => {
    const crate = CRATES[kind];
    const card = el("div", "crate-card t" + (crate.tier || 1) + (kind === "royal" ? " royal" : ""));
    card.appendChild(el("div", "crate-glyph", crate.glyph));
    const meta = el("div", "crate-meta");
    meta.appendChild(el("b", null, crate.name));
    meta.appendChild(el("span", null, "in the hold: " + (G.crates[kind] || 0) + " · " + crate.from));
    const odds = el("span", "crate-odds");
    odds.textContent = RARITY_ORDER.map(r => RARITY[r].name.slice(0, 3) + " " + crate.odds[r] + "%").join(" · ");
    meta.appendChild(odds);
    card.appendChild(meta);
    const btn = el("button", "btn tiny", (G.crates[kind] || 0) > 0 ? "Spin it" : "Not in the hold");
    btn.disabled = (G.crates[kind] || 0) <= 0;
    btn.onclick = () => rollCrate(kind);
    card.appendChild(btn);
    grid.appendChild(card);
  });
  body.appendChild(grid);""",
    """// The two top rarities stay a mystery until the player has actually found one of
// them - their names and contents are hidden behind a 🔒 ??? until then.
const SECRET_RARITIES = ["legendary", "mythic"];
function rarityFound(r) {
  return COSMETIC_CATS.some(cat => Object.entries(cat.items)
    .some(([id, it]) => (it.r || "common") === r && unlocked(cat.id, id)));
}
function renderCrates(body) {
  const grid = el("div", "crate-grid");
  CRATE_ORDER.forEach(kind => {
    const crate = CRATES[kind];
    const card = el("div", "crate-card t" + (crate.tier || 1) + (kind === "royal" ? " royal" : ""));
    // --- header: glyph, name, hold, spin ---
    const top = el("div", "crate-top");
    top.appendChild(el("div", "crate-glyph", crate.glyph));
    const meta = el("div", "crate-meta");
    meta.appendChild(el("b", null, crate.name));
    meta.appendChild(el("span", null, "in the hold: " + (G.crates[kind] || 0) + " · " + crate.from));
    top.appendChild(meta);
    const btn = el("button", "btn tiny", (G.crates[kind] || 0) > 0 ? "Spin it" : "Not in the hold");
    btn.disabled = (G.crates[kind] || 0) <= 0;
    btn.onclick = () => rollCrate(kind);
    top.appendChild(btn);
    card.appendChild(top);

    // --- drop rates, as badges that cannot break mid-word ---
    const odds = el("div", "crate-odds");
    RARITY_ORDER.forEach(r => {
      const pct = crate.odds[r];
      if (!pct) return;
      odds.appendChild(el("span", "r-" + r, RARITY[r].name + " " + pct + "%"));
    });
    card.appendChild(odds);

    // --- contents: every collectible this crate can roll, by rarity ---
    const contents = el("div", "crate-contents");
    let poolTotal = 0;
    let poolOwn = 0;
    RARITY_ORDER.forEach(r => {
      if (!crate.odds[r]) return;
      const locked = SECRET_RARITIES.indexOf(r) >= 0 && !rarityFound(r);
      const row = el("div", "cont-row");
      row.appendChild(el("span", "rarity " + r, RARITY[r].name));
      if (locked) {
        row.appendChild(el("div", "crate-secret",
          "🔒 ??? — " + (r === "mythic" ? "mythic turret cards" : "legendary contents") +
          " stay hidden until you find one of your own."));
        contents.appendChild(row);
        return;
      }
      const pool = cratePool(r);
      const own = pool.filter(x => unlocked(x.cat, x.id));
      poolTotal += pool.length;
      poolOwn += own.length;
      row.appendChild(el("span", "cont-count", own.length + "/" + pool.length));
      const chips = el("div", "chips");
      pool.forEach(x => chips.appendChild(el("span", unlocked(x.cat, x.id) ? "have" : null,
        (unlocked(x.cat, x.id) ? "✓ " : "") + x.item.name)));
      row.appendChild(chips);
      contents.appendChild(row);
    });
    contents.insertBefore(el("div", "cont-head",
      "Contents · " + poolTotal + " item" + (poolTotal === 1 ? "" : "s") + " can drop · you have " + poolOwn),
      contents.firstChild);
    card.appendChild(contents);
    grid.appendChild(card);
  });
  body.appendChild(grid);""", "renderCrates")

# the last-drop readout belongs on the crates screen too
sub("""  const note = el("div", "crate-note",""",
    """  if (G.lastDrop) {
    const cat = COSMETIC_CATS.find(c => c.id === G.lastDrop.cat);
    const item = cat && cat.items[G.lastDrop.id];
    if (item) {
      const last = el("div", "crate-last");
      last.appendChild(el("span", null, "Last drop: " + item.name));
      last.appendChild(el("span", null, G.lastDrop.dup ? "duplicate" : "new"));
      body.appendChild(last);
    }
  }
  const note = el("div", "crate-note",""", "last drop")

# ================================================ 1. keep the session across reloads
# Already handled by authGate() -> readSession() -> resumeSession(); verified live
# rather than rewritten here (a second restore path would be dead, divergent code).

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
