import collections
import csv
import json

annotations = collections.defaultdict(list)

with open("../annotations/Starless Lands Data - Notated Stopwatch.tsv") as f:
    rd = csv.DictReader(f, delimiter="\t", quotechar='"')
    key = None
    for row in rd:
        if row["cumulative"].startswith("starless"):
            key = row["cumulative"]
            continue
        time = float(row["seconds"])
        strings = [s.strip() for s in row["strict match strings"].split(",")]
        if not strings:
            continue
        annotations[key].append({"time": time, "matches": strings})

with open("gold-stopwatch.json", "w") as f:
    json.dump(annotations, f, indent=2)
