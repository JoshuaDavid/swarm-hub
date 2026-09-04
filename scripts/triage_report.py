#!/usr/bin/env python3
"""Check a 'Report a site' issue against the registry before anyone triages it.

Reads the issue body (GitHub issue-form markdown) from stdin and prints a
Markdown comment saying whether the host, path scope, or any listed trace URL
is already recorded. Exit code is always 0 — this informs, it does not block.

    python scripts/triage_report.py < body.md
    python scripts/triage_report.py --github-output "$GITHUB_OUTPUT" < body.md

With --github-output, writes `duplicate=true|false` for the workflow to label on.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_duplicates import norm_host, norm_scope, norm_url  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EMPTY = {"", "_no response_", "none", "n/a", "-", "—"}


def fields(body: str) -> dict[str, str]:
    """Issue forms render as '### Label\\n\\nvalue' blocks."""
    out = {}
    for m in re.finditer(r"^###\s+(.+?)\s*\n(.*?)(?=^###\s|\Z)", body, re.S | re.M):
        out[m.group(1).strip().lower()] = m.group(2).strip()
    return out


def field(fs: dict, prefix: str) -> str:
    for k, v in fs.items():
        if k.startswith(prefix.lower()):
            return "" if v.strip().lower() in EMPTY else v.strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--github-output")
    args = ap.parse_args()
    fs = fields(sys.stdin.read())

    host = norm_host(re.sub(r"^https?://", "", field(fs, "host")).split("/")[0])
    scope = norm_scope(field(fs, "path scope"))
    trace_urls = [norm_url(m.group(0)) for line in field(fs, "traces").splitlines()
                  for m in [re.search(r"https?://\S+", line)] if m]

    sites = {}
    for f in sorted((ROOT / "sites").glob("*.yaml")):
        sites[f"sites/{f.name}"] = yaml.safe_load(f.read_text()) or {}

    exact, same_host, url_hits = [], [], []
    for rel, s in sites.items():
        h, sc = norm_host(s.get("host", "")), norm_scope(s.get("path_scope"))
        if h != host:
            continue
        (exact if sc == scope else same_host).append((rel, s))
        known = {norm_url(t.get("url", "")): t for t in s.get("traces") or []}
        for u in trace_urls:
            if u in known:
                url_hits.append((rel, known[u].get("url")))

    incident_hits = []
    for f in sorted((ROOT / "incidents").glob("*.yaml")):
        inc = yaml.safe_load(f.read_text()) or {}
        for ah in inc.get("affected_hosts") or []:
            if norm_host(ah.split("/")[0]) == host:
                incident_hits.append((f"incidents/{f.name}", inc.get("name", "")))
                break

    dup = bool(exact or url_hits)
    lines = ["<!-- triage-report -->", "**Prior-report check**", ""]
    if not host:
        lines.append("Could not read a host from this report — a maintainer will check by hand.")
    elif exact:
        rel, s = exact[0]
        n = len(s.get("traces") or [])
        st = (s.get("status") or {}).get("state", "unknown")
        lines.append(f"⚠️ `{host}{scope}` is **already in the registry**: [`{rel}`]({rel}) "
                     f"({n} trace{'s' if n != 1 else ''}, status `{st}`, last seen {s.get('last_seen', '?')}).")
        lines.append("If you have traces that are not in that file, a maintainer will add them there instead of opening a new record.")
    else:
        lines.append(f"✅ No existing record for `{host}{scope}`.")
    if same_host:
        others = ", ".join(f"[`{r}`]({r})" for r, _ in same_host)
        lines.append(f"Other scopes on this host are already recorded: {others}.")
    if url_hits:
        lines.append("")
        lines.append("These trace URLs are already recorded:")
        lines += [f"- {u} — in [`{rel}`]({rel})" for rel, u in url_hits]
    elif trace_urls:
        lines.append(f"None of the {len(trace_urls)} trace URL(s) listed is already recorded.")
    if incident_hits:
        lines.append("")
        lines.append("Related disclosed incidents naming this host: "
                     + ", ".join(f"[`{r}`]({r}) ({n})" for r, n in incident_hits) + ".")
    lines += ["", "_Automated check by `scripts/triage_report.py`; a maintainer still reviews every report._"]
    print("\n".join(lines))

    if args.github_output:
        with open(args.github_output, "a") as fh:
            fh.write(f"duplicate={'true' if dup else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
