"""
timeline_builder.py
Combines logs + metrics + events into a unified chronological incident timeline.
"""

import json
import pandas as pd
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class TimelineEvent:
    timestamp: str
    event_type: str      # log | metric_anomaly | deployment | alert | incident | action
    source: str          # service or system name
    severity: str        # info | warn | high | critical
    title: str
    detail: str
    icon: str            # emoji for UI rendering


def load_events(filepath: str = "data/events.json") -> List[Dict]:
    with open(filepath) as f:
        return json.load(f)


def build_timeline(
    logs: List[Dict],
    anomalies: List[Dict],
    events: List[Dict],
) -> List[TimelineEvent]:
    """
    Merge all data sources into a single sorted timeline.
    Deduplicates and assigns severity/icons for each event type.
    """
    timeline: List[TimelineEvent] = []

    # 1. Key log entries (errors + criticals only, deduplicated per service+msg combo)
    seen_log_keys = set()
    for log in logs:
        if log["level"] not in ("ERROR", "CRITICAL", "WARN"):
            continue
        key = f"{log['service']}|{log['message'][:50]}"
        if key in seen_log_keys:
            continue
        seen_log_keys.add(key)

        sev = {
            "CRITICAL": "critical",
            "ERROR": "high",
            "WARN": "medium",
        }.get(log["level"], "info")

        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(sev, "⚪")

        timeline.append(TimelineEvent(
            timestamp=log["timestamp"],
            event_type="log",
            source=log["service"],
            severity=sev,
            title=f"[{log['level']}] {log['service']}",
            detail=log["message"],
            icon=icon,
        ))

    # 2. Metric anomalies (critical/high only to keep timeline clean)
    for anomaly in anomalies:
        if anomaly.get("severity") not in ("critical", "high"):
            continue
        timeline.append(TimelineEvent(
            timestamp=anomaly["timestamp"],
            event_type="metric_anomaly",
            source=anomaly["service"],
            severity=anomaly["severity"],
            title=f"📈 Metric Spike: {anomaly['service']}",
            detail=anomaly["description"],
            icon="📈",
        ))

    # 3. Deployment & infrastructure events
    for event in events:
        etype = event.get("type", "")
        ts    = event.get("timestamp", "")

        if etype == "deployment":
            sev  = "medium" if event.get("status") == "success" else "high"
            icon = "🚀"
            changes = "; ".join(event.get("changes", []))
            timeline.append(TimelineEvent(
                timestamp=ts,
                event_type="deployment",
                source=event.get("service", ""),
                severity=sev,
                title=f"🚀 Deploy: {event.get('service')} → {event.get('version')}",
                detail=f"Changes: {changes}" if changes else "No change notes",
                icon=icon,
            ))

        elif etype == "config_change":
            changes = "; ".join(event.get("changes", []))
            timeline.append(TimelineEvent(
                timestamp=ts,
                event_type="config_change",
                source=event.get("service", ""),
                severity="medium",
                title=f"⚙️ Config Change: {event.get('service')}",
                detail=changes,
                icon="⚙️",
            ))

        elif etype == "alert":
            sev  = "critical" if event.get("severity") == "critical" else "high"
            icon = "🚨"
            timeline.append(TimelineEvent(
                timestamp=ts,
                event_type="alert",
                source=event.get("service", ""),
                severity=sev,
                title=f"🚨 Alert: {event.get('alert_name')}",
                detail=(
                    f"{event.get('service')}: {event.get('alert_name')} — "
                    f"threshold={event.get('threshold')}, actual={event.get('actual_value')}"
                ),
                icon=icon,
            ))

        elif etype == "incident":
            sev  = "critical" if event.get("status") == "active" else "info"
            icon = "🔥" if event.get("status") == "active" else "✅"
            timeline.append(TimelineEvent(
                timestamp=ts,
                event_type="incident",
                source="ops",
                severity=sev,
                title=f"{icon} Incident {event.get('status','').upper()}: {event.get('incident_id')}",
                detail=event.get("resolution") or event.get("title", ""),
                icon=icon,
            ))

        elif etype == "action":
            timeline.append(TimelineEvent(
                timestamp=ts,
                event_type="action",
                source=event.get("service", ""),
                severity="info",
                title=f"🛠️ Action: {event.get('action','').title()} {event.get('service')}",
                detail=event.get("outcome", ""),
                icon="🛠️",
            ))

    # Sort chronologically
    timeline.sort(key=lambda e: e.timestamp)
    return timeline


def timeline_to_dict(timeline: List[TimelineEvent]) -> List[Dict]:
    return [vars(e) for e in timeline]


def get_incident_phases(timeline: List[TimelineEvent]) -> Dict[str, Any]:
    """
    Identify distinct phases of the incident from the timeline.
    Returns phase boundaries with labels.
    """
    phases = []
    has_deployment  = any(e.event_type == "deployment" for e in timeline)
    first_anomaly   = next((e for e in timeline if e.severity in ("critical","high")), None)
    peak_events     = [e for e in timeline if e.severity == "critical"]
    recovery_events = [e for e in timeline if "recover" in e.detail.lower() or "resolved" in e.title.lower()]

    if has_deployment:
        dep = next(e for e in timeline if e.event_type == "deployment")
        phases.append({"phase": "Pre-incident Change", "timestamp": dep.timestamp, "color": "yellow"})

    if first_anomaly:
        phases.append({"phase": "Incident Onset", "timestamp": first_anomaly.timestamp, "color": "orange"})

    if peak_events:
        phases.append({"phase": "Peak Impact", "timestamp": peak_events[0].timestamp, "color": "red"})

    if recovery_events:
        phases.append({"phase": "Recovery", "timestamp": recovery_events[0].timestamp, "color": "green"})

    return {"phases": phases, "total_events": len(timeline)}


if __name__ == "__main__":
    from modules.log_parser import load_logs, parse_logs, parsed_logs_to_dict
    from modules.anomaly_detector import load_metrics, detect_anomalies, anomalies_to_dict

    logs      = load_logs()
    metrics   = load_metrics()
    events    = load_events()
    anomalies = anomalies_to_dict(detect_anomalies(metrics))
    timeline  = build_timeline(logs, anomalies, events)

    print(f"Timeline has {len(timeline)} events")
    for e in timeline[:5]:
        print(f"  {e.timestamp[:19]} | {e.icon} {e.title}")
