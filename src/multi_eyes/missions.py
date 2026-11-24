"""
What we need to know about each mission's observation catalogue at HEASARC.

Every mission keeps a "master" catalogue with one row per observation, but no two of
them name their columns the same way. Some give the end of the observation, some only
its length; some call the start ``time``, others ``start_time`` or ``start_date``; and
each marks planned-but-not-executed observations differently. :data:`MISSIONS` records
these differences, so that the rest of the package can treat every mission alike.

Missions also have more than one name (Chandra was AXAF, RXTE is often XTE, Suzaku was
Astro-E2). :func:`resolve_mission` accepts any of them.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

__all__ = ["MISSIONS", "MissionSpec", "normalize_name", "resolve_mission", "list_missions"]


@dataclass(frozen=True)
class MissionSpec:
    """
    How to read one mission's observation catalogue.

    Parameters
    ----------
    name : str
        Short canonical name, used in output column names (``nustar``, ``xmm``, ...).
    label : str
        Human-readable name.
    table : str
        Name of the HEASARC catalogue (TAP table).
    obsid_column : str
        Column holding the observation identifier.
    start_column : str
        Column holding the start of the observation, in MJD.
    end_column : str or None
        Column holding the end of the observation, in MJD. If the catalogue has none,
        the end is computed as start + ``duration_column`` (in seconds).
    duration_column : str or None
        Column holding the length of the observation in seconds, used only if
        ``end_column`` is None.
    exposure_column : str or None
        Column holding the exposure in seconds, reported in the output.
    name_column : str or None
        Column holding the target name given by the observer.
    radius_deg : float
        Default cone-search radius. It is roughly the half-width of the main
        instrument's field of view, so that observations with the source off-axis are
        also found.
    condition : str
        Extra ADQL condition (on table alias ``cat``) that removes observations that
        were planned but never executed.
    merge_contiguous : bool
        If True, catalogue rows that follow each other without a gap are merged into a
        single observation. Used for INTEGRAL, whose catalogue has one row per
        ~1-hour science window.
    aliases : tuple of str
        Other names of the mission. Matching ignores case, spaces, hyphens and
        underscores.
    """

    name: str
    label: str
    table: str
    obsid_column: str
    start_column: str
    end_column: str | None = None
    duration_column: str | None = None
    exposure_column: str | None = None
    name_column: str | None = "name"
    radius_deg: float = 0.1
    condition: str = ""
    merge_contiguous: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.end_column is None and self.duration_column is None:
            raise ValueError(f"{self.name}: give either end_column or duration_column")


def _status_in(*values):
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"cat.status IN ({quoted})"


_MISSION_LIST = [
    MissionSpec(
        name="nustar",
        label="NuSTAR",
        table="numaster",
        obsid_column="obsid",
        start_column="time",
        end_column="end_time",
        exposure_column="exposure_a",
        radius_deg=0.1,
        # As in heasarc_retrieve_pipeline: zero exposure_a in numaster really means
        # "no data".
        condition=_status_in("archived", "observed", "processed") + " AND cat.exposure_a > 0",
    ),
    MissionSpec(
        name="nicer",
        label="NICER",
        table="nicermastr",
        obsid_column="obsid",
        start_column="time",
        end_column="end_time",
        exposure_column="exposure",
        radius_deg=0.05,
        # Zero exposure is kept: NICER's own pipeline sometimes filters away good data
        # and records zero exposure (see heasarc_retrieve_pipeline).
        condition="cat.exposure >= 0",
        aliases=("iss-nicer",),
    ),
    MissionSpec(
        name="xmm",
        label="XMM-Newton",
        table="xmmmaster",
        obsid_column="obsid",
        start_column="time",
        end_column="end_time",
        exposure_column="duration",
        radius_deg=0.25,
        condition=_status_in("archived", "observed", "processed") + " AND cat.duration >= 0",
        aliases=("xmm-newton", "newton", "xmm newton"),
    ),
    MissionSpec(
        name="chandra",
        label="Chandra",
        table="chanmaster",
        obsid_column="obsid",
        start_column="time",
        # chanmaster has no end time: use the exposure as the length.
        duration_column="exposure",
        exposure_column="exposure",
        radius_deg=0.2,
        condition=_status_in("archived", "observed"),
        aliases=("axaf", "cxo", "cxc"),
    ),
    MissionSpec(
        name="rxte",
        label="RXTE",
        table="xtemaster",
        obsid_column="obsid",
        start_column="time",
        # xtemaster has no end time either; duration is the elapsed time.
        duration_column="duration",
        exposure_column="exposure",
        name_column="target_name",
        radius_deg=0.5,
        condition=_status_in("archived", "observed", "processed"),
        aliases=("xte", "rossi", "rossi x-ray timing explorer"),
    ),
    MissionSpec(
        name="swift",
        label="Swift",
        table="swiftmastr",
        obsid_column="obsid",
        start_column="start_time",
        end_column="stop_time",
        exposure_column="xrt_exposure",
        radius_deg=0.2,
        aliases=("neil gehrels swift", "gehrels swift", "swift-xrt"),
    ),
    MissionSpec(
        name="suzaku",
        label="Suzaku",
        table="suzamaster",
        obsid_column="obsid",
        start_column="time",
        end_column="stop_time",
        exposure_column="exposure",
        radius_deg=0.2,
        aliases=("astro-e2",),
    ),
    MissionSpec(
        name="hitomi",
        label="Hitomi",
        table="hitomaster",
        obsid_column="obsid",
        start_column="time",
        end_column="stop_time",
        exposure_column="exposure",
        radius_deg=0.1,
        aliases=("astro-h",),
    ),
    MissionSpec(
        name="xrism",
        label="XRISM",
        table="xrismmastr",
        obsid_column="obsid",
        start_column="time",
        end_column="end_time",
        exposure_column="exposure",
        radius_deg=0.15,
        condition=_status_in("archived", "processed", "preprocessed"),
        aliases=("xarm",),
    ),
    MissionSpec(
        name="ixpe",
        label="IXPE",
        table="ixmaster",
        obsid_column="obsid",
        start_column="time",
        end_column="end_time",
        exposure_column="exposure_1",
        radius_deg=0.1,
        condition=_status_in("archived", "processed"),
    ),
    MissionSpec(
        name="asca",
        label="ASCA",
        table="ascamaster",
        obsid_column="sequence_number",
        start_column="time",
        end_column="end_time",
        exposure_column="sis_exposure",
        name_column="target_name",
        radius_deg=0.3,
        aliases=("astro-d",),
    ),
    MissionSpec(
        name="ginga",
        label="Ginga",
        table="gingalog",
        # gingalog has no observation identifier; the row number is the only one.
        obsid_column="__row",
        start_column="time",
        end_column="end_time",
        exposure_column="exposure",
        radius_deg=0.5,
        aliases=("astro-c",),
    ),
    MissionSpec(
        name="exosat",
        label="EXOSAT",
        table="exomaster",
        obsid_column="sequence_number",
        start_column="time",
        end_column="end_time",
        radius_deg=0.25,
    ),
    MissionSpec(
        name="rosat",
        label="ROSAT",
        table="rosmaster",
        obsid_column="seq_id",
        start_column="start_time",
        end_column="end_time",
        exposure_column="exposure",
        radius_deg=0.5,
    ),
    MissionSpec(
        name="bepposax",
        label="BeppoSAX",
        table="saxnfilog",
        obsid_column="seq_id",
        # start_time/end_time are strings in saxnfilog; the MJDs are start_date/end_date.
        start_column="start_date",
        end_column="end_date",
        exposure_column="mecs_exposure",
        radius_deg=0.3,
        condition="cat.obs_perf != 'no'",
        aliases=("sax", "beppo sax"),
    ),
    MissionSpec(
        name="integral",
        label="INTEGRAL",
        table="intscw",
        obsid_column="scw_id",
        start_column="start_date",
        end_column="end_date",
        exposure_column="good_isgri",
        name_column=None,
        # IBIS/ISGRI's fully coded field of view is about 9x9 degrees.
        radius_deg=5.0,
        condition="cat.scw_type = 'pointing'",
        merge_contiguous=True,
    ),
]


def normalize_name(name: str) -> str:
    """
    Reduce a mission name to lowercase letters and digits.

    Examples
    --------
    >>> normalize_name("XMM-Newton")
    'xmmnewton'
    >>> normalize_name(" Astro_E2 ")
    'astroe2'
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


MISSIONS: dict[str, MissionSpec] = {m.name: m for m in _MISSION_LIST}
"""Every supported mission, by canonical name."""


def _build_alias_map():
    alias_map = {}
    for mission in _MISSION_LIST:
        for alias in (mission.name, mission.label, mission.table, *mission.aliases):
            key = normalize_name(alias)
            previous = alias_map.setdefault(key, mission.name)
            if previous != mission.name:
                raise ValueError(f"Alias {alias!r} names both {previous} and {mission.name}")
    return alias_map


_ALIASES = _build_alias_map()


def resolve_mission(name: str | MissionSpec) -> MissionSpec:
    """
    Find a mission from any of its names.

    Parameters
    ----------
    name : str or MissionSpec
        Mission name, alias, or catalogue name. Case, spaces, hyphens and underscores
        are ignored. A ``MissionSpec`` is returned unchanged.

    Returns
    -------
    MissionSpec

    Raises
    ------
    ValueError
        If the name is unknown. The message suggests close matches.

    Examples
    --------
    >>> resolve_mission("AXAF").name
    'chandra'
    >>> resolve_mission("XTE").name
    'rxte'
    >>> resolve_mission("XMM-Newton").name
    'xmm'
    """
    if isinstance(name, MissionSpec):
        return name
    key = normalize_name(name)
    if key in _ALIASES:
        return MISSIONS[_ALIASES[key]]
    close = difflib.get_close_matches(key, _ALIASES, n=3, cutoff=0.6)
    hint = ""
    if close:
        hint = " Did you mean " + " or ".join(sorted({_ALIASES[c] for c in close})) + "?"
    raise ValueError(
        f"Unknown mission {name!r}.{hint} Known missions: {', '.join(sorted(MISSIONS))}"
    )


def list_missions() -> str:
    """
    A text table of the supported missions, their aliases and default search radius.
    """
    lines = [f"{'name':<10} {'catalogue':<11} {'radius':>7}  aliases"]
    for m in _MISSION_LIST:
        aliases = ", ".join((m.label, *m.aliases))
        lines.append(f"{m.name:<10} {m.table:<11} {m.radius_deg:>6.2f}d  {aliases}")
    return "\n".join(lines)
