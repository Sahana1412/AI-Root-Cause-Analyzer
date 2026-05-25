"""
action_simulator.py
Simulates the effect of applying a recommended action on system metrics.
Returns "before" and "after" states to visualize recovery.
"""

import json
import copy
import random
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass


@dataclass
class SimulationResult:
    action_type: str
    target_service: str
    success: bool
    duration_seconds: int
    message: str
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    recovery_timeline: List[Dict]   # t+0, t+30s, t+60s, t+120s snapshots


# Baseline healthy metrics per service
HEALTHY_BASELINES = {
    "api-gateway": {
        "cpu_percent": 25, "memory_percent": 47, "latency_ms": 130,
        "error_rate_percent": 0.5, "db_connections": 0,
    },
    "order-service": {
        "cpu_percent": 22, "memory_percent": 55, "latency_ms": 110,
        "error_rate_percent": 0.3, "db_connections": 52,
    },
    "db-primary": {
        "cpu_percent": 33, "memory_percent": 64, "latency_ms": 16,
        "error_rate_percent": 0.0, "db_connections": 52,
    },
    "payment-service": {
        "cpu_percent": 18, "memory_percent": 42, "latency_ms": 95,
        "error_rate_percent": 0.2, "db_connections": 20,
    },
}

# Incident (crisis) state metrics
INCIDENT_STATE = {
    "api-gateway": {
        "cpu_percent": 81, "memory_percent": 65, "latency_ms": 3500,
        "error_rate_percent": 94.2, "db_connections": 0,
    },
    "order-service": {
        "cpu_percent": 92, "memory_percent": 79, "latency_ms": 3000,
        "error_rate_percent": 98.1, "db_connections": 500,
    },
    "db-primary": {
        "cpu_percent": 97, "memory_percent": 91, "latency_ms": 3000,
        "error_rate_percent": 45.0, "db_connections": 500,
    },
    "payment-service": {
        "cpu_percent": 55, "memory_percent": 58, "latency_ms": 2800,
        "error_rate_percent": 85.0, "db_connections": 0,
    },
}


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * t


def _jitter(val: float, pct: float = 0.05) -> float:
    """Add small random noise."""
    return val * (1 + random.uniform(-pct, pct))


def simulate_rollback_deployment(target_service: str) -> SimulationResult:
    before = copy.deepcopy(INCIDENT_STATE)
    after  = copy.deepcopy(HEALTHY_BASELINES)

    # Recovery timeline: 0s → 30s → 90s → 180s
    recovery = []
    t_points = [(0, 0.0), (30, 0.1), (60, 0.35), (90, 0.65), (120, 0.85), (180, 1.0)]

    for t, progress in t_points:
        snapshot = {}
        for svc in INCIDENT_STATE:
            crisis  = INCIDENT_STATE[svc]
            healthy = HEALTHY_BASELINES.get(svc, crisis)
            snapshot[svc] = {
                metric: round(_jitter(_lerp(crisis[metric], healthy[metric], progress)), 1)
                for metric in crisis
            }
        recovery.append({"t_seconds": t, "progress": round(progress, 2), "metrics": snapshot})

    return SimulationResult(
        action_type="rollback_deployment",
        target_service=target_service,
        success=True,
        duration_seconds=180,
        message=(
            f"✅ Rollback of {target_service} initiated. "
            f"Reverting to previous stable version. "
            f"Connection leak eliminated. System recovering over next 3 minutes."
        ),
        before_state=before,
        after_state=after,
        recovery_timeline=recovery,
    )


def simulate_restart_service(target_service: str) -> SimulationResult:
    before = copy.deepcopy(INCIDENT_STATE)
    after  = copy.deepcopy(HEALTHY_BASELINES)

    # Restart is faster but has a brief downtime dip at t=30s
    recovery = []
    t_points = [(0, 0.0), (15, -0.05), (30, 0.0), (60, 0.55), (90, 0.80), (120, 1.0)]

    for t, progress in t_points:
        snapshot = {}
        effective = max(0.0, progress)
        for svc in INCIDENT_STATE:
            crisis  = INCIDENT_STATE[svc]
            healthy = HEALTHY_BASELINES.get(svc, crisis)
            snapshot[svc] = {
                metric: round(_jitter(_lerp(crisis[metric], healthy[metric], effective)), 1)
                for metric in crisis
            }
        recovery.append({"t_seconds": t, "progress": round(progress, 2), "metrics": snapshot})

    return SimulationResult(
        action_type="restart_service",
        target_service=target_service,
        success=True,
        duration_seconds=120,
        message=(
            f"✅ {target_service} restart initiated. "
            f"Brief 15-second downtime as service restarts. "
            f"Connection pool cleared. Recovery expected within 2 minutes."
        ),
        before_state=before,
        after_state=after,
        recovery_timeline=recovery,
    )


def simulate_scale_resources(target_service: str) -> SimulationResult:
    before = copy.deepcopy(INCIDENT_STATE)
    after  = copy.deepcopy(HEALTHY_BASELINES)
    # Scale-out is gentler — gradual load distribution
    for svc in after:
        after[svc]["cpu_percent"] *= 0.6  # more instances = lower CPU per pod

    recovery = []
    t_points = [(0, 0.0), (30, 0.2), (60, 0.5), (120, 0.8), (180, 1.0)]
    for t, progress in t_points:
        snapshot = {}
        for svc in INCIDENT_STATE:
            crisis  = INCIDENT_STATE[svc]
            healthy = HEALTHY_BASELINES.get(svc, crisis)
            snapshot[svc] = {
                metric: round(_jitter(_lerp(crisis[metric], healthy[metric], progress)), 1)
                for metric in crisis
            }
        recovery.append({"t_seconds": t, "progress": round(progress, 2), "metrics": snapshot})

    return SimulationResult(
        action_type="scale_resources",
        target_service=target_service,
        success=True,
        duration_seconds=180,
        message=(
            f"✅ Scaling {target_service} from 2 → 6 replicas. "
            f"Load distributing across new pods. "
            f"CPU and latency normalizing over next 3 minutes."
        ),
        before_state=before,
        after_state=after,
        recovery_timeline=recovery,
    )


def run_simulation(action_type: str, target_service: str) -> SimulationResult:
    """Entry point: dispatch to the correct simulation."""
    simulators = {
        "rollback_deployment": simulate_rollback_deployment,
        "restart_service":     simulate_restart_service,
        "scale_resources":     simulate_scale_resources,
    }
    fn = simulators.get(action_type, simulate_restart_service)
    return fn(target_service)


def simulation_to_dict(sim: SimulationResult) -> Dict[str, Any]:
    return {
        "action_type":       sim.action_type,
        "target_service":    sim.target_service,
        "success":           sim.success,
        "duration_seconds":  sim.duration_seconds,
        "message":           sim.message,
        "before_state":      sim.before_state,
        "after_state":       sim.after_state,
        "recovery_timeline": sim.recovery_timeline,
    }
