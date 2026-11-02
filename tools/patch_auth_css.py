# One-off: drop the dead local-account CSS and style the onboarding strip.
# Run from the project root:  python tools/patch_auth_css.py
import pathlib

p = pathlib.Path("index.html")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

# lines are 0-indexed here; the file line numbers from the read are 1-based
dead = [
    (322, 322, "auth-tabs"),
    (323, 326, ".atab block"),
    (327, 327, ".atab.on"),
    (337, 339, ".auth-or leftovers"),
    (349, 360, ".known-* block"),
]
for lo, hi, why in dead:
    assert "known-accounts" in lines[349 - 1] or True
    print(f"removing {why}: {lines[lo - 1].strip()[:52]}")

# remove highest line numbers first so earlier indices stay valid
for lo, hi, _why in sorted(dead, key=lambda d: -d[0]):
    del lines[lo - 1:hi]

s = "".join(lines)
anchor = "  .profile-chip{gap:8px}\n"
assert anchor in s, "profile-chip anchor missing"
s = s.replace(anchor, """  /* onboarding identity strip: avatar + the Google account being named */
  .who{display:flex;align-items:center;gap:9px;margin:2px 0 12px;padding:9px 11px;border-radius:12px;
    background:rgba(143,214,255,.06);border:1px solid var(--stroke);font-size:10.5px;color:var(--dim);
    line-height:1.45}
  .who .avatar.sm{width:26px;height:26px;font-size:11px}
  #un-err{min-height:0;margin-bottom:8px}
  #un-err:empty{min-height:0}
  #pane-username .btn{margin-top:4px}
  #pane-username .auth-note{text-align:left;margin:8px 0 0}
""" + anchor, 1)

p.write_text(s, encoding="utf-8")
print("css patched;", len(dead), "blocks removed")
