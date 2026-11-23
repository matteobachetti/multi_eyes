import argparse

import pytest

from find_simultaneous.cli import main, parse_radius, parse_tolerance


def test_tolerance_units():
    """Tolerances are read in seconds, minutes, hours or days; plain numbers are days."""
    assert parse_tolerance("3600s").to_value("h") == pytest.approx(1)
    assert parse_tolerance("30min").to_value("h") == pytest.approx(0.5)
    assert parse_tolerance("1d").to_value("h") == pytest.approx(24)
    with pytest.raises(argparse.ArgumentTypeError):
        parse_tolerance("1 fortnight")


def test_radius_mixed_is_refused():
    """A global radius cannot be mixed with per-mission ones."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_radius(["0.3", "nicer=0.1"])


def test_list_missions(capsys):
    """--list-missions prints the mission table without needing a source."""
    assert main(["--list-missions"]) == 0
    assert "chanmaster" in capsys.readouterr().out


def test_needs_two_missions():
    """Asking for a single mission is an error."""
    with pytest.raises(SystemExit):
        main(["Cyg X-1", "nustar"])
