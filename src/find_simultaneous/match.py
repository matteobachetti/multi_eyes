"""
Find groups of observations by different missions that happen at about the same time.

Definition
----------
Each observation is a time interval ``[start, end]``. A group of observations, one per
mission, is *simultaneous within a tolerance T* if a single time window of length T
touches all of them. In formulas::

    max(starts) - min(ends) <= T

With ``T = 0`` the observations share at least one instant. For each group we report
``overlap = min(ends) - max(starts)``: positive, it is how long all of them were
observing together; negative, it is the largest gap that had to be bridged.

A useful property: the group condition holds if and only if it holds for every *pair* of
observations in the group. The search therefore adds one mission at a time and keeps only
the candidates compatible with everything chosen so far.

Note that ``start`` and ``end`` are the catalogue's start and end, not the good time
intervals: a NICER or RXTE observation can span many orbits with gaps between them.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from astropy.table import MaskedColumn, Table

__all__ = ["find_matches", "match_columns"]

SECONDS_PER_DAY = 86400.0


def _prepare(table):
    """Arrays of start, end and the original row index, sorted by start."""
    start = np.asarray(table["start"], dtype=float)
    end = np.asarray(table["end"], dtype=float)
    # An unknown or impossible end makes the observation a single instant.
    bad = ~np.isfinite(end) | (end < start)
    end = np.where(bad, start, end)
    good = np.isfinite(start)
    index = np.flatnonzero(good)
    order = np.argsort(start[good], kind="stable")
    index = index[order]
    return {
        "start": start[index],
        "end": end[index],
        "row": index,
        "max_length": float(np.max(end[index] - start[index])) if index.size else 0.0,
    }


def _search(prepared, tolerance):
    """
    All combinations, one observation per mission, satisfying the tolerance.

    Returns a list of tuples of original row indices, in the order of ``prepared``.
    """
    results = []
    n = len(prepared)

    def recurse(level, chosen, max_start, min_end):
        if level == n:
            results.append(tuple(chosen))
            return
        p = prepared[level]
        # Candidates need start <= min_end + T and end >= max_start - T. Starts are
        # sorted, so the first condition is a binary search. For the second, an
        # observation ending after max_start - T must start after
        # max_start - T - (longest observation), which bounds the search from below.
        hi = np.searchsorted(p["start"], min_end + tolerance, side="right")
        lo = np.searchsorted(p["start"], max_start - tolerance - p["max_length"], side="left")
        for k in range(lo, hi):
            if p["end"][k] < max_start - tolerance:
                continue
            chosen.append(p["row"][k])
            recurse(
                level + 1,
                chosen,
                max(max_start, p["start"][k]),
                min(min_end, p["end"][k]),
            )
            chosen.pop()

    recurse(0, [], -np.inf, np.inf)
    return results


def match_columns(missions):
    """
    Names of the output columns, for the given missions.

    Examples
    --------
    >>> match_columns(["nustar"])[:4]
    ['n_missions', 'missions', 'overlap', 'span_start']
    """
    cols = ["n_missions", "missions", "overlap", "span_start", "span_end"]
    for m in missions:
        cols += [f"{m}_obsid", f"{m}_start", f"{m}_end", f"{m}_exposure"]
    return cols


def find_matches(observations, tolerance=0.0, min_missions=None):
    """
    Find (quasi-)simultaneous observations among several missions.

    Parameters
    ----------
    observations : dict
        Mission name -> table with columns ``obsid``, ``start`` and ``end`` (MJD), and
        optionally ``exposure`` (s). The order of the dictionary sets the order of the
        output columns.
    tolerance : float or astropy.units.Quantity, optional
        Maximum gap allowed between the observations, in days if a plain number.
        Zero means that all observations share at least one instant.
    min_missions : int, optional
        Smallest number of missions in a group. By default all missions must take part.
        With fewer, every subset of at least ``min_missions`` missions is searched, so
        that, for example, pairs are also found when the third mission is missing.

    Returns
    -------
    astropy.table.Table
        One row per group, sorted by time, with columns:

        * ``n_missions``, ``missions``: how many and which missions are in the group;
        * ``overlap``: ``min(end) - max(start)`` in seconds. Positive is the time all
          missions observed together, negative is the gap between them;
        * ``span_start``, ``span_end``: earliest start and latest end (MJD);
        * ``<mission>_obsid``, ``_start``, ``_end``, ``_exposure`` for each mission,
          masked when that mission is not in the group.

        A group of k missions that is part of a larger group is reported too, as its own
        row, when ``min_missions <= k``.

    Examples
    --------
    >>> from astropy.table import Table
    >>> a = Table({"obsid": ["a1"], "start": [100.0], "end": [100.5]})
    >>> b = Table({"obsid": ["b1"], "start": [100.4], "end": [101.0]})
    >>> res = find_matches({"nustar": a, "nicer": b})
    >>> str(res["nustar_obsid"][0]), str(res["nicer_obsid"][0]), round(float(res["overlap"][0]))
    ('a1', 'b1', 8640)
    """
    if hasattr(tolerance, "unit"):
        tolerance = tolerance.to_value("day")
    tolerance = float(tolerance)
    if tolerance < 0:
        raise ValueError("tolerance must be zero or positive")

    names = list(observations)
    if len(names) < 2:
        raise ValueError("Give at least two missions")
    if min_missions is None:
        min_missions = len(names)
    if not 2 <= min_missions <= len(names):
        raise ValueError(f"min_missions must be between 2 and {len(names)}")

    prepared = {m: _prepare(observations[m]) for m in names}

    rows = []
    for size in range(len(names), min_missions - 1, -1):
        for subset in combinations(names, size):
            # Searching the smallest catalogues first keeps the candidate lists short.
            order = sorted(subset, key=lambda m: prepared[m]["row"].size)
            for combo in _search([prepared[m] for m in order], tolerance):
                rows.append(dict(zip(order, combo, strict=True)))

    return _build_table(observations, names, rows)


def _build_table(observations, names, rows):
    n = len(rows)
    out = Table()
    starts = np.full((n, len(names)), np.nan)
    ends = np.full((n, len(names)), np.nan)
    for j, m in enumerate(names):
        tab = observations[m]
        idx = np.array([r.get(m, -1) for r in rows], dtype=int)
        present = idx >= 0
        safe = np.where(present, idx, 0)
        for col in ("obsid", "start", "end", "exposure"):
            if col in tab.colnames and len(tab) > 0:
                values = np.asarray(tab[col])[safe] if n else np.asarray(tab[col])[:0]
            else:
                values = np.full(n, np.nan)
            out[f"{m}_{col}"] = MaskedColumn(values, mask=~present)
        if n:
            s = np.asarray(tab["start"], dtype=float)[safe]
            e = np.asarray(tab["end"], dtype=float)[safe]
            e = np.where(~np.isfinite(e) | (e < s), s, e)
            starts[present, j] = s[present]
            ends[present, j] = e[present]

    if n:
        max_start = np.nanmax(starts, axis=1)
        min_end = np.nanmin(ends, axis=1)
        span_start = np.nanmin(starts, axis=1)
        span_end = np.nanmax(ends, axis=1)
    else:
        max_start = min_end = span_start = span_end = np.zeros(0)

    out.add_column([sum(m in r for m in names) for r in rows], name="n_missions", index=0)
    out.add_column(
        [",".join(m for m in names if m in r) for r in rows] if n else np.zeros(0, dtype=str),
        name="missions",
        index=1,
    )
    out.add_column((min_end - max_start) * SECONDS_PER_DAY, name="overlap", index=2)
    out.add_column(span_start, name="span_start", index=3)
    out.add_column(span_end, name="span_end", index=4)
    out["overlap"].unit = "s"
    out["span_start"].unit = out["span_end"].unit = "d"

    if n:
        out.sort(["span_start", "n_missions"], reverse=False)
    return out
