"""
Usage: python merge.py spells
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

merge_dir = Path(__file__).parents[1] / "data" / sys.argv[1]
out = defaultdict(list)

for fp in Path(merge_dir).glob(f"{merge_dir.name}-*.json"):
    with open(fp) as f:
        data = json.load(f)
        for k, v in data.items():
            if isinstance(v, list):
                out[k].extend(v)

with open(f"{merge_dir.name}-merged.json", "w") as f:
    json.dump(out, f, indent=2)
