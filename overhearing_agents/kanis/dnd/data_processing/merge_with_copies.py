import json
import re
from pathlib import Path

monsters = []
monsters_by_name_and_source = {}
templates_by_name_and_source = {}
BESTIARY_DIR = Path(__file__).parents[1] / "data/bestiary"

# load them all
for fp in BESTIARY_DIR.glob(f"bestiary-*.json"):
    with open(fp) as f:
        data = json.load(f)
        for monster in data["monster"]:
            monsters_by_name_and_source[(monster["name"].lower(), monster["source"])] = monster
            monsters.append(monster)
with open(BESTIARY_DIR / "template.json") as f:
    for t in json.load(f)["monsterTemplate"]:
        templates_by_name_and_source[(t["name"].lower(), t["source"])] = t


# ==== operations (inplace) ====
def apply_template(mon, template):
    template_mon = templates_by_name_and_source[(template["name"].lower(), template["source"])]
    if "_copy" in template_mon:
        copy_details = template_mon.pop("_copy")
        template_mon_src = templates_by_name_and_source[(copy_details["name"].lower(), copy_details["source"])]
        template_mon = {**template_mon_src, **template_mon}
        # run replacements
        for field, op in copy_details.get("_mod", {}).items():
            # print(field, op)
            apply_op(template_mon, field, op)
        templates_by_name_and_source[(template["name"].lower(), template["source"])] = template_mon

    apps = template_mon["apply"]
    for k, v in apps.get("_root", {}).items():
        mon[k] = v
    for field, mod in apps.get("_mod", {}).items():
        apply_op(mon, field, mod)


def apply_op(mon, field, op):
    if isinstance(op, list):
        for o in op:
            apply_op(mon, field, o)
        return
    if field == "*":
        for f in mon:
            apply_op(mon, f, op)
        return

    match op:
        # prop ops
        case {"mode": "replaceTxt", "replace": frm, "with": to}:
            if field not in mon:
                return
            # little hacky but oh well idc
            flags = op.get("flags", "")
            mon[field] = json.loads(re.sub(f"(?{flags}:{frm})", to, json.dumps(mon[field])))
        case {"mode": "setProp", "prop": prop_path, "value": value}:
            *parents, final = prop_path.split(".")
            parent_obj = mon
            for parent in parents:
                parent_obj = parent_obj[parent]
            parent_obj[final] = value
        # array ops
        case {"mode": "replaceArr", "replace": name, "items": repl}:
            new_field = []
            for item in mon[field]:
                if item["name"] == name:
                    if isinstance(repl, list):
                        new_field.extend(repl)
                    else:
                        new_field.append(repl)
                else:
                    new_field.append(item)
            mon[field] = new_field
        case {"mode": "appendArr", "items": repl}:
            if field not in mon:
                mon[field] = []
            if isinstance(repl, list):
                mon[field].extend(repl)
            else:
                mon[field].append(repl)
        case {"mode": "prependArr", "items": repl}:
            if field not in mon:
                mon[field] = []
            if isinstance(repl, list):
                mon[field] = repl + mon[field]
            else:
                mon[field].insert(0, repl)
        case {"mode": "insertArr", "index": insert_idx, "items": repl}:
            if field not in mon:
                mon[field] = []
            if isinstance(repl, list):
                mon[field] = mon[field][:insert_idx] + repl + mon[field][insert_idx:]
            else:
                mon[field].insert(insert_idx, repl)
        case {"mode": "appendIfNotExistsArr", "items": repl}:
            if field not in mon:
                mon[field] = []
            if isinstance(repl, list):
                mon[field].extend([r for r in repl if r not in mon[field]])
            elif repl not in mon[field]:
                mon[field].append(repl)
        case {"mode": "removeArr", "names": name}:
            if isinstance(name, list):
                mon[field] = [i for i in mon[field] if i["name"] not in name]
            else:
                mon[field] = [i for i in mon[field] if i["name"] != name]
        case {"mode": "removeArr", "items": name}:
            if isinstance(name, list):
                mon[field] = [i for i in mon[field] if i not in name]
            else:
                mon[field] = [i for i in mon[field] if i != name]
        # field ops
        case "remove":
            mon.pop(field)
        case _:
            print("UNHANDLED MOD OP:", op)


def do_copy(mon):
    print(f"===== Copying to {mon['name']} =====")
    copy_details = mon.pop("_copy")
    # print(copy_details)
    # copy from base
    source_mon = monsters_by_name_and_source[(copy_details["name"].lower(), copy_details["source"])]
    out = {**source_mon, **mon}
    # apply templates
    for template in copy_details.get("_templates", []):
        apply_template(mon, template)
    # run replacements
    for field, op in copy_details.get("_mod", {}).items():
        # print(field, op)
        apply_op(out, field, op)
    return out


for idx, monster in enumerate(monsters):
    if "_copy" in monster:
        monsters[idx] = do_copy(monster)

# write result
with open("monsters-merged.json", "w") as f:
    json.dump({"monster": monsters}, f, indent=2)
