# Pass A2: clear the two leftovers from pass A (dangling difficulty-handler body,
# and the endless checkbox wiring) and wire the repair button.
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


# the old difficulty dropdown handler lost its head; its body was left dangling
sub("""  const fresh = applyDifficultyEconomy();
  sfx("coin");
  banner("Difficulty · " + d.label, "#8fd6ff");
  toast(fresh
    ? "Difficulty → " + d.label + ": " + d.startGold + " 🪙 and " + d.lives + " lives, and the fleet is " +
      (d.hp > 1 ? "tougher" : d.hp < 1 ? "softer" : "unchanged") + " (×" + d.hp.toFixed(2) + " hp, ×" +
      d.gold.toFixed(2) + " gold)."
    : "Difficulty → " + d.label + ": ships spawning from now on use ×" + d.hp.toFixed(2) + " hp, ×" +
      d.gold.toFixed(2) + " gold. Your current run keeps its " + G.gold + " 🪙 and " + G.lives +
      " lives — press Play Again for a fresh " + d.startGold + " 🪙 / " + d.lives + " lives start.");
  ui();
};
""", "", "dangling diff handler body")

# the endless checkbox is gone - this handler (and the flag) go with it
sub("""document.getElementById("endless").onchange = e => {
  G.endless = e.target.checked;
  toast(G.endless ? "Endless mode: breaches no longer cost lives." : "Endless mode off — lives count again.");
};""",
    """document.getElementById("repair-btn").onclick = () => buyRepair();""", "endless handler")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")
