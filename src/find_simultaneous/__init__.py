"""Find simultaneous or quasi-simultaneous observations of a source by several missions."""

from .group import assign_campaigns, group_matches
from .match import find_matches
from .missions import MISSIONS, MissionSpec, list_missions, resolve_mission
from .query import find_simultaneous, query_mission, resolve_source

__all__ = [
    "MISSIONS",
    "MissionSpec",
    "assign_campaigns",
    "find_matches",
    "find_simultaneous",
    "group_matches",
    "list_missions",
    "query_mission",
    "resolve_mission",
    "resolve_source",
]
try:
    from ._version import version as __version__
except ImportError:  # running from a source tree that was never installed
    __version__ = "unknown"
