#!/usr/bin/env python3
"""Refuse records that duplicate something already in the registry.

Usage:  python scripts/check_duplicates.py                    # whole tree
        python scripts/check_duplicates.py --base origin/main # mark which side is new
        python scripts/check_duplicates.py --strict           # warnings also fail

Runs in CI before merge. Exit 1 on any error (or on warnings with --strict).

What counts as a duplicate
  sites      same host (case, `www.`, trailing dot ignored) and path scope in two files
  traces     same URL (scheme, `www.`, trailing slash, fragment ignored) in two places;
             same `key` twice on one host
  incidents  same name; disclosed on the same day by the same party about an
             overlapping set of hosts
  campaigns  same name
  tasks      same name
Warnings (not fatal unless --strict) flag near-misses a reviewer should look at:
  similar names, a source URL cited by two incidents, two incidents whose
  hosts, campaigns and period all overlap.

With --base REF, records absent from REF are labelled NEW so a PR review can
see at a glance that the new record is the one duplicating an existing one.
"""
import argparse
import datetime
import difflib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("sites", "campaigns", "tasks", "incidents")
NAME_SIMILAR = 0.85  # difflib ratio at which two names are flagged

errors: list[str] = []
warnings: list[str] = []


# --- normalisation ---------------------------------------------------------
def norm_host(h: str) -> str:
    h = (h or "").strip().lower().rstrip(".")
    return h[4:] if h.startswith("www.") else h


def norm_scope(s) -> str:
    s = (s or "").strip()
    return "/" + s.strip("/") if s else ""


def norm_url(u: str) -> str:
    """Canonical form for comparing URLs, not for display."""
    p = urlsplit((u or "").strip())
    host = norm_host(p.hostname or "")
    if p.port and p.port not in (80, 443):
        host = f"{host}:{p.port}"
    path = unquote(p.path or "").rstrip("/")
    q = f"?{p.query}" if p.query else ""
    return f"{host}{path}{q}".lower()


def norm_name(n: str) -> str:
    n = (n or "").lower()
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def site_id(s: dict) -> str:
    return norm_host(s.get("host", "")) + norm_scope(s.get("path_scope"))


def to_date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str) and v:
        parts = (v.split("T")[0] + "-01-01").split("-")[:3]
        try:
            return datetime.date(*map(int, parts))
        except ValueError:
            return None
    return None


def period_overlaps(a: dict, b: dict) -> bool:
    a0, a1 = to_date(a.get("start")), to_date(a.get("end"))
    b0, b1 = to_date(b.get("start")), to_date(b.get("end"))
    if not (a0 and b0):
        return False
    a1, b1 = a1 or datetime.date.max, b1 or datetime.date.max
    return a0 <= b1 and b0 <= a1


# --- loading ----------------------------------------------------------------
def load_tree(base: str | None):
    """{dir: {relpath: doc}} from the working tree, or from git ref `base`."""
    out = {d: {} for d in DIRS}
    if base is None:
        for d in DIRS:
            for f in sorted((ROOT / d).glob("*.yaml")):
                out[d][f"{d}/{f.name}"] = yaml.safe_load(f.read_text()) or {}
        return out
    ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", base, "--", *DIRS],
                        cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for rel in ls:
        if not rel.endswith(".yaml"):
            continue
        d = rel.split("/")[0]
        blob = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout
        out[d][rel] = yaml.safe_load(blob) or {}
    return out


# --- checks -----------------------------------------------------------------
def pair(a, b, new: set) -> str:
    tag = lambda p: f"NEW {p}" if p in new else p
    return f"{tag(a)} ↔ {tag(b)}"


def check_sites(sites: dict, new: set):
    by_id = defaultdict(list)
    for rel, s in sites.items():
        by_id[site_id(s)].append(rel)
    for sid, rels in by_id.items():
        for a, b in zip(rels, rels[1:]):
            errors.append(f"{pair(b, a, new)}: both describe site '{sid}'")

    url_seen: dict[str, tuple[str, int]] = {}
    key_seen: dict[tuple[str, str], tuple[str, int]] = {}
    for rel, s in sites.items():
        host = norm_host(s.get("host", ""))
        for i, t in enumerate(s.get("traces") or []):
            u = norm_url(t.get("url", ""))
            if u:
                if u in url_seen:
                    prev, j = url_seen[u]
                    errors.append(f"{pair(rel, prev, new)}: traces[{i}] and traces[{j}] "
                                  f"record the same URL {t.get('url')}")
                else:
                    url_seen[u] = (rel, i)
            k = t.get("key")
            if k:
                kk = (host, str(k).strip())
                if kk in key_seen:
                    prev, j = key_seen[kk]
                    errors.append(f"{pair(rel, prev, new)}: traces[{i}] and traces[{j}] "
                                  f"share key '{k}' on {host}")
                else:
                    key_seen[kk] = (rel, i)


def check_names(records: dict, label: str, new: set):
    items = [(rel, norm_name(d.get("name") or d.get("id") or "")) for rel, d in records.items()]
    for i, (ra, na) in enumerate(items):
        for rb, nb in items[i + 1:]:
            if not (na and nb):
                continue
            if na == nb:
                errors.append(f"{pair(rb, ra, new)}: identical {label} name '{na}'")
            else:
                r = difflib.SequenceMatcher(None, na, nb).ratio()
                if r >= NAME_SIMILAR:
                    warnings.append(f"{pair(rb, ra, new)}: {label} names are {r:.0%} similar")


def check_incidents(incidents: dict, new: set):
    check_names(incidents, "incident", new)
    src_seen: dict[str, str] = {}
    items = list(incidents.items())
    for rel, inc in items:
        for s in inc.get("sources") or []:
            u = norm_url(s.get("url", ""))
            if not u:
                continue
            if u in src_seen and src_seen[u] != rel:
                warnings.append(f"{pair(rel, src_seen[u], new)}: both cite {s.get('url')} "
                                f"— confirm these are distinct incidents")
            src_seen.setdefault(u, rel)
    for i, (ra, a) in enumerate(items):
        for rb, b in items[i + 1:]:
            hosts = {norm_host(h.split('/')[0]) + norm_scope('/'.join(h.split('/')[1:]))
                     for h in a.get("affected_hosts") or []} & \
                    {norm_host(h.split('/')[0]) + norm_scope('/'.join(h.split('/')[1:]))
                     for h in b.get("affected_hosts") or []}
            same_disclosure = (to_date(a.get("disclosed_on")) == to_date(b.get("disclosed_on"))
                               and norm_name(a.get("disclosed_by")) == norm_name(b.get("disclosed_by")))
            if same_disclosure and hosts:
                errors.append(f"{pair(rb, ra, new)}: disclosed on the same day by the same party "
                              f"about the same hosts {sorted(hosts)}")
                continue
            camps = set(a.get("campaigns") or []) & set(b.get("campaigns") or [])
            if hosts and camps and period_overlaps(a.get("period") or {}, b.get("period") or {}):
                warnings.append(f"{pair(rb, ra, new)}: overlapping hosts {sorted(hosts)}, "
                                f"campaigns {sorted(camps)} and period — same event?")


def check_campaigns(campaigns: dict, new: set):
    check_names(campaigns, "campaign", new)
    src_seen: dict[str, str] = {}
    for rel, c in campaigns.items():
        for s in c.get("primary_sources") or []:
            u = norm_url(s.get("url", ""))
            if u and u in src_seen and src_seen[u] != rel:
                warnings.append(f"{pair(rel, src_seen[u], new)}: both cite {s.get('url')} "
                                f"as a primary source — one campaign or two?")
            if u:
                src_seen.setdefault(u, rel)


# --- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="git ref to compare against; records not in it are labelled NEW")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    tree = load_tree(None)
    new: set[str] = set()
    if args.base:
        try:
            base = load_tree(args.base)
        except subprocess.CalledProcessError as e:
            print(f"cannot read git ref {args.base!r}: {e.stderr.strip()}", file=sys.stderr)
            return 2
        for d in DIRS:
            new |= set(tree[d]) - set(base[d])

    check_sites(tree["sites"], new)
    check_incidents(tree["incidents"], new)
    check_campaigns(tree["campaigns"], new)
    check_names(tree["tasks"], "task", new)

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    n = sum(len(m) for m in tree.values())
    fail = errors or (args.strict and warnings)
    if fail:
        print(f"\n{len(errors)} duplicate(s), {len(warnings)} warning(s) across {n} records.")
        return 1
    tail = f", {len(warnings)} warning(s)" if warnings else ""
    print(f"OK — no duplicates across {n} records"
          + (f" ({len(new)} new vs {args.base})" if args.base else "") + f"{tail}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
