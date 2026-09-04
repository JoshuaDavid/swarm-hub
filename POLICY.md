# Policy

This repository is, unavoidably, a list of places on the internet that accept writes
they should not. Handle it accordingly.

## 1. Look, don't touch

Never edit, delete, test, or "clean up" anything on a listed site. Do not create
pages, pastes, links, or counter keys to see whether it still works. Read-only
enumeration (RecentChanges, `/lists`, public stats pages) is fine.

## 2. Mechanisms are not recorded

`platform.write_path` is a category. Nothing in this repository may describe *how* a
site can be written to, how a proxy or sandbox was bypassed, or how a filter was
evaded — not in notes, not in trace titles, not in issue comments. If a trace's
content is itself such a description, record that it exists (`content_kind:
bypass_share`) and nothing more. Maintainers will edit or reject submissions that
cross this line.

## 3. Notify owners

Anyone adding a site should attempt to notify its operator and record the date in
`owner.notified`. Universities, individuals running class wikis, and hobby projects
did not consent to being case studies. Where an owner asks for their host to be
removed, the record is reduced to host + campaign + `status.state: cleaned` with no
traces.

## 4. IP addresses and people

Full IP addresses are recorded only when they belong to cloud provider or Tor ranges
(they identify infrastructure). All others are masked to the /24 with `x`. Never
record names, emails, or handles of humans — moderators, site owners, HN commenters
beyond their public username as `found_by`.

## 5. Attribution is graded, not asserted

Nothing here says a developer *did* something. Records say what was observed and how
strong the link is. `confirmed` is reserved for developer disclosure. Claims that a
site was seeded by a third party to make agents look bad are possible and are why
`unattributed` exists.

## 6. Reading by AI systems

This repository is public and will be crawled. It contains no operational content
(see §2). Whether to serve it to AI-lab address ranges is a deployment decision, not
a repository one; the data itself is designed to be safe to read.
