#!/usr/bin/env python3
"""Validate every record against its schema and check cross-references.

Usage:  python scripts/validate.py            # whole repo
        python scripts/validate.py sites/x.yaml
Exit code 1 on any error. Uses `jsonschema` if installed; otherwise a built-in
subset checker (required / enum / type / additionalProperties / pattern / minItems).
"""
import json, re, sys, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
    "sites": "site.schema.json",
    "campaigns": "campaign.schema.json",
    "tasks": "task.schema.json",
    "incidents": "incident.schema.json",
}
errors: list[str] = []


def err(path, msg):
    errors.append(f"{path.relative_to(ROOT)}: {msg}")


# --- schema validation -----------------------------------------------------
def load_schema(name):
    return json.loads((ROOT / "schema" / name).read_text())


try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    def validate_schema(path, doc, schema_name):
        registry = Registry()
        for f in (ROOT / "schema").glob("*.json"):
            s = json.loads(f.read_text())
            registry = registry.with_resource(s["$id"], Resource.from_contents(s))
        v = Draft202012Validator(load_schema(schema_name), registry=registry,
                                 format_checker=Draft202012Validator.FORMAT_CHECKER)
        for e in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
            loc = "/".join(str(p) for p in e.path) or "<root>"
            err(path, f"{loc}: {e.message}")

except ImportError:  # minimal fallback so the repo validates offline
    _defs_cache = {}

    def _resolve(ref, schema):
        if ref.startswith("#/$defs/"):
            return schema["$defs"][ref.split("/")[-1]], schema
        s = load_schema(ref)
        return s, s

    def _check(doc, sch, root, path, loc):
        if "$ref" in sch:
            sch, root = _resolve(sch["$ref"], root)
        t = sch.get("type")
        types = t if isinstance(t, list) else ([t] if t else [])
        pymap = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None), "integer": int}
        if types and not any(isinstance(doc, pymap[x]) for x in types):
            err(path, f"{loc}: expected {types}, got {type(doc).__name__}")
            return
        if "enum" in sch and doc not in sch["enum"]:
            err(path, f"{loc}: {doc!r} not in {sch['enum']}")
        if isinstance(doc, str) and "pattern" in sch and not re.search(sch["pattern"], doc):
            err(path, f"{loc}: {doc!r} does not match {sch['pattern']}")
        if isinstance(doc, str) and sch.get("format") == "date" and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", doc):
            err(path, f"{loc}: {doc!r} is not a date")
        if isinstance(doc, dict):
            for r in sch.get("required", []):
                if r not in doc:
                    err(path, f"{loc}: missing required '{r}'")
            props = sch.get("properties", {})
            addl = sch.get("additionalProperties", True)
            for k, v in doc.items():
                if k in props:
                    _check(v, props[k], root, path, f"{loc}/{k}")
                elif addl is False:
                    err(path, f"{loc}: unexpected key '{k}'")
                elif isinstance(addl, dict):
                    _check(v, addl, root, path, f"{loc}/{k}")
        if isinstance(doc, list):
            if len(doc) < sch.get("minItems", 0):
                err(path, f"{loc}: fewer than {sch['minItems']} items")
            for i, item in enumerate(doc):
                _check(item, sch.get("items", {}), root, path, f"{loc}[{i}]")

    def validate_schema(path, doc, schema_name):
        s = load_schema(schema_name)
        _check(doc, s, s, path, "<root>")


# --- load everything --------------------------------------------------------
def load_dir(d):
    out = {}
    for f in sorted((ROOT / d).glob("*.yaml")):
        with f.open() as fh:
            out[f] = yaml.safe_load(fh)
    return out


records = {d: load_dir(d) for d in SCHEMAS}

# YAML turns unquoted dates into date objects; normalise back to ISO strings
def normalise(o):
    if isinstance(o, dict):
        return {k: normalise(v) for k, v in o.items()}
    if isinstance(o, list):
        return [normalise(v) for v in o]
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat().replace("+00:00", "Z")
    return o

records = {d: {p: normalise(v) for p, v in m.items()} for d, m in records.items()}

only = [Path(a).resolve() for a in sys.argv[1:]]
for d, schema in SCHEMAS.items():
    for path, doc in records[d].items():
        if only and path not in only:
            continue
        validate_schema(path, doc, schema)

# --- cross-references & conventions ----------------------------------------
campaign_ids = {d["id"] for d in records["campaigns"].values()}
task_ids = {d["id"] for d in records["tasks"].values()}
incident_ids = {d["id"] for d in records["incidents"].values()}
site_ids = set()

for path, s in records["sites"].items():
    host, scope = s.get("host", ""), s.get("path_scope")
    site_id = host + (scope or "")
    site_ids.add(site_id)
    expected = host + ("__" + scope.strip("/").split("/")[-1] if scope else "") + ".yaml"
    if path.name != expected:
        err(path, f"filename should be {expected}")
    for c in s.get("campaigns", []):
        if c not in campaign_ids:
            err(path, f"unknown campaign '{c}'")
    fs, ls = s.get("first_seen"), s.get("last_seen")
    if fs and ls and fs > ls:
        err(path, "first_seen is after last_seen")
    for i, t in enumerate(s.get("traces", [])):
        tc = t.get("task_cluster")
        if tc and tc not in task_ids:
            err(path, f"traces[{i}]: unknown task_cluster '{tc}'")
        if t.get("attribution", {}).get("confidence") == "unattributed" and s.get("campaigns"):
            pass  # allowed: site attributed, single trace not
        if t.get("attribution", {}).get("confidence") == "confirmed" and \
           "developer_disclosure" not in t["attribution"]["evidence"]:
            err(path, f"traces[{i}]: 'confirmed' requires developer_disclosure evidence")

for kind, ids_field, target in [("campaigns", "task_clusters", task_ids),
                                ("campaigns", "related_campaigns", campaign_ids),
                                ("campaigns", "related_incidents", incident_ids),
                                ("tasks", "campaigns", campaign_ids),
                                ("incidents", "campaigns", campaign_ids),
                                ("incidents", "affected_hosts", site_ids)]:
    for path, d in records[kind].items():
        if path.stem != d.get("id"):
            err(path, f"filename should be {d.get('id')}.yaml")
        for ref in d.get(ids_field, []) or []:
            if ref not in target:
                err(path, f"{ids_field}: unknown id '{ref}'")

# --- report -----------------------------------------------------------------
n = sum(len(m) for m in records.values())
traces = sum(len(s.get("traces", [])) for s in records["sites"].values())
if errors:
    print("\n".join(errors))
    print(f"\n{len(errors)} error(s) across {n} records.")
    sys.exit(1)
print(f"OK — {n} records ({len(records['sites'])} sites, {traces} traces) valid.")
