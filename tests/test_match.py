from itertools import product

import astropy.units as u
import numpy as np
import pytest
from astropy.table import Table

from find_simultaneous.match import find_matches


def obs(prefix, intervals):
    return Table(
        {
            "obsid": [f"{prefix}{i}" for i in range(len(intervals))],
            "start": [float(s) for s, _ in intervals],
            "end": [float(e) for _, e in intervals],
            "exposure": [1000.0] * len(intervals),
        }
    )


def test_overlapping_pair():
    """Two overlapping observations match with zero tolerance, with the right overlap."""
    res = find_matches({"a": obs("a", [(10, 11)]), "b": obs("b", [(10.75, 12)])})
    assert len(res) == 1
    assert np.isclose(res["overlap"][0], 0.25 * 86400)
    assert res["span_start"][0] == 10 and res["span_end"][0] == 12


def test_gap_and_tolerance():
    """A 0.5-day gap is bridged by a 0.6-day tolerance but not by 0.4 days."""
    data = {"a": obs("a", [(10, 11)]), "b": obs("b", [(11.5, 12)])}
    assert len(find_matches(data, tolerance=0.4)) == 0
    res = find_matches(data, tolerance=0.6 * u.day)
    assert len(res) == 1
    assert np.isclose(res["overlap"][0], -0.5 * 86400)


def test_chain_is_not_a_triplet():
    """A-B and B-C overlapping does not make a triplet if A and C are too far apart."""
    data = {
        "a": obs("a", [(10, 11)]),
        "b": obs("b", [(10.5, 13.5)]),
        "c": obs("c", [(13, 14)]),
    }
    assert len(find_matches(data, tolerance=1)) == 0
    pairs = find_matches(data, tolerance=1, min_missions=2)
    assert sorted(pairs["missions"]) == ["a,b", "b,c"]
    assert pairs["c_obsid"].mask[list(pairs["missions"]).index("a,b")]


def test_every_combination_reported():
    """Two observations of one mission inside one of another give two matches."""
    data = {"a": obs("a", [(10, 12)]), "b": obs("b", [(10.2, 10.3), (11, 11.5)])}
    res = find_matches(data)
    assert list(res["b_obsid"]) == ["b0", "b1"]


def test_empty_mission():
    """A mission with no observations gives an empty table with all the columns."""
    res = find_matches({"a": obs("a", [(10, 11)]), "b": obs("b", [])})
    assert len(res) == 0
    assert "b_obsid" in res.colnames and "overlap" in res.colnames


def test_against_brute_force():
    """The fast search finds exactly the triplets that checking every combination finds."""
    rng = np.random.default_rng(1234)
    data = {}
    for name, n in zip("abc", (30, 50, 40), strict=True):
        start = rng.uniform(0, 100, n)
        data[name] = obs(name, list(zip(start, start + rng.uniform(0, 2, n), strict=True)))
    tol = 0.7
    expected = set()
    for i, j, k in product(*(range(len(data[m])) for m in "abc")):
        rows = [data[m][x] for m, x in zip("abc", (i, j, k), strict=True)]
        if max(r["start"] for r in rows) - min(r["end"] for r in rows) <= tol:
            expected.add((f"a{i}", f"b{j}", f"c{k}"))
    res = find_matches(data, tolerance=tol)
    found = set(zip(res["a_obsid"], res["b_obsid"], res["c_obsid"], strict=True))
    assert found == expected and len(expected) > 0


def test_bad_arguments():
    """Negative tolerances, a single mission and impossible minimum sizes are refused."""
    a, b = obs("a", [(1, 2)]), obs("b", [(1, 2)])
    with pytest.raises(ValueError):
        find_matches({"a": a, "b": b}, tolerance=-1)
    with pytest.raises(ValueError):
        find_matches({"a": a})
    with pytest.raises(ValueError):
        find_matches({"a": a, "b": b}, min_missions=3)
