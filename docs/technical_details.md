# Technical details

## Mission catalogues

Every mission is described by a `MissionSpec` in `src/find_simultaneous/missions.py`.
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

The search (`find_simultaneous.match.find_matches`) takes the missions one at a time,
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
