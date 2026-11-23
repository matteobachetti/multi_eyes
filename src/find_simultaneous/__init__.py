"""Find simultaneous or quasi-simultaneous observations of a source by several missions."""

from .missions import MISSIONS, MissionSpec, resolve_mission

__all__ = ["MISSIONS", "MissionSpec", "resolve_mission"]
__version__ = "0.1.0.dev0"
