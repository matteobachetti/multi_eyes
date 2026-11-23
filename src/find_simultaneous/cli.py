"""
Command-line interface.

Example::

    find-simultaneous "Cyg X-1" nustar xmm nicer --tolerance 1d -o cygx1.ecsv
"""

from __future__ import annotations

import argparse
import re

import numpy as np
from astropy import units as u
from astropy.time import Time

from .missions import list_missions, resolve_mission
from .query import find_simultaneous

__all__ = ["main", "parse_tolerance", "parse_radius", "summary_table"]

_UNITS = {"s": u.s, "sec": u.s, "min": u.min, "m": u.min, "h": u.h, "hr": u.h, "d": u.day}


def parse_tolerance(text: str) -> u.Quantity:
    """
    Read a time tolerance such as ``1d``, ``12h``, ``30min``, ``3600s`` or ``0.5``.

    A plain number is in days.

    Examples
    --------
    >>> float(parse_tolerance("12h").to_value("day"))
    0.5
    >>> float(parse_tolerance("2").to_value("day"))
    2.0
    """
    match = re.fullmatch(r"\s*([0-9.eE+-]+)\s*([a-zA-Z]*)\s*", text)
    if match is None or match.group(2).lower() not in {"", *_UNITS}:
        raise argparse.ArgumentTypeError(
            f"Cannot read tolerance {text!r}; use e.g. 1d, 12h, 30min, 3600s"
        )
    unit = _UNITS.get(match.group(2).lower(), u.day)
    return float(match.group(1)) * unit


def parse_radius(values):
    """
    Read ``--radius`` options: one number for all missions, or ``mission=number``.

    Examples
    --------
    >>> parse_radius(["0.3"])
    0.3
    >>> parse_radius(["nicer=0.1", "AXAF=0.2"])
    {'nicer': 0.1, 'chandra': 0.2}
    """
    if not values:
        return None
    if len(values) == 1 and "=" not in values[0]:
        return float(values[0])
    radii = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError(
                f"Mix of global and per-mission radii: {values}. Use mission=radius."
            )
        name, number = value.split("=", 1)
        radii[resolve_mission(name).name] = float(number)
    return radii


def summary_table(matches, missions):
    """
    A short, readable version of the matches: date, overlap in ks and ObsIDs.
    """
    from astropy.table import Table

    out = Table()
    if len(matches) == 0:
        return out
    out["date"] = [t[:16] for t in Time(matches["span_start"], format="mjd").iso]
    out["overlap_ks"] = np.round(np.asarray(matches["overlap"]) / 1000, 1)
    for m in missions:
        out[m] = matches[f"{m}_obsid"].astype(str).filled("-")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="find-simultaneous",
        description=(
            "Find observations of a source made by several missions at the same time, "
            "or within a tolerance, using the HEASARC observation catalogues."
        ),
    )
    parser.add_argument("source", nargs="?", help="Source name or 'RA Dec' (deg)")
    parser.add_argument("missions", nargs="*", help="Two or more missions, any alias")
    parser.add_argument(
        "-t",
        "--tolerance",
        type=parse_tolerance,
        default=0 * u.day,
        help="Largest gap allowed between observations (e.g. 1d, 12h, 3600s; "
        "plain numbers are days). Default 0: they must overlap.",
    )
    parser.add_argument(
        "-n",
        "--min-missions",
        type=int,
        default=None,
        help="Report also groups with at least this many missions (default: all).",
    )
    parser.add_argument(
        "-r",
        "--radius",
        nargs="+",
        default=None,
        help="Search radius in deg: one value, or mission=value pairs. "
        "Default: each mission's own (see --list-missions).",
    )
    parser.add_argument("-o", "--output", help="Save the full table (.ecsv, .csv, .fits, ...)")
    parser.add_argument(
        "--list-missions", action="store_true", help="List the supported missions and exit"
    )
    args = parser.parse_args(argv)

    if args.list_missions:
        print(list_missions())
        return 0
    if args.source is None or len(args.missions) < 2:
        parser.error("give a source and at least two missions")

    try:
        radius = parse_radius(args.radius)
        missions = [resolve_mission(m).name for m in args.missions]
    except (ValueError, argparse.ArgumentTypeError) as err:
        parser.error(str(err))

    matches, observations = find_simultaneous(
        args.source,
        missions,
        tolerance=args.tolerance,
        min_missions=args.min_missions,
        radius=radius,
        verbose=True,
    )
    print(f"\n{len(matches)} groups within {args.tolerance:g}\n")
    if len(matches):
        summary_table(matches, missions).pprint(max_lines=-1, max_width=-1)
    if args.output:
        matches.write(args.output, overwrite=True)
        print(f"\nFull table saved to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
