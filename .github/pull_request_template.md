## What this adds or changes

<!-- One line per record touched. -->

## How I found it

<!-- HN comment URL, report page, own search … -->

## Prior-report check

- [ ] I searched `sites/` and open/closed issues for this host and it is not already recorded, **or** this PR extends the existing record instead of adding a new one.
- [ ] For a new incident: no existing `incidents/*.yaml` covers the same disclosure (same source, same hosts, same day).
- [ ] `python scripts/check_duplicates.py --base origin/main` prints OK.

## Checks

- [ ] `python scripts/validate.py` prints OK
- [ ] `python scripts/build_index.py` run, `INDEX.md` committed
- [ ] No mechanisms described (POLICY §2)
- [ ] Site owner notified: yes / no / unknown
