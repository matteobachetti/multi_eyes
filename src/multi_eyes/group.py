"""
Merge matches into campaigns.

:func:`multi_eyes.match.find_matches` reports every compatible combination of
observations. During a coordinated campaign this produces many nearly identical rows: if
one long XMM observation overlaps five NICER ObsIDs, that is five matches. Here, two
matches belong to the same *campaign* if they share at least one observation, and
campaigns are the chains of matches linked this way (in graph language, the connected
components of the graph whose nodes are observations and whose edges are matches).
"""

from __future__ import annotations

import numpy as np
from astropy.table import Table

__all__ = ["match_missions", "assign_campaigns", "group_matches"]


def match_missions(matches: Table) -> list[str]:
    """
    The missions in a match table, in column order.

    Examples
    --------
    >>> t = Table({"overlap": [0.0], "nustar_obsid": ["a"], "nicer_obsid": ["b"]})
    >>> match_missions(t)
    ['nustar', 'nicer']
    """
    return [c[: -len("_obsid")] for c in matches.colnames if c.endswith("_obsid")]


def _observations(matches, missions):
    """For each match, the list of (mission, obsid) observations it contains."""
    rows = [[] for _ in range(len(matches))]
    for m in missions:
        col = matches[f"{m}_obsid"]
        mask = np.ma.getmaskarray(col)
        values = np.ma.getdata(col)
        for i in np.flatnonzero(~mask):
            rows[i].append((m, str(values[i])))
    return rows


def assign_campaigns(matches: Table, missions=None) -> np.ndarray:
    """
    Campaign number of each match: matches sharing an observation get the same number.

    Campaigns are numbered 0, 1, 2, ... in order of their first match in the table.

    Examples
    --------
    >>> t = Table({"a_obsid": ["a1", "a1", "a2"], "b_obsid": ["b1", "b2", "b3"]})
    >>> assign_campaigns(t).tolist()
    [0, 0, 1]
    """
    if missions is None:
        missions = match_missions(matches)
    parent = {}

    def find(x):
        # Union-find with path halving: follow parents to the root of x's set.
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    observations = _observations(matches, missions)
    for obs in observations:
        for other in obs[1:]:
            ra, rb = find(obs[0]), find(other)
            if ra != rb:
                parent[rb] = ra

    labels = {}
    out = np.zeros(len(matches), dtype=int)
    for i, obs in enumerate(observations):
        root = find(obs[0])
        out[i] = labels.setdefault(root, len(labels))
    return out


def group_matches(matches: Table, missions=None) -> Table:
    """
    One row per campaign, summarizing the matches it contains.

    Parameters
    ----------
    matches : astropy.table.Table
        Output of :func:`~multi_eyes.match.find_matches` or
        :func:`~multi_eyes.query.search`. If it has a ``campaign``
        column, that is used; otherwise campaigns are computed with
        :func:`assign_campaigns`.
    missions : list of str, optional
        Missions to consider. Default: all those in the table.

    Returns
    -------
    astropy.table.Table
        Columns:

        * ``campaign``: campaign number, as in the ``campaign`` column of the matches;
        * ``n_matches``: number of matches merged;
        * ``n_missions``, ``missions``: missions with at least one observation;
        * ``max_n_missions``: largest number of missions in a single match;
        * ``span_start``, ``span_end``: earliest start and latest end (MJD);
        * ``best_overlap``: largest overlap of any single match (s);
        * ``<mission>_n`` and ``<mission>_obsids``: number and comma-separated list of
          that mission's observations, in time order.

    Examples
    --------
    >>> t = Table({"n_missions": [2, 2], "overlap": [10.0, 30.0],
    ...            "span_start": [1.0, 1.5], "span_end": [2.0, 2.5],
    ...            "a_obsid": ["a1", "a1"], "a_start": [1.0, 1.0],
    ...            "b_obsid": ["b1", "b2"], "b_start": [1.2, 1.5]})
    >>> row = group_matches(t)[0]
    >>> int(row["n_matches"]), str(row["b_obsids"]), float(row["best_overlap"])
    (2, 'b1,b2', 30.0)
    """
    if missions is None:
        missions = match_missions(matches)
    if "campaign" in matches.colnames:
        campaign = np.asarray(matches["campaign"])
    else:
        campaign = assign_campaigns(matches, missions)

    n_campaigns = int(campaign.max()) + 1 if len(matches) else 0
    out = Table()
    out["campaign"] = np.arange(n_campaigns)
    out["n_matches"] = np.bincount(campaign, minlength=n_campaigns)

    per_mission = {}
    for m in missions:
        obsid = matches[f"{m}_obsid"]
        mask = np.ma.getmaskarray(obsid)
        starts = (
            np.ma.getdata(matches[f"{m}_start"]).astype(float)
            if f"{m}_start" in matches.colnames
            else np.zeros(len(matches))
        )
        lists = [{} for _ in range(n_campaigns)]
        for i in np.flatnonzero(~mask):
            lists[campaign[i]][str(np.ma.getdata(obsid)[i])] = starts[i]
        per_mission[m] = [sorted(d, key=d.get) for d in lists]

    out["n_missions"] = [sum(bool(per_mission[m][c]) for m in missions) for c in range(n_campaigns)]
    out["missions"] = (
        [",".join(m for m in missions if per_mission[m][c]) for c in range(n_campaigns)]
        if n_campaigns
        else np.zeros(0, dtype=str)
    )

    def reduce(column, func, dtype=float):
        values = np.ma.getdata(matches[column]).astype(dtype)
        return np.array([func(values[campaign == c]) for c in range(n_campaigns)], dtype=dtype)

    out["max_n_missions"] = reduce("n_missions", np.max, int)
    out["span_start"] = reduce("span_start", np.min)
    out["span_end"] = reduce("span_end", np.max)
    out["best_overlap"] = reduce("overlap", np.max)
    out["span_start"].unit = out["span_end"].unit = "d"
    out["best_overlap"].unit = "s"
    for m in missions:
        out[f"{m}_n"] = [len(lst) for lst in per_mission[m]]
        out[f"{m}_obsids"] = (
            [",".join(lst) for lst in per_mission[m]] if n_campaigns else np.zeros(0, dtype=str)
        )
    return out
