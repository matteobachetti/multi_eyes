"""
Query the HEASARC observation catalogues and put the answers in a common format.

Every mission's answer becomes a table with the same columns:

* ``obsid`` (str): observation identifier;
* ``start``, ``end`` (MJD);
* ``exposure`` (s; NaN if the catalogue has none);
* ``target``: target name given by the observer;
* ``ra``, ``dec``: pointing direction (deg);
* ``offset``: angular distance between the pointing and the source (deg).
"""

from __future__ import annotations

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table

from .match import SECONDS_PER_DAY, find_matches
from .missions import MissionSpec, resolve_mission

__all__ = [
    "build_query",
    "normalize_table",
    "merge_contiguous",
    "resolve_source",
    "query_mission",
    "find_simultaneous",
]

# Science windows closer than this (15 min) are merged into one observation.
CONTIGUOUS_GAP_DAYS = 15 / 1440


def build_query(spec: MissionSpec, ra_deg: float, dec_deg: float, radius_deg: float) -> str:
    """
    The ADQL query for one mission's observations within a cone.

    Examples
    --------
    >>> from find_simultaneous.missions import MISSIONS
    >>> q = build_query(MISSIONS["chandra"], 299.59, 35.20, 0.2)
    >>> "cat.exposure as t_duration" in q and "FROM chanmaster" in q
    True
    """
    cols = [
        f"cat.{spec.obsid_column} as obsid",
        f"cat.{spec.start_column} as t_start",
        "cat.ra as ra",
        "cat.dec as dec",
    ]
    if spec.end_column is not None:
        cols.append(f"cat.{spec.end_column} as t_stop")
    else:
        cols.append(f"cat.{spec.duration_column} as t_duration")
    if spec.exposure_column is not None:
        cols.append(f"cat.{spec.exposure_column} as exposure")
    if spec.name_column is not None:
        cols.append(f"cat.{spec.name_column} as target")

    where = [
        f"contains(point('ICRS', cat.ra, cat.dec), "
        f"circle('ICRS', {float(ra_deg)!r}, {float(dec_deg)!r}, {float(radius_deg)!r})) = 1",
        f"cat.{spec.start_column} IS NOT NULL",
    ]
    if spec.condition:
        where.append(f"({spec.condition})")
    return (
        f"SELECT {', '.join(cols)} FROM {spec.table} as cat "
        f"WHERE {' AND '.join(where)} ORDER BY cat.{spec.start_column}"
    )


def _float_column(table, name):
    if name not in table.colnames:
        return np.full(len(table), np.nan)
    col = table[name]
    values = np.ma.asarray(col).astype(float)
    return np.ma.filled(values, np.nan)


def normalize_table(raw: Table, spec: MissionSpec, coord: SkyCoord | None = None) -> Table:
    """
    Put a catalogue answer in the common format described in the module docstring.

    Parameters
    ----------
    raw : astropy.table.Table
        Answer of :func:`build_query`'s query (columns ``obsid``, ``t_start``, ``t_stop`` or
        ``t_duration``, and optionally ``exposure``, ``target``, ``ra``, ``dec``).
    spec : MissionSpec
        The mission.
    coord : SkyCoord, optional
        Source position, used to compute the ``offset`` column.

    Examples
    --------
    >>> from find_simultaneous.missions import MISSIONS
    >>> raw = Table({"obsid": [1], "t_start": [50000.0], "t_duration": [8640.0],
    ...              "exposure": [8640.0], "ra": [10.0], "dec": [20.0], "target": ["X"]})
    >>> float(normalize_table(raw, MISSIONS["chandra"])["end"][0])
    50000.1
    """
    out = Table()
    out["obsid"] = [str(o).strip() for o in raw["obsid"]] if len(raw) else np.zeros(0, str)
    out["start"] = _float_column(raw, "t_start")
    if spec.end_column is not None:
        out["end"] = _float_column(raw, "t_stop")
    else:
        duration = np.nan_to_num(_float_column(raw, "t_duration"), nan=0.0)
        out["end"] = out["start"] + duration / SECONDS_PER_DAY
    out["exposure"] = _float_column(raw, "exposure")
    if "target" in raw.colnames and len(raw):
        out["target"] = [str(t).strip() for t in np.ma.filled(raw["target"].astype(str), "")]
    else:
        out["target"] = np.full(len(raw), "", dtype="<U1")
    out["ra"] = _float_column(raw, "ra")
    out["dec"] = _float_column(raw, "dec")
    if coord is not None and len(raw):
        pointing = SkyCoord(out["ra"], out["dec"], unit="deg")
        out["offset"] = pointing.separation(coord).deg
    else:
        out["offset"] = np.full(len(raw), np.nan)
    out["start"].unit = out["end"].unit = "d"
    out["exposure"].unit = "s"
    out["offset"].unit = "deg"

    out = out[np.isfinite(out["start"])]
    out.sort("start")
    if spec.merge_contiguous:
        out = merge_contiguous(out)
    out.meta["mission"] = spec.name
    return out


def merge_contiguous(table: Table, max_gap: float = CONTIGUOUS_GAP_DAYS) -> Table:
    """
    Merge observations that follow each other with gaps shorter than ``max_gap`` days.

    Used for INTEGRAL, whose catalogue lists ~1-hour science windows. The merged
    observation is named ``first..last``, its exposure is the sum, and ``n_merged``
    counts the rows merged.

    Examples
    --------
    >>> t = Table({"obsid": ["a", "b", "c"], "start": [0.0, 0.05, 1.0],
    ...            "end": [0.04, 0.09, 1.04], "exposure": [100.0, 100.0, 100.0],
    ...            "target": ["", "", ""], "ra": [0.0] * 3, "dec": [0.0] * 3,
    ...            "offset": [1.0, 2.0, 3.0]})
    >>> merge_contiguous(t)["obsid"].tolist()
    ['a..b', 'c']
    """
    if len(table) == 0:
        table = table.copy()
        table["n_merged"] = np.zeros(0, dtype=int)
        return table
    start = np.asarray(table["start"])
    end = np.asarray(table["end"])
    # A new group starts wherever the gap after the latest end so far exceeds max_gap.
    running_end = np.maximum.accumulate(end)
    new_group = np.concatenate([[True], start[1:] - running_end[:-1] > max_gap])

    keep = np.flatnonzero(new_group)
    out = table[keep]
    last = np.concatenate([keep[1:], [len(table)]]) - 1
    out["obsid"] = [
        str(table["obsid"][a]) if a == b else f"{table['obsid'][a]}..{table['obsid'][b]}"
        for a, b in zip(keep, last, strict=True)
    ]
    out["end"] = np.maximum.reduceat(end, keep)
    out["exposure"] = np.add.reduceat(np.nan_to_num(np.asarray(table["exposure"])), keep)
    out["offset"] = np.fmin.reduceat(np.asarray(table["offset"]), keep)
    out["n_merged"] = last - keep + 1
    return out


def resolve_source(source) -> SkyCoord:
    """
    Turn a source name or a coordinate string into a sky position.

    Parameters
    ----------
    source : str or SkyCoord
        A name that SIMBAD/NED/VizieR know (``"Cyg X-1"``), a coordinate string
        (``"299.59 35.20"`` in degrees, or ``"19h58m21.7s +35d12m06s"``), or a SkyCoord.

    Examples
    --------
    >>> c = resolve_source("299.59 35.20")
    >>> round(float(c.ra.deg), 2), round(float(c.dec.deg), 2)
    (299.59, 35.2)
    """
    if isinstance(source, SkyCoord):
        return source
    try:
        parts = source.split()
        if len(parts) == 2:
            try:
                return SkyCoord(float(parts[0]), float(parts[1]), unit="deg")
            except ValueError:
                return SkyCoord(*parts)
    except ValueError:
        pass
    return SkyCoord.from_name(source)


def query_mission(mission, coord: SkyCoord, radius_deg: float | None = None) -> Table:
    """
    All observations of a sky position by one mission, in the common format.

    Parameters
    ----------
    mission : str or MissionSpec
        Mission name or alias.
    coord : SkyCoord
        Source position.
    radius_deg : float, optional
        Cone-search radius. Default: the mission's ``radius_deg``.
    """
    from astroquery.heasarc import Heasarc

    spec = resolve_mission(mission)
    radius = spec.radius_deg if radius_deg is None else float(radius_deg)
    icrs = coord.icrs
    raw = Heasarc.query_tap(build_query(spec, icrs.ra.deg, icrs.dec.deg, radius)).to_table()
    return normalize_table(raw, spec, coord)


def _radius_for(spec, radius):
    if radius is None:
        return None
    if isinstance(radius, dict):
        for key, value in radius.items():
            if resolve_mission(key).name == spec.name:
                return value
        return None
    return radius


def find_simultaneous(
    source,
    missions,
    tolerance=0.0,
    min_missions=None,
    radius=None,
    verbose=False,
):
    """
    Find (quasi-)simultaneous observations of a source by several missions.

    Parameters
    ----------
    source : str or SkyCoord
        Source name or position (see :func:`resolve_source`).
    missions : list of str
        Missions to consider, by any of their names (e.g. ``["NuSTAR", "XMM", "NICER"]``).
    tolerance : float or Quantity, optional
        Maximum gap between the observations, in days if a plain number. Zero means
        that all observations share at least one instant.
    min_missions : int, optional
        Smallest number of missions in a group; by default all of them.
    radius : float or dict, optional
        Search radius in degrees, for all missions or as ``{mission: radius}``.
        Missions not given use their default.
    verbose : bool, optional
        Print how many observations were found for each mission.

    Returns
    -------
    matches : astropy.table.Table
        See :func:`find_simultaneous.match.find_matches`. Each mission also gets
        ``<mission>_offset`` (distance of the pointing from the source, deg) and
        ``<mission>_target`` (the observer's target name).
    observations : dict
        Mission name -> table of all its observations of the source.
    """
    coord = resolve_source(source)
    specs = [resolve_mission(m) for m in missions]
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise ValueError(f"The same mission was given twice: {list(missions)}")

    observations = {}
    for spec in specs:
        observations[spec.name] = query_mission(spec, coord, _radius_for(spec, radius))
        if verbose:
            print(f"{spec.label}: {len(observations[spec.name])} observations")

    matches = find_matches(
        observations,
        tolerance=tolerance,
        min_missions=min_missions,
        columns=("obsid", "start", "end", "exposure", "offset", "target"),
    )
    if isinstance(source, str):
        matches.meta["source"] = source
    matches.meta["ra"], matches.meta["dec"] = coord.icrs.ra.deg, coord.icrs.dec.deg
    matches.meta["tolerance_days"] = float(u.Quantity(tolerance, "day").value)
    return matches, observations
