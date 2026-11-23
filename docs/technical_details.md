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
