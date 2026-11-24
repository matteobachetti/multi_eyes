# Technical details

## Mission catalogues

Every mission is described by a `MissionSpec` in `src/multi_eyes/missions.py`.
Each HEASARC master catalogue stores the same information under different column names:

| Mission | Catalogue | Start | End | Exposure reported |
|---|---|---|---|---|
| NuSTAR | `numaster` | `time` | `end_time` | `exposure_a` |
| NICER | `nicermastr` | `time` | `end_time` | `exposure` |
| XMM-Newton | `xmmmaster` | `time` | `end_time` | `duration` |
| Chandra | `chanmaster` | `time` | start + `exposure` | `exposure` |
| RXTE | `xtemaster` | `time` | start + `duration` | `exposure` |
| Swift | `swiftmastr` | `start_time` | `stop_time` | `xrt_exposure` |
| Suzaku | `suzamaster` | `time` | `stop_time` | `exposure` |
| Hitomi | `hitomaster` | `time` | `stop_time` | `exposure` |
| XRISM | `xrismmastr` | `time` | `end_time` | `exposure` (Resolve) |
| IXPE | `ixmaster` | `time` | `end_time` | `exposure_1` |
| ASCA | `ascamaster` | `time` | `end_time` | `sis_exposure` |
| Ginga | `gingalog` | `time` | `end_time` | `exposure` |
| EXOSAT | `exomaster` | `time` | `end_time` | - |
| ROSAT | `rosmaster` | `start_time` | `end_time` | `exposure` |
| BeppoSAX | `saxnfilog` | `start_date` | `end_date` | `mecs_exposure` |
| INTEGRAL | `intscw` | `start_date` | `end_date` | `good_isgri` |

All times are Modified Julian Dates (MJD).

Chandra's and RXTE's catalogues have no end time. For Chandra we use the exposure as the
length of the observation; for RXTE the `duration` column (elapsed time). This makes
Chandra observations look slightly shorter than they are.

### Removing observations that never happened

The catalogues also list accepted or scheduled observations. We drop them:

* Catalogues with a `status` column (NuSTAR, XMM, Chandra, RXTE, XRISM, IXPE): we keep
  only `archived`, `observed`, `processed` (and `preprocessed` for XRISM). Rejected
  values include `accepted`, `scheduled`, `unobserved` and `untriggered`.
* NuSTAR: `exposure_a > 0`, because zero exposure means no data.
* NICER and XMM: exposure `>= 0`. Zero is kept for NICER because its pipeline sometimes
  records zero exposure for good data (lesson from `heasarc_retrieve_pipeline`).
* BeppoSAX: `obs_perf != 'no'`.
* INTEGRAL: only pointings (`scw_type = 'pointing'`), not slews.

### Search radius

The catalogues give the *pointing* direction, not the source position. A source can be
well inside the field of view of an observation pointed elsewhere, so each mission has a
default search radius of roughly half its field of view (e.g. 0.05 deg for NICER,
0.25 deg for XMM-Newton, 5 deg for INTEGRAL). It can be changed per mission.

### Missions not included

AstroSat (ISSDC AstroBrowse/PRADAN) and Insight-HXMT (IHEP) only offer web portals, with
no catalogue that a program can query. SVOM needs credentials. They are not supported
for now.

## What counts as simultaneous

Each observation is a time interval from its catalogue start to its catalogue end. A group
of observations, one per mission, is *simultaneous within a tolerance T* if one time
window of length T touches all of them:

    max(starts) - min(ends) <= T

With T = 0 all observations share at least one instant. Every match also reports
`overlap = min(ends) - max(starts)` in seconds. A positive value is how long all the
missions observed together; a negative value is the gap that had to be bridged.

The group condition holds if and only if it holds for every pair in the group. (The
largest start and the smallest end either belong to two different observations, which
is a pair condition, or to the same one, where start - end <= 0 <= T anyway.) This is
why A overlapping B and B overlapping C does *not* make A, B and C a match when A and C
are far apart.

The search (`multi_eyes.match.find_matches`) takes the missions one at a time,
smallest catalogue first. For each candidate it keeps the latest start and earliest end
chosen so far, and finds the next mission's compatible observations by binary search on
the sorted start times. A test checks it against trying every combination.

Every compatible combination is reported. If NICER observed twice during one NuSTAR
observation, that gives two rows. With `min_missions` smaller than the number of
missions, every subset of at least that many missions is searched, so pairs are also
reported. A pair that is part of a reported triplet appears as its own row too.

**Caveat:** catalogue start and end are not good time intervals. A NICER or RXTE
observation can span a day or more with only a few ks of data, so an overlap does not
guarantee photons at the same moment.

## Campaigns

Because every compatible combination is reported, a coordinated campaign gives many
nearly identical matches. For Cyg X-1 with NuSTAR, RXTE, Chandra and Swift (at least
three, within 1 day) there are 26 matches, but only two campaigns.

`multi_eyes.group` puts two matches in the same *campaign* if they share at least
one observation. Campaigns are the chains of matches linked this way. Think of a graph
whose points are observations, with a line joining the observations of each match: a
campaign is a connected piece of that graph. It is computed with a union-find structure
(each observation points to a representative of its set, and two sets are merged by
re-pointing one representative), in time proportional to the number of matches.

This rule needs no extra parameter, and it never merges two matches that have nothing in
common, even if they happen on consecutive days. On the other hand, a long observation
can link matches that are far apart in time: a 3-day RXTE observation overlapping a
Swift pointing at each end puts both pointings in one campaign.

`search()` adds a `campaign` column to the matches. `group_matches()` gives one
row per campaign, with the number of matches, the time span, the best single-match
overlap, and each mission's ObsIDs in time order.

## Querying the catalogues

`multi_eyes.query` builds one ADQL query per mission (`build_query`) and sends it
to HEASARC's TAP service through `astroquery.heasarc.Heasarc.query_tap`. The query renames
each catalogue's columns to common names (`t_start`, `t_stop` or `t_duration`, `exposure`,
`target`). `start` cannot be used as an alias: it is a reserved word for HEASARC's ADQL
parser, and the query fails with "invalid syntax". `normalize_table` then produces the
common format, with columns `obsid`, `start`, `end`, `exposure`, `target`, `ra`, `dec` and
`offset`. `offset` is the distance of the pointing from the source.

Masked (missing) exposures become NaN. A missing duration (Chandra, RXTE) gives an
observation of zero length.

### INTEGRAL

`intscw` has one row per science window, about 1 hour long, so a single INTEGRAL
revolution produces dozens of rows. Science windows separated by less than 15 minutes
(the slews between them) are merged into one observation named `first..last`. Its
exposure is the sum of the ISGRI good times, `offset` is the smallest offset, and
`n_merged` counts the science windows. For Cyg X-1 this reduces the INTEGRAL pointings to
about 1300 observations.

### Source positions

`resolve_source` accepts a name (resolved through Sesame: SIMBAD, NED, VizieR), two
numbers in degrees, or a sexagesimal coordinate pair.

## Command line

    multi-eyes SOURCE MISSION MISSION [MISSION ...] [options]

* `-t/--tolerance`: largest gap between observations: `1d`, `12h`, `30min`, `3600s`, or
  a plain number of days. Default 0 (they must overlap).
* `-n/--min-missions`: also report groups with at least this many missions.
* `-r/--radius`: search radius in degrees, either one value or `mission=value` pairs
  (`-r nicer=0.1 xmm=0.3`).
* `-o/--output`: save the full table. The format comes from the extension (`.ecsv`
  keeps units and masks; `.csv`, `.fits` also work).
* `-g/--group`: print campaigns instead of every match. With `-o`, the campaigns are also
  saved, in a file with `_campaigns` added to the name.
* `--list-missions`: supported missions, aliases and default radii.

The printed summary shows, for each group, the start date, the overlap in ks (negative
means a gap) and each mission's ObsID (`-` if that mission is not in the group).

## Development infrastructure

* **Version:** derived from git tags by `setuptools_scm`. It writes
  `src/multi_eyes/_version.py`, which is not tracked. When running from a source
  tree that was never installed, `__version__` is `"unknown"`.
* **Documentation:** Sphinx, configured through `sphinx_astropy.conf.v2` (numpydoc,
  automodapi, intersphinx, pydata theme), with pages written in Markdown and read by
  `myst-parser`. `docs/usage.md` includes the usage part of the README, between the
  `usage-start` and `usage-end` markers, so the two cannot drift apart. The API pages are
  generated from the docstrings into `docs/api/` (not tracked). Built on Read the Docs
  (`.readthedocs.yml`), with warnings treated as errors.
* **Changelog:** each pull request adds a snippet `docs/changes/<PR>.<type>.rst`. Get the
  number with `nextpr`. `towncrier build --version X.Y` folds the snippets into
  `CHANGES.rst`.
* **Tests and CI:** every CI job is a tox environment (`tox.ini`), so it can be reproduced
  locally with `tox -e <name>`, e.g. `tox -e py313-test`, `tox -e build_docs`,
  `tox -e codestyle`. `.github/workflows/ci_tests.yml` runs code style, Python 3.11,
  3.13 (with coverage) and 3.14 on Linux, 3.13 on macOS, the docs build and a package
  build check, on every push to main and every pull request. The tests that query HEASARC
  (`pytest --remote-data`, or `tox -e py313-test-remote`) run only in the weekly workflow
  `ci_cron_weekly.yml`, together with a link check and the development versions of
  astropy and astroquery. An archive outage thus never blocks a pull request, but a
  renamed catalogue column is noticed within a week.
