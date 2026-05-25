"""
decision_module.py
Maps root cause analysis results to concrete recommended actions.
Provides action metadata, risk assessment, and execution plan.
"""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ActionPlan:
    action_type: str           # restart_service | rollback_deployment | scale_resources | manual_review
    target_service: str
    priority: str              # immediate | high | medium | low
    estimated_downtime_mins: float
    risk_level: str            # low | medium | high
    steps: List[str]
    expected_outcome: str
    rollback_plan: str
    success_metrics: List[str]
    icon: str


ACTION_CATALOG = {
    "restart_service": {
        "icon": "🔄",
        "risk_level": "medium",
        "estimated_downtime_mins": 2.0,
        "base_steps": [
            "Send SIGTERM to gracefully drain active connections",
            "Wait for in-flight requests to complete (30s grace period)",
            "Issue hard restart if not stopped within grace period",
            "Wait for service health check to pass (/health endpoint)",
            "Verify error rate normalizes in monitoring dashboard",
        ],
        "expected_outcome": "Service restarts with clean state; connections/memory reset",
        "rollback_plan": "If service fails to start, revert to last known-good image tag",
        "success_metrics": [
            "Service health check returns 200 within 60s",
            "Error rate < 2% within 3 minutes",
            "Connection count normalizes",
        ],
    },
    "rollback_deployment": {
        "icon": "⏪",
        "risk_level": "low",
        "estimated_downtime_mins": 3.0,
        "base_steps": [
            "Identify the previous stable version from deployment history",
            "Trigger rollback via CI/CD pipeline (or kubectl rollout undo)",
            "Monitor deployment rollout progress",
            "Verify new pods are running the correct image tag",
            "Run smoke tests on critical paths (checkout, payment)",
            "Confirm error rate drops below threshold",
        ],
        "expected_outcome": "Service reverts to previous stable version; bug eliminated",
        "rollback_plan": "If rollback fails, escalate to manual hotfix or feature flag disable",
        "success_metrics": [
            "Correct image version running on all pods",
            "Error rate < 1% within 5 minutes",
            "Business KPIs (orders/min) return to baseline",
        ],
    },
    "scale_resources": {
        "icon": "📈",
        "risk_level": "low",
        "estimated_downtime_mins": 0.5,
        "base_steps": [
            "Determine target scale factor based on current load metrics",
            "Update HPA (Horizontal Pod Autoscaler) target replicas",
            "Verify new pods start and pass readiness checks",
            "Confirm load distributes evenly across new instances",
            "Monitor CPU/memory utilization across pods",
        ],
        "expected_outcome": "Increased capacity absorbs load; performance returns to normal",
        "rollback_plan": "Scale back down to original count if new pods cause instability",
        "success_metrics": [
            "CPU utilization per pod < 70%",
            "Latency p99 < 500ms",
            "No OOM events in new pods",
        ],
    },
    "manual_review": {
        "icon": "🔍",
        "risk_level": "low",
        "estimated_downtime_mins": 0,
        "base_steps": [
            "Collect full thread dump and heap dump from affected service",
            "Review recent code changes in version control",
            "Reproduce the issue in staging environment",
            "Engage on-call engineer and relevant team leads",
            "Document findings in incident ticket",
        ],
        "expected_outcome": "Root cause confirmed with sufficient evidence for targeted fix",
        "rollback_plan": "Apply temporary mitigation while investigation continues",
        "success_metrics": [
            "Root cause documented with evidence",
            "Fix PR created and reviewed",
            "Staging environment reproduces and validates fix",
        ],
    },
}

PRIORITY_MAP = {
    "critical": "immediate",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def build_action_plan(
    recommended_action: str,
    target_service: str,
    confidence: float,
    incident_severity: str = "high",
) -> ActionPlan:
    """
    Build a concrete action plan for the recommended action.
    """
    action_key  = recommended_action if recommended_action in ACTION_CATALOG else "manual_review"
    catalog     = ACTION_CATALOG[action_key]
    priority    = PRIORITY_MAP.get(incident_severity, "high") if confidence >= 0.6 else "high"

    # Customize steps with the target service name
    steps = [s.replace("<service>", target_service) for s in catalog["base_steps"]]

    return ActionPlan(
        action_type=action_key,
        target_service=target_service,
        priority=priority,
        estimated_downtime_mins=catalog["estimated_downtime_mins"],
        risk_level=catalog["risk_level"],
        steps=steps,
        expected_outcome=catalog["expected_outcome"],
        rollback_plan=catalog["rollback_plan"],
        success_metrics=catalog["success_metrics"],
        icon=catalog["icon"],
    )


def get_confidence_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "High Confidence"
    elif confidence >= 0.65:
        return "Medium Confidence"
    elif confidence >= 0.40:
        return "Low Confidence"
    return "Very Low Confidence"


def get_confidence_color(confidence: float) -> str:
    if confidence >= 0.85:
        return "#22c55e"   # green
    elif confidence >= 0.65:
        return "#f59e0b"   # amber
    elif confidence >= 0.40:
        return "#ef4444"   # red
    return "#6b7280"       # gray


def action_plan_to_dict(plan: ActionPlan) -> Dict[str, Any]:
    return vars(plan)
