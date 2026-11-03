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
    # mythic turret cards: every entry in TURRET_CARDS is mythic, keyed "turret:<id>"
    order = re.search(r"MYTHIC_ORDER\s*=\s*\[([^\]]*)\]", html)
    if order:
        for key in re.findall(r'"([^"]+)"', order.group(1)):
            out[f"turret:{key}"] = "mythic"

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
        "RARITY_RANK = {\"common\": 0, \"rare\": 1, \"epic\": 2, \"legendary\": 3, \"mythic\": 4}",
        f"TRADE_RARITY = {json.dumps(out, sort_keys=True)}",
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
    print("tradeable (rare+):", sum(v for k, v in by_rarity.items() if k != "common"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
