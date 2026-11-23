# find_simultaneous

Find the times when a source was observed by several X-ray missions at the same time,
or within a given tolerance: for example, every time Cyg X-1 was observed by NuSTAR,
XMM-Newton and NICER within one day.

The observation lists come from the HEASARC master catalogues, queried with
[astroquery](https://astroquery.readthedocs.io). Missions can be named in any of their
usual ways (Chandra/AXAF/CXO, RXTE/XTE, XMM/XMM-Newton, Suzaku/Astro-E2, BeppoSAX/SAX, ...).

Supported: NuSTAR, NICER, XMM-Newton, Chandra, RXTE, Swift, Suzaku, Hitomi, XRISM, IXPE,
ASCA, Ginga, EXOSAT, ROSAT, BeppoSAX, INTEGRAL. Run `find-simultaneous --list-missions`
for aliases and default search radii.

<!-- usage-start -->

## Installation

```bash
pip install -e .
```

## Command line

```bash
find-simultaneous "Cyg X-1" nustar xmm nicer --tolerance 1d --min-missions 2 -o cygx1.ecsv
```

```
NuSTAR: 41 observations
XMM-Newton: 20 observations
NICER: 142 observations

55 groups within 1 d

      date       overlap_ks    nustar      xmm       nicer
---------------- ---------- ----------- ---------- ----------
2016-05-27 22:19      144.0 30002150002 0745250201          -
2016-05-27 22:19      -23.2 30002150004 0745250201          -
...
2017-11-04 17:16        4.1 30302019002          - 1100320105
2018-02-08 20:01        8.1 30302019004          - 1100320110
```

`overlap_ks` is the time during which all the missions in the group were observing
together. A negative value is the gap between them, which the tolerance allowed.
Without `--min-missions` only groups containing *all* the missions are reported. (For
Cyg X-1 there are none with all three: XMM last observed it in 2016, before NICER was
launched.)

Main options:

* `-t/--tolerance`: `1d`, `12h`, `30min`, `3600s`, or a plain number of days (default 0:
  the observations must overlap);
* `-n/--min-missions`: also report pairs, triplets, ... out of the missions given;
* `-r/--radius`: cone-search radius in degrees, global (`-r 0.3`) or per mission
  (`-r nicer=0.1 xmm=0.3`);
* `-g/--group`: print *campaigns* (matches linked by shared observations) instead of
  every match;
* `-o/--output`: save the full table (ECSV keeps units and masks).

During a coordinated campaign every compatible combination of ObsIDs is a separate match,
which can give dozens of rows. `--group` merges matches that share an observation:

```bash
find-simultaneous "Cyg X-1" NuSTAR XTE AXAF Swift -t 1d -n 3 --group
```

```
26 matches within 1 d, in 2 campaigns

campaign       date       days matches best_overlap_ks nustar        rxte              chandra   swift
-------- ---------------- ---- ------- --------------- ------ ---------------------- --------- ---------------------
       0 2008-04-18 13:13  1.3      24             8.4      - 93120-01-01-00,931...  8525,9847 00030388002,00030...
       1 2010-07-22 05:57  0.5       2           -17.0      - 95429-01-02-02,954...      12313 00031651011
```

## Python

```python
from find_simultaneous import find_simultaneous

matches, observations = find_simultaneous(
    "Cyg X-1", ["NuSTAR", "XMM-Newton", "NICER"], tolerance=1, min_missions=2
)
matches["missions", "overlap", "nustar_obsid", "nicer_obsid"]
observations["nicer"]  # every NICER observation of the source

from find_simultaneous import group_matches

campaigns = group_matches(matches)  # one row per campaign
```

`matches` has one row per group, with `<mission>_obsid`, `_start`, `_end` (MJD),
`_exposure` (s), `_offset` (deg from the source) and `_target` for each mission. Columns
of missions that are not in a group are masked.

If you already have observation lists (for example from another archive), the matching
can be used on its own: `find_simultaneous.find_matches({"a": table_a, "b": table_b},
tolerance=0.5)`, where each table has `obsid`, `start` and `end` columns in MJD.

## Limitations

* Start and end come from the catalogues, not from good time intervals. A NICER or RXTE
  observation can span a day with only a few ks of data, so an overlap does not
  guarantee photons at the same moment.
* Chandra's catalogue has no end time; its length is taken to be the exposure.
* AstroSat, Insight-HXMT and SVOM are not supported: they have no catalogue that a
  program can query without credentials.

<!-- usage-end -->

See [`docs/technical_details.md`](docs/technical_details.md) for how each catalogue is read
and how matches are defined.

## Tests

```bash
pytest                 # offline tests
pytest --remote-data   # also query HEASARC for every mission
```
