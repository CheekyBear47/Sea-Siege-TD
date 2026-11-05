# 1. Runs reach the server immediately (and survive a tab close); the global board stops
#    serving a 20s-stale cache.
# 2. Flak Cutter and Pike Battery actually damage things, scaled to their tier.
# 3. Longbow Nest upgrade scaling tamed.
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


# ================================================= 1. leaderboard / run saving
sub("""  bumpAccountStats({ runs: 1, bestWave: G.wave });
  saveGame();
  renderTopBar();
  return entry;""",
    """  bumpAccountStats({ runs: 1, bestWave: G.wave });
  saveGame();
  renderTopBar();
  // Push the finished run at once. bumpAccountStats queues a push on a 1.5s debounce and
  // the heartbeat covers it within 15s, but a run that ends as the player leaves should
  // not be the one that goes missing. If the board is open, show the new row immediately.
  pushSoon(250);
  if (document.getElementById("board").classList.contains("on")) renderBoardOverlay();
  return entry;""", "recordRun push")

sub("""window.addEventListener("beforeunload", () => {
  try { netLeave(); } catch (e) {}
  if (switchingProfile) return;
  try { recordRun(); saveGame(); } catch (e) {}
});""",
    """window.addEventListener("beforeunload", () => {
  try { netLeave(); } catch (e) {}
  if (switchingProfile) return;
  // Order matters. The other beforeunload listener (registered earlier, for the save
  // beacon) fires FIRST, so its payload predates this run - the run has to be recorded
  // and then beaconed again from here or a tab closed at the end of a run never reaches
  // the server's board at all.
  try { recordRun(); saveGame(); beaconProfile(); } catch (e) {}
});""", "unload order")

sub("""  if (globalBoard && !force && Date.now() - globalBoard.at < 20000) return;""",
    """  // Was 20s, which meant a finished run could be missing from the global tab for a third
  // of a minute. Opening the board forces a fetch anyway; this is just the floor for
  // re-renders that happen to run back to back.
  if (globalBoard && !force && Date.now() - globalBoard.at < 3000) return;""", "board cache")

sub("""function showBoard(on) {
  const visible = on !== false;
  if (visible) closeOverlays("board");
  document.getElementById("board").classList.toggle("on", visible);
  if (visible) renderBoardOverlay();""",
    """function showBoard(on) {
  const visible = on !== false;
  if (visible) closeOverlays("board");
  document.getElementById("board").classList.toggle("on", visible);
  if (visible) { loadGlobalBoard(true); renderBoardOverlay(); }   // always fresh on open""",
    "showBoard force")

# ================================================= 2. tower damage repairs
sub("""  flakcutter: {
    name: "Flak Cutter", glyph: "🔫", cost: 160, rank: 1, kind: "Rapid",
    dmg: 0, rate: 1.35, range: 150, color: "#bfe3ff", desc: "a fast hull that deals no damage",
    special: { name: "Flak Burst", text: "fires fast and often, but its shots carry no damage." }
  },""",
    """  flakcutter: {
    name: "Flak Cutter", glyph: "🔫", cost: 160, rank: 1, kind: "Rapid",
    dmg: 11, rate: 0.45, range: 150, projType: "bolt", color: "#bfe3ff",
    desc: "a rapid, cheap hull that chews through light ships",
    special: { name: "Flak Burst", text: "fires twice as fast as anything else in its tier." }
  },""", "flakcutter")

sub("""  pike: {
    name: "Pike Battery", glyph: "🎯", cost: 430, rank: 2, kind: "Piercing",
    dmg: 38, rate: 1.9, range: 210, pierceBase: 2, color: "#9fd6ff", desc: "bolts that ignore plating",""",
    """  pike: {
    name: "Pike Battery", glyph: "🎯", cost: 430, rank: 2, kind: "Piercing",
    dmg: 62, rate: 1.6, range: 210, pierceBase: 2, pierceArmor: true, projType: "bolt",
    color: "#9fd6ff", desc: "bolts that ignore plating",""", "pike")

sub("""  /* ---- ballistic: bolt / arrow / shell / stone ---- */
  const isBoltLike = b.projType === "bolt" || b.projType === "arrow";
  muzzle(t, ang);
  sfx(isBoltLike ? (b.projType === "arrow" ? "arrow" : "bolt") : (b.projType === "stone" ? "trebuchet" : "cannon"), t.x, t.y);""",
    """  /* ---- ballistic: bolt / arrow / shell / stone ---- */
  // An unset projType used to fall through to the lobbed-shell branch, which only hurts
  // anything via `splash` - so a turret with no projType silently dealt NOTHING. That is
  // exactly how the Flak Cutter and Pike Battery ended up inert. Never let it be unset.
  const ballKind = b.projType || (b.splash ? "shell" : "bolt");
  const isBoltLike = ballKind === "bolt" || ballKind === "arrow";
  muzzle(t, ang);
  sfx(isBoltLike ? (ballKind === "arrow" ? "arrow" : "bolt") : (ballKind === "stone" ? "trebuchet" : "cannon"), t.x, t.y);""",
    "ballistic default")

sub("""      kind: b.projType, x: t.x + Math.cos(a) * 20, y: t.y + Math.sin(a) * 20,""",
    """      kind: ballKind, x: t.x + Math.cos(a) * 20, y: t.y + Math.sin(a) * 20,""", "proj kind")

# ================================================= 3. Longbow Nest nerf
sub("""  longbow: {""",
    """  longbow: {
    grow: 0.55,""", "longbow grow")

sub("""  const s = t.st;
  const dmg = b.dmg * (1 + 0.26 * s.dmg) * (1 + 0.22 * (t.tier - 1)) * gD;
  const rate = b.rate / ((1 + 0.16 * s.rate) * (1 + 0.14 * (t.tier - 1)) * gF);
  const range = b.range * (1 + 0.13 * s.range) * (1 + 0.08 * (t.tier - 1)) * gR;""",
    """  const s = t.st;
  // `grow` scales how hard upgrades bite for a given turret. Any tower that multiplies its
  // own damage - extra arrows, stacked pierce - compounds on top of the shared upgrade
  // curve, so it needs a lower factor to stay on the ladder instead of running away with
  // it. The Longbow Nest (3 arrows with a special, and pierce on every tier) is the case
  // that prompted this: full upgrades made one 110-gold tier-I turret out-damage the whole
  // tier-III board.
  const grow = b.grow || 1;
  const dmg = b.dmg * (1 + 0.26 * s.dmg * grow) * (1 + 0.22 * (t.tier - 1) * grow) * gD;
  const rate = b.rate / ((1 + 0.16 * s.rate * grow) * (1 + 0.14 * (t.tier - 1) * grow) * gF);
  const range = b.range * (1 + 0.13 * s.range) * (1 + 0.08 * (t.tier - 1)) * gR;""",
    "towerStats grow")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
