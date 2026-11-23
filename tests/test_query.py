import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.table import Table

from find_simultaneous.missions import MISSIONS
from find_simultaneous.query import (
    build_query,
    find_simultaneous,
    normalize_table,
    query_mission,
    resolve_source,
)

CYGX1 = SkyCoord(299.590315, 35.201604, unit="deg")


def test_query_uses_mission_columns():
    """The query renames each catalogue's own columns to the common names."""
    q = build_query(MISSIONS["swift"], 299.59, 35.2, 0.2)
    assert "cat.start_time as t_start" in q and "cat.stop_time as t_stop" in q
    assert "FROM swiftmastr" in q and "circle('ICRS', 299.59, 35.2, 0.2)" in q
    q = build_query(MISSIONS["nustar"], 0, 0, 0.1)
    assert "cat.exposure_a > 0" in q


def test_normalize_masked_and_offset():
    """Masked exposures become NaN, rows come out sorted, offsets are measured."""
    raw = Table(
        {
            "obsid": [2, 1],
            "t_start": [50001.0, 50000.0],
            "t_stop": [50001.5, 50000.5],
            "exposure": np.ma.MaskedArray([1.0, 2.0], mask=[True, False]),
            "ra": [299.59, 300.59],
            "dec": [35.2, 35.2],
            "target": ["B", "A"],
        }
    )
    out = normalize_table(raw, MISSIONS["nicer"], CYGX1)
    assert list(out["obsid"]) == ["1", "2"]
    assert np.isnan(out["exposure"][1])
    assert out["offset"][1] < 0.01 < out["offset"][0]


def test_normalize_merges_integral_windows():
    """INTEGRAL science windows separated by short slews become one observation."""
    raw = Table(
        {
            "obsid": ["s1", "s2", "s3"],
            "t_start": [0.0, 0.045, 2.0],
            "t_stop": [0.04, 0.085, 2.04],
            "exposure": [3000.0, 3000.0, 3000.0],
            "ra": [299.0] * 3,
            "dec": [35.0] * 3,
        }
    )
    out = normalize_table(raw, MISSIONS["integral"], CYGX1)
    assert list(out["obsid"]) == ["s1..s2", "s3"]
    assert list(out["n_merged"]) == [2, 1]
    assert out["exposure"][0] == 6000.0


def test_resolve_source_from_coordinates():
    """Coordinate strings in degrees or sexagesimal are understood without a name lookup."""
    a = resolve_source("299.590315 35.201604")
    b = resolve_source("19h58m21.68s +35d12m05.8s")
    assert a.separation(b).arcsec < 1


@pytest.mark.remote_data
@pytest.mark.parametrize("mission", sorted(MISSIONS))
def test_every_catalogue_query_runs(mission):
    """Each mission's query is accepted by HEASARC, so its column names are right."""
    out = query_mission(mission, CYGX1, radius_deg=0.01)
    assert {"obsid", "start", "end", "exposure"} <= set(out.colnames)
    assert np.all(out["end"] >= out["start"])


@pytest.mark.remote_data
def test_cygx1_nustar_nicer():
    """Cyg X-1 has strictly simultaneous NuSTAR and NICER observations."""
    matches, obs = find_simultaneous("299.590315 35.201604", ["NuSTAR", "NICER"])
    assert len(obs["nustar"]) > 10 and len(obs["nicer"]) > 10
    assert len(matches) > 0
    assert np.all(matches["overlap"] >= 0)
