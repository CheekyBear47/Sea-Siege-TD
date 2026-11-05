# Single-reel slot machine for crates, an accordion armory, and 5 new turrets.
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


# ============================================================ 5 new turrets
sub("""const TOWER_ORDER = ["longbow", "slinger", "crossbow", "cannon", "harpoon",
                     "trebuchet", "tesla", "brazier", "mortar", "frostbite",
                     "stormcaller", "wavebreak", "sunforge", "dreadnought"];""",
    """const TOWER_ORDER = ["longbow", "slinger", "crossbow", "cannon", "harpoon",
                     "trebuchet", "tesla", "brazier", "mortar", "frostbite",
                     "stormcaller", "wavebreak", "sunforge", "dreadnought",
                     // the five added in the patch pass - appended so the number keys
                     // (which map to the first nine) do not shift under existing players
                     "flakcutter", "pike", "tidecaller", "scorpion", "obsidian"];""",
    "TOWER_ORDER")

sub("""  /* ---------- rank 5 — 2,600..3,400 gold: end-game support ---------- */""",
    """  /* ---------- the five added turrets, one per tier I-V ---------- */
  flakcutter: {
    name: "Flak Cutter", glyph: "🔫", cost: 160, rank: 1, kind: "Rapid",
    dmg: 11, rate: 1.35, range: 150, color: "#bfe3ff", desc: "cheap, quick, relentless",
    special: { name: "Flak Burst", text: "a snub fast-firer - more shots per coin than anything else." }
  },
  pike: {
    name: "Pike Battery", glyph: "🎯", cost: 430, rank: 2, kind: "Piercing",
    dmg: 38, rate: 1.9, range: 210, pierceBase: 2, color: "#9fd6ff", desc: "bolts that ignore plating",
    special: { name: "Armour Pike", text: "bolts punch through hull armour and two ships at once." }
  },
  tidecaller: {
    name: "Tidecaller Shrine", glyph: "🌀", cost: 890, rank: 3, kind: "Control",
    dmg: 62, rate: 1.6, range: 260, slow: 0.34, slowDur: 1.9, color: "#7fd0ff",
    desc: "churns the channel into a slow drag",
    special: { name: "Riptide", text: "everything it touches is dragged down to a crawl." }
  },
  scorpion: {
    name: "Scorpion Deck", glyph: "🏹", cost: 1900, rank: 4, kind: "Sniper",
    dmg: 270, rate: 2.6, range: 450, pierceBase: 3, projType: "ray", color: "#d0b8ff",
    desc: "long-range skewer, three hulls deep",
    special: { name: "Skewer Volley", text: "a single bolt that runs the length of a column." }
  },
  obsidian: {
    name: "Obsidian Battery", glyph: "🖤", cost: 5900, rank: 5, kind: "Artillery",
    dmg: 440, rate: 2.2, range: 470, projSpeed: 260, projType: "stone",
    splash: 250, minRange: 120, color: "#b9a5ff", desc: "black-glass shells, wide and final",
    special: { name: "Glassfall", text: "the blast shatters plating and leaves nothing standing in it." }
  },
  /* ---------- rank 5 — 2,600..3,400 gold: end-game support ---------- */""",
    "5 new turrets")

# ============================================================ armory accordion
sub("""function renderArmory() {
  const shop = document.getElementById("shop");
  if (!shop) return;
  shop.textContent = "";
  const section = (label, keys, cls) => {
    shop.appendChild(el("div", "sect" + (cls ? " " + cls : ""), label));
    const grid = el("div", "shop");
    keys.forEach(k => grid.appendChild(armoryCard(k)));
    shop.appendChild(grid);
  };
  [1, 2, 3, 4, 5, 6].forEach(rank => {
    const keys = TOWER_ORDER.filter(k => TOWERS[k].rank === rank);
    if (keys.length) section("Armory · " + RANK_BRACKETS[rank], keys);
  });
  section("Mythic armory · crate drops only", MYTHIC_ORDER, "mythic-sect");
}""",
    """// The armory is an accordion: one tier open at a time by default, remembering what the
// player had open, so the sidebar is a clean list of tiers instead of a wall of cards.
const ARM_KEY = "seaSiege.armory.v1";
let armOpen = {};
try { armOpen = JSON.parse(localStorage.getItem(ARM_KEY) || "{}") || {}; } catch (e) { armOpen = {}; }
function armoryIsOpen(key, dflt) {
  return armOpen[key] === undefined ? !!dflt : !!armOpen[key];
}
function toggleArmory(key) {
  armOpen[key] = !armoryIsOpen(key, false);
  try { localStorage.setItem(ARM_KEY, JSON.stringify(armOpen)); } catch (e) {}
  renderArmory();
}
function renderArmory() {
  const shop = document.getElementById("shop");
  if (!shop) return;
  shop.textContent = "";
  const section = (label, keys, cls, key, dflt) => {
    const open = armoryIsOpen(key, dflt);
    const head = el("div", "sect acc" + (cls ? " " + cls : "") + (open ? " open" : ""));
    head.appendChild(el("span", "chev", open ? "▾" : "▸"));
    head.appendChild(el("span", "acc-label", label));
    head.appendChild(el("span", "acc-count", keys.length + (keys.length === 1 ? " turret" : " turrets")));
    head.setAttribute("role", "button");
    head.title = (open ? "Hide" : "Show") + " " + label;
    head.onclick = () => toggleArmory(key);
    shop.appendChild(head);
    if (!open) return;
    const grid = el("div", "shop");
    keys.forEach(k => grid.appendChild(armoryCard(k)));
    shop.appendChild(grid);
  };
  [1, 2, 3, 4, 5, 6].forEach(rank => {
    const keys = TOWER_ORDER.filter(k => TOWERS[k].rank === rank);
    if (keys.length) section("Armory · " + RANK_BRACKETS[rank], keys, null, "r" + rank, rank === 1);
  });
  section("Mythic armory · crate drops only", MYTHIC_ORDER, "mythic-sect", "mythic", false);
}""", "armory accordion")

sub("""  .inv-selects select{max-width:190px}""",
    """  .inv-selects select{max-width:190px}
  /* accordion tiers */
  .sect.acc{display:flex;align-items:center;gap:8px;cursor:pointer;border-radius:10px;
    padding:8px 10px;margin:10px 0 6px;background:var(--glass-2);border:1px solid var(--stroke);
    -webkit-tap-highlight-color:transparent;user-select:none}
  .sect.acc:hover{background:rgba(120,180,255,.12)}
  .sect.acc .chev{font-size:11px;color:#9fd6ff;width:11px;flex:0 0 auto}
  .sect.acc .acc-label{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sect.acc .acc-count{flex:0 0 auto;font-size:9.5px;letter-spacing:.6px;color:var(--dim)}
  .sect.acc.open{border-color:rgba(143,214,255,.4)}""", "accordion css")

# ============================================================ single-reel slot
sub("""  .roll-box{text-align:center}
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
  .roll-label{font-size:13px;font-weight:800;color:#eaf6ff}""",
    """  /* single-reel slot machine: one column of tiles that spins and snaps to the win */
  .roll-box{text-align:center;display:flex;flex-direction:column;align-items:center;gap:14px}
  .reel-wrap{position:relative}
  .reel-window{
    position:relative;width:168px;height:168px;overflow:hidden;border-radius:18px;
    border:1px solid rgba(143,214,255,.32);background:linear-gradient(160deg, rgba(16,28,46,.95), rgba(6,12,22,.98));
    box-shadow:0 22px 50px rgba(0,0,0,.65), 0 0 0 6px rgba(8,16,28,.6) inset;
  }
  .reel-strip{position:absolute;left:0;right:0;top:0;display:flex;flex-direction:column;will-change:transform}
  .reel-item{
    height:168px;flex:0 0 auto;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;
    padding:10px;
  }
  .reel-item .ri-glyph{font-size:46px;line-height:1;filter:drop-shadow(0 4px 10px rgba(0,0,0,.5))}
  .reel-item .ri-name{font-size:10.5px;font-weight:800;letter-spacing:.3px;color:#cfe6ff;
    max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .reel-item.r-rare .ri-name{color:#a8d8ff}
  .reel-item.r-epic .ri-name{color:#d0b8ff}
  .reel-item.r-legendary .ri-name{color:#ffd166}
  .reel-item.r-mythic .ri-name{color:#ffb3e6}
  .reel-item.win{background:radial-gradient(circle at 50% 45%, rgba(255,255,255,.14), transparent 70%);
    animation:rollwin .5s cubic-bezier(.2,1.5,.4,1) 1;animation-fill-mode:forwards}
  @keyframes rollwin{0%{transform:scale(.8)}60%{transform:scale(1.08)}100%{transform:scale(1)}}
  .reel-payline{
    position:absolute;left:0;right:0;top:50%;height:2px;transform:translateY(-1px);
    background:linear-gradient(90deg, transparent, rgba(143,214,255,.75), transparent);
    pointer-events:none;
  }
  .reel-window::before,.reel-window::after{
    content:"";position:absolute;left:0;right:0;height:52px;pointer-events:none;z-index:2;
  }
  .reel-window::before{top:0;background:linear-gradient(180deg, rgba(6,12,22,.92), transparent)}
  .reel-window::after{bottom:0;background:linear-gradient(0deg, rgba(6,12,22,.92), transparent)}
  .roll-label{font-size:14px;font-weight:800;color:#eaf6ff;max-width:min(88vw,420px)}
  .roll-sub{font-size:11px;color:var(--dim);margin-top:-6px}""", "slot css")

sub("""    <div id="roll"><div class="roll-box">
      <div class="roll-card r-common" id="roll-card">📦</div>
      <div class="roll-label" id="roll-label">Rolling…</div>""",
    """    <div id="roll"><div class="roll-box">
      <div class="reel-wrap"><div class="reel-window">
        <div class="reel-strip" id="reel-strip"></div>
        <div class="reel-payline"></div>
      </div></div>
      <div class="roll-label" id="roll-label">Rolling…</div>
      <div class="roll-sub" id="roll-sub"></div>""", "slot markup")

sub("""function playRoll(pick, crate, duplicate, done) {
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
  const landed = () => {
    reveal();
    setTimeout(() => {
      host.classList.remove("on");
      rolling = false;
      done();
    }, 1200);
  };
  // Wall-clock, frame-driven. A tick-counting setInterval stalls on a throttled or
  // hidden page and the overlay would stay up (the drop is already in the hold).
  const started = Date.now();
  const SPIN = 1500, HOLD = 1400;
  const spray = () => {
    const it = pool[(Math.random() * pool.length) | 0];
    if (it) {
      card.textContent = it.item.glyph || "🎁";
      card.className = "roll-card spin r-" + (it.item.r || "common");
    }
  };
  const frame = () => {
    if (Date.now() - started >= SPIN) {
      clearInterval(safety);
      landed();
      return;
    }
    spray();
    requestAnimationFrame(frame);
  };""",
    """// One reel, spun on a wall clock: the strip is a column of real possible drops with the
// actual win on the end, and it eases to a stop on the payline. Frame-driven and
// time-based (a tick-counting interval stalls on a throttled tab and the drop, which is
// already committed, would sit behind a stuck overlay).
function reelTile(entry) {
  const it = entry.item || entry;
  const tile = el("div", "reel-item r-" + (it.r || "common"));
  tile.appendChild(el("span", "ri-glyph", it.glyph || (it.tint ? "🎨" : "🎁")));
  tile.appendChild(el("span", "ri-name", it.name));
  return tile;
}
function playRoll(pick, crate, duplicate, done) {
  const host = document.getElementById("roll");
  const strip = document.getElementById("reel-strip");
  const label = document.getElementById("roll-label");
  const sub = document.getElementById("roll-sub");
  const reveal = () => {
    if (label) {
      label.textContent = rarityOf(pick.item).name + " · " + pick.item.name;
    }
    if (sub) {
      sub.textContent = crate.glyph + " " + crate.name +
        (duplicate ? " · duplicate — gems refunded" : " · +" + itemWorth(pick.item) + " worth points");
    }
    sfx(pick.item.r === "mythic" || pick.item.r === "legendary" ? "win" : "gem");
  };
  if (!host || !strip) { reveal(); setTimeout(done, 900); return; }
  rolling = true;
  const pool = [];
  RARITY_ORDER.forEach(r => cratePool(r).forEach(x => pool.push(x)));
  if (label) label.textContent = "Rolling " + crate.name + "…";
  if (sub) sub.textContent = crate.gems + " 💎 spent";
  host.classList.add("on");
  const finish = () => {
    host.classList.remove("on");
    rolling = false;
    done();
  };
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const TILE = 168, RUN = 22;
  strip.textContent = "";
  strip.style.transform = "translateY(0)";
  if (reduce) {
    strip.appendChild(reelTile(pick));
    strip.firstChild.classList.add("win");
    reveal();
    setTimeout(finish, 1400);
    return;
  }
  // build the strip: filler from the real pool, then the winner in the last slot
  const filler = [];
  for (let i = 0; i < RUN; i++) {
    const it = pool[(Math.random() * pool.length) | 0];
    filler.push(it || pick);
  }
  filler.forEach(x => strip.appendChild(reelTile(x)));
  const winTile = reelTile(pick);
  strip.appendChild(winTile);
  const travel = RUN * TILE;                 // stop with the winner inside the window
  const SPIN = 2600;
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    reveal();
    clearInterval(safety);
    setTimeout(finish, 1500);
  };
  const started = Date.now();
  // Safety net: if frames stop (hidden tab, throttling), land it anyway.
  const safety = setInterval(() => { if (Date.now() - started > SPIN + 2500) close(); }, 500);
  const step = () => {
    const t = Math.min(1, (Date.now() - started) / SPIN);
    const ease = 1 - Math.pow(1 - t, 3.1);   // decelerate into the payline
    strip.style.transform = "translateY(" + (-travel * ease).toFixed(1) + "px)";
    if (t >= 1) { winTile.classList.add("win"); close(); return; }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);""", "slot animation")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
