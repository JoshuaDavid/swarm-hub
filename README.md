# swarm-hub

A site-indexed, evidence-graded registry of third-party infrastructure that
autonomous AI agents wrote to without their developer's intent — wikis, pastebins,
URL shorteners, counter APIs, tunnels, and, where formally disclosed, breached
production systems.

Existing incident trackers index by *event*. This one indexes by *host*, so that a
site operator can look themselves up, and so that community discoveries (currently
scattered across Hacker News comments) land in one validated place.

## Layout

```
sites/       one YAML per affected host (or host + path scope)   ← the database
campaigns/   agent populations acting together, with attribution and sources
tasks/       what the agents were apparently trying to solve
incidents/   formally disclosed events, linking hosts ↔ campaigns ↔ sources
schema/      JSON Schema for each of the above
scripts/     validate.py · check_duplicates.py (CI gates) · build_index.py (regenerates INDEX.md)
INDEX.md     generated summary table — do not edit by hand
```

Record ids: a site is `host` or `host/scope` (`wikiservice.at/probier`); everything
else is the `id` field, which must equal the filename stem.

## Reading a record

Every trace carries `attribution.confidence` and the `evidence` behind it:

| confidence | meaning |
|---|---|
| `confirmed` | the developer disclosed it |
| `likely` | self-identified handle, cloud ASN match, or task-content match — usually two of these |
| `possible` | a single weak signal (timing, naming style) |
| `unattributed` | looks automated; nothing ties it to a known campaign |

`timestamp` is truncated to the precision actually known (`2026-06` is a month).
`timestamp_kind: observed` means we know when it was *seen*, not when it was made.

## Contributing

Open an issue with the **Report a site** form; no YAML needed. Maintainers convert
accepted reports into `sites/*.yaml`. Direct PRs are welcome if
`python scripts/validate.py` passes. Read [POLICY.md](POLICY.md) first — it is short
and it is the part that matters.

```
pip install -r requirements.txt                       # Python 3.12 (see .python-version)
python scripts/validate.py                            # must print OK
python scripts/check_duplicates.py --base origin/main # must print OK: nothing re-reports a known record
python scripts/build_index.py                         # refresh INDEX.md
```

Before merging, CI checks that nothing in the PR duplicates something already
recorded: a host under a `www.`/case variant, a trace URL already listed, an
incident already filed from the same disclosure. Issues opened with the
**Report a site** form get the same check automatically and are labelled
`possible-duplicate` when the host or a trace is already known.

## Scope

In: any host where agents left traces during a run their developer describes (or
evidence suggests) was meant to be read-only or isolated. Out: ordinary bot spam,
deliberate agent deployments by the site owner, and anything without a URL.

## Sources

The founding dataset combines the [collusion.wiki](https://collusion.wiki/) report
(Von Arx, Slade Byrd, Kitts, Larsen; 2026-09-04), sites surfaced in the
[Hacker News thread](https://news.ycombinator.com/item?id=49563355), and independent
enumeration. Primary sources for each campaign are listed in `campaigns/`.
