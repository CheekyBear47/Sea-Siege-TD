#!/usr/bin/env python3
"""Regenerate the server's item->rarity table from index.html.

The hub refuses offers of basic (Common) items, which means the server has to know each
item's rarity. Rather than hand-maintain a second copy, this parses the client's own
tables and rewrites the marked block in server.py. Run it after touching the item tables:

    python tools/gen_trade_rarity.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEGIN = "# --- trading rules (generated from index.html by tools/gen_trade_rarity.py)"
END = "# --- end trading rules"

# table name in index.html -> key prefix used in the own-store ("env:dawn")
TABLES = {
    "ENVIRONMENTS": "env",
    "FLEETS": "fleet",
    "WRAPS": "wrap",
    "BANNERS": "banner",
    "FX_SKINS": "fx",
}
RARITY_RE = re.compile(r'^\s{2}([A-Za-z0-9_]+):\s*\{[^}]*?\br:\s*"(\w+)"')


def table_block(src: str, name: str) -> str:
    start = src.index(f"const {name} = {{")
    depth, i = 0, src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise ValueError(f"unterminated {name}")


def main() -> int:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for name, prefix in TABLES.items():
        for line in table_block(html, name).splitlines():
            m = RARITY_RE.match(line)
            if m:
                out[f"{prefix}:{m.group(1)}"] = m.group(2)
    # turret cards: MYTHIC_ORDER is mythic, SECRET_ORDER is the secret tier. Derived from
    # the client so a new rarity cannot drift out of this table.
    for order_name, rarity in (("MYTHIC_ORDER", "mythic"), ("SECRET_ORDER", "secret")):
        order = re.search(rf"{order_name}\s*=\s*\[([^\]]*)\]", html)
        if order:
            for key in re.findall(r'"([^"]+)"', order.group(1)):
                out[f"turret:{key}"] = rarity

    # worth points per rarity, straight from the client's RARITY table, so the global
    # leaderboard can score a profile from its own-store without a second table
    points: dict[str, int] = {}
    rarity_block = re.search(r"const RARITY = \{(.*?)\n\};", html, re.S)
    if rarity_block:
        for rk, pts in re.findall(r"(\w+):\s*\{[^}]*?pts:\s*(\d+)", rarity_block.group(1)):
            points[rk] = int(pts)
    if not points:
        print("!! could not read the RARITY table from index.html")
        return 1
    # the rarity ladder, in the client's own order: this is what decides what is tradeable
    order_match = re.search(r"RARITY_ORDER\s*=\s*\[([^\]]*)\]", html)
    rarity_order = re.findall(r'"([^"]+)"', order_match.group(1)) if order_match else list(points)
    if not rarity_order:
        print("!! could not read RARITY_ORDER from index.html")
        return 1
    item_points = {k: points.get(v, 0) for k, v in out.items()}

    server = ROOT / "server.py"
    src = server.read_text(encoding="utf-8")
    if BEGIN not in src or END not in src:
        print("!! server.py is missing the generated-block markers")
        return 1
    head, rest = src.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    lines = [
        BEGIN,
        "# item key -> rarity, used to keep basic starter gear out of trades.",
        # generated from the client's RARITY_ORDER: adding a rarity there is enough
        "RARITY_RANK = {" + ", ".join(
            f'"{rk}": {i}' for i, rk in enumerate(rarity_order)) + "}",
        f"TRADE_RARITY = {json.dumps(out, sort_keys=True)}",
        f"ITEM_POINTS = {json.dumps(item_points, sort_keys=True)}",
        "",
        "def owned_ids(save) -> dict:",
        "    \"\"\"The own-store out of a save blob: {\"env:dawn\": True, ...}.\"\"\"",
        "    cos = (save or {}).get(\"cos\") or {}",
        "    own = cos.get(\"own\") if isinstance(cos, dict) else None",
        "    return own if isinstance(own, dict) else {}",
        "",
        "def profile_worth(save) -> int:",
        "    return sum(ITEM_POINTS.get(k, 0) for k, v in owned_ids(save).items() if v)",
        "",
        "def profile_owned(save) -> int:",
        "    return sum(1 for v in owned_ids(save).values() if v)",
        "",
        "",
        "def tradeable(item_id: str) -> bool:",
        "    \"\"\"Rare and above only - sprats and starter skins never change hands.\"\"\"",
        "    return RARITY_RANK.get(TRADE_RARITY.get(str(item_id), \"\"), -1) >= RARITY_RANK[\"rare\"]",
        "",
        END,
    ]
    server.write_text(head + "\n".join(lines) + tail, encoding="utf-8")

    by_rarity: dict[str, int] = {}
    for r in out.values():
        by_rarity[r] = by_rarity.get(r, 0) + 1
    print(f"wrote {len(out)} items into server.py: " +
          ", ".join(f"{k} {v}" for k, v in sorted(by_rarity.items())))
    print("tradeable (rare+):", sum(v for k, v in by_rarity.items() if k != "common"),
          "| worth points:", points)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
