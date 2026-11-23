from astropy.table import Table

from find_simultaneous.group import assign_campaigns, group_matches
from find_simultaneous.match import find_matches


def obs(prefix, intervals):
    return Table(
        {
            "obsid": [f"{prefix}{i}" for i in range(len(intervals))],
            "start": [float(s) for s, _ in intervals],
            "end": [float(e) for _, e in intervals],
        }
    )


def campaign_data():
    # One long XMM observation overlapping three NICER ones, then an unrelated pair.
    xmm = obs("x", [(10, 12), (50, 51)])
    nicer = obs("n", [(10.1, 10.2), (10.5, 10.6), (11.5, 11.6), (50.5, 50.7)])
    return {"xmm": xmm, "nicer": nicer}


def test_shared_observation_makes_one_campaign():
    """Matches sharing an XMM observation form one campaign; unrelated ones do not."""
    matches = find_matches(campaign_data())
    assert assign_campaigns(matches).tolist() == [0, 0, 0, 1]
    campaigns = group_matches(matches)
    assert campaigns["n_matches"].tolist() == [3, 1]
    assert campaigns["nicer_obsids"][0] == "n0,n1,n2"
    assert campaigns["xmm_n"].tolist() == [1, 1]


def test_chain_through_different_missions():
    """A-B and B-C matches sharing the B observation end up in the same campaign."""
    data = {
        "a": obs("a", [(10, 11)]),
        "b": obs("b", [(10.5, 13.5)]),
        "c": obs("c", [(13, 14)]),
    }
    matches = find_matches(data, tolerance=1, min_missions=2)
    campaigns = group_matches(matches)
    assert len(campaigns) == 1
    assert campaigns["missions"][0] == "a,b,c"
    assert campaigns["max_n_missions"][0] == 2


def test_empty_matches():
    """No matches give no campaigns, with the expected columns."""
    matches = find_matches({"a": obs("a", [(1, 2)]), "b": obs("b", [(5, 6)])})
    campaigns = group_matches(matches)
    assert len(campaigns) == 0 and "a_obsids" in campaigns.colnames
