"""FastAPI routers for the Control Plane (Stream B)."""

from control_plane.api.agents import build_agents_router
from control_plane.api.health import build_health_router
from control_plane.api.metrics import build_metrics_router
from control_plane.api.runs import build_runs_router
from control_plane.api.sessions import build_sessions_router

__all__ = [
    "build_agents_router",
    "build_health_router",
    "build_metrics_router",
    "build_runs_router",
    "build_sessions_router",
]
