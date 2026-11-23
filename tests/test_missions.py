import pytest

from find_simultaneous.missions import MISSIONS, MissionSpec, list_missions, resolve_mission


@pytest.mark.parametrize(
    "alias, expected",
    [
        ("Chandra", "chandra"),
        ("AXAF", "chandra"),
        ("cxo", "chandra"),
        ("XTE", "rxte"),
        ("RXTE", "rxte"),
        ("XMM-Newton", "xmm"),
        ("xmm_newton", "xmm"),
        ("Astro-E2", "suzaku"),
        ("Astro-H", "hitomi"),
        ("SAX", "bepposax"),
        ("numaster", "nustar"),
    ],
)
def test_aliases(alias, expected):
    """Old and alternative mission names, in any case or punctuation, find the mission."""
    assert resolve_mission(alias).name == expected


def test_unknown_mission_suggests():
    """A misspelt name raises an error that suggests the intended mission."""
    with pytest.raises(ValueError, match="Did you mean nustar"):
        resolve_mission("nustr")


def test_spec_needs_end_or_duration():
    """A mission without an end time or a duration cannot be defined."""
    with pytest.raises(ValueError, match="end_column or duration_column"):
        MissionSpec(name="x", label="X", table="x", obsid_column="o", start_column="t")


def test_list_missions_mentions_all():
    """The mission listing shows every supported mission."""
    text = list_missions()
    assert all(name in text for name in MISSIONS)
