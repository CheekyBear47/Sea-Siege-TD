# THE actual reason Flak Cutter / Pike Battery / Tidecaller dealt nothing: they had no
# `projSpeed`, so the spawned projectile's speed was undefined, `step = speed * dt` was
# NaN, its position went NaN, the hit test could never be true - and it never expired
# either, so the NaN shots piled up in the array. Every tower that works has a projSpeed.
import pathlib
import re

p = pathlib.Path("index.html")
s = p.read_text(encoding="utf-8")
miss = []


def sub(old, new, why=""):
    global s
    if old not in s:
        miss.append(why or old[:70])
        return
    s = s.replace(old, new, 1)


# 1. give the three towers a projectile speed (and the flak a matching look/feel)
sub("""    dmg: 11, rate: 0.45, range: 150, projType: "bolt", color: "#bfe3ff",""",
    """    dmg: 11, rate: 0.45, range: 150, projType: "bolt", projSpeed: 900, color: "#bfe3ff",""",
    "flakcutter projSpeed")

sub("""    dmg: 62, rate: 1.6, range: 210, pierceBase: 2, pierceArmor: true, projType: "bolt",""",
    """    dmg: 62, rate: 1.6, range: 210, pierceBase: 2, pierceArmor: true, projType: "bolt",
    projSpeed: 880,""", "pike projSpeed")

sub("""    dmg: 62, rate: 1.6, range: 260, color: "#63d6ff",""",
    """    dmg: 62, rate: 1.6, range: 260, projType: "bolt", projSpeed: 760, color: "#63d6ff",""",
    "tidecaller")

# 2. never let a projectile be NaN again - a missing speed must not silently mean
#    "cannot hit anything and never expires"
sub("""      speed: st.projSpeed, travel: 0, total: Math.max(sp, 1),""",
    """      speed: st.projSpeed || 760, travel: 0, total: Math.max(sp, 1),
      // Guard: a tower with no projSpeed used to spawn projectiles whose speed was
      // undefined, so `step = speed * dt` was NaN, their position went NaN, the hit test
      // was never true and `travel > total + 90` was never true either - an invisible,
      // immortal, harmless shot. Default the speed so that cannot happen.""",
    "projSpeed guard")

p.write_text(s, encoding="utf-8")
print("missed anchors:", miss if miss else "none")

# 3. report every remaining ballistic tower that still has no projSpeed
table = s[s.index("const TOWERS = {"):s.index("const TURRETS")]
non_ballistic = ("flame", "ray", "frost", "harpoon", "tesla")
bad = []
for m in re.finditer(r"\n  (\w+): \{(.*?)\n  \},", table, re.S):
    name, body = m.group(1), m.group(2)

    def field(f, b=body):
        mm = re.search(f + r":\s*([^,\n]+)", b)
        return mm.group(1).strip() if mm else None

    pt, ps = field("projSpeed"), None
    kind = field("projType")
    if kind and kind.strip('"') in non_ballistic:
        continue                      # cone/beam/pulse towers spawn no projectile
    ps = field("projSpeed")
    if not ps:
        bad.append(name)
print("ballistic towers still missing projSpeed:", bad if bad else "none - all covered")
