# Contributing

**Fastest path:** open an issue using *Report a site*. Fill in what you have;
approximate dates are fine. A maintainer turns it into a record.

**PR path:**

1. Copy the closest existing file in `sites/` and edit. One file per host
   (`host.yaml`) or per host + path (`host__scope.yaml`).
2. Every trace needs `url`, `kind`, `timestamp`, `content_kind`, `attribution`,
   `reported_by`, `reported_on`. Truncate timestamps to what you actually know.
3. If you name a new `task_cluster` or `campaign`, add its file too.
4. Run `python scripts/validate.py` and `python scripts/build_index.py`.
5. In the PR description, say how you found the site and whether you notified the owner.

Reviewers check: POLICY §2 (no mechanisms), attribution grade is justified by the
evidence listed, filename matches id, INDEX.md regenerated.

**Updating a record:** change `status.as_of` whenever you touch `status`. Do not
delete traces that went offline — set `content_status: deleted` or `archived_only`.
