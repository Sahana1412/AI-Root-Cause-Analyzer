"""
log_parser.py
Parses structured logs to extract error patterns, cascades, and key signals.
"""

import json
import re
from typing import List, Dict, Any, Tuple
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class LogPattern:
    pattern_id: str
    description: str
    count: int
    first_seen: str
    last_seen: str
    services: List[str]
    severity: str
    sample_message: str


@dataclass
class ParsedLogs:
    total_entries: int
    error_count: int
    critical_count: int
    warn_count: int
    patterns: List[LogPattern]
    error_cascade: List[Dict]      # ordered chain of errors
    affected_services: List[str]
    incident_window: Tuple[str, str]  # (start, end)
    key_signals: List[str]         # human-readable bullet points


KNOWN_PATTERNS = [
    {
        "id": "DB_TIMEOUT",
        "regex": r"(database|db).*(timeout|timed out|connection refused)",
        "description": "Database connection timeout",
        "severity": "critical",
    },
    {
        "id": "DB_MAX_CONN",
        "regex": r"max connections reached|connection pool.*full|rejecting new connections",
        "description": "Database max connections exhausted",
        "severity": "critical",
    },
    {
        "id": "DB_DEADLOCK",
        "regex": r"deadlock detected",
        "description": "Database deadlock",
        "severity": "high",
    },
    {
        "id": "CIRCUIT_OPEN",
        "regex": r"circuit breaker.*(open|tripped)",
        "description": "Circuit breaker opened (downstream failure)",
        "severity": "high",
    },
    {
        "id": "UPSTREAM_DOWN",
        "regex": r"(upstream|downstream|dependency).*(unreachable|down|unavailable)",
        "description": "Upstream/downstream service unreachable",
        "severity": "high",
    },
    {
        "id": "HIGH_ERROR_RATE",
        "regex": r"error rate.*(exceeded|threshold)",
        "description": "Error rate threshold exceeded",
        "severity": "critical",
    },
    {
        "id": "HTTP_5XX",
        "regex": r"5\d\d (service unavailable|internal server error|bad gateway)",
        "description": "HTTP 5xx error returned to clients",
        "severity": "high",
    },
    {
        "id": "CONN_POOL_HIGH",
        "regex": r"connection pool.*(utilization|usage).*(7[0-9]|8[0-9]|9[0-9])%",
        "description": "Connection pool utilization high",
        "severity": "medium",
    },
    {
        "id": "HIGH_LATENCY",
        "regex": r"latency (high|spike).*(ms|milliseconds?)",
        "description": "High query/request latency",
        "severity": "medium",
    },
]


def load_logs(filepath: str = "data/logs.json") -> List[Dict]:
    with open(filepath) as f:
        return json.load(f)


def match_patterns(message: str) -> List[str]:
    """Return list of pattern IDs matching this log message."""
    msg_lower = message.lower()
    matched = []
    for p in KNOWN_PATTERNS:
        if re.search(p["regex"], msg_lower):
            matched.append(p["id"])
    return matched


def parse_logs(logs: List[Dict]) -> ParsedLogs:
    error_logs    = [l for l in logs if l["level"] in ("ERROR", "CRITICAL")]
    warn_logs     = [l for l in logs if l["level"] == "WARN"]
    critical_logs = [l for l in logs if l["level"] == "CRITICAL"]

    # Pattern matching
    pattern_hits: Dict[str, Dict] = {}  # pattern_id -> aggregated info
    for log in logs:
        if log["level"] not in ("ERROR", "CRITICAL", "WARN"):
            continue
        matched = match_patterns(log["message"])
        for pid in matched:
            if pid not in pattern_hits:
                pattern_hits[pid] = {
                    "first_seen": log["timestamp"],
                    "last_seen": log["timestamp"],
                    "count": 0,
                    "services": set(),
                    "sample": log["message"],
                }
            entry = pattern_hits[pid]
            entry["count"] += 1
            entry["services"].add(log["service"])
            if log["timestamp"] < entry["first_seen"]:
                entry["first_seen"] = log["timestamp"]
            if log["timestamp"] > entry["last_seen"]:
                entry["last_seen"] = log["timestamp"]

    # Build LogPattern objects
    patterns: List[LogPattern] = []
    pattern_meta = {p["id"]: p for p in KNOWN_PATTERNS}
    for pid, data in pattern_hits.items():
        meta = pattern_meta.get(pid, {})
        patterns.append(LogPattern(
            pattern_id=pid,
            description=meta.get("description", pid),
            count=data["count"],
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            services=sorted(data["services"]),
            severity=meta.get("severity", "medium"),
            sample_message=data["sample"],
        ))
    patterns.sort(key=lambda p: p.first_seen)

    # Build error cascade (ordered unique error events)
    cascade = []
    seen_msgs: set = set()
    for log in sorted(logs, key=lambda l: l["timestamp"]):
        if log["level"] in ("ERROR", "CRITICAL"):
            key = f"{log['service']}:{log['message'][:60]}"
            if key not in seen_msgs:
                seen_msgs.add(key)
                cascade.append({
                    "timestamp": log["timestamp"],
                    "service": log["service"],
                    "level": log["level"],
                    "message": log["message"],
                })

    # Affected services
    affected = sorted({l["service"] for l in error_logs})

    # Incident window
    error_times = sorted(l["timestamp"] for l in error_logs)
    incident_window = (
        (error_times[0], error_times[-1]) if error_times else ("", "")
    )

    # Key signals (human-readable)
    key_signals = _extract_key_signals(patterns, cascade, logs)

    return ParsedLogs(
        total_entries=len(logs),
        error_count=len(error_logs),
        critical_count=len(critical_logs),
        warn_count=len(warn_logs),
        patterns=patterns,
        error_cascade=cascade,
        affected_services=affected,
        incident_window=incident_window,
        key_signals=key_signals,
    )


def _extract_key_signals(patterns, cascade, logs) -> List[str]:
    signals = []

    # DB signals
    db_timeout = next((p for p in patterns if p.pattern_id == "DB_TIMEOUT"), None)
    db_max     = next((p for p in patterns if p.pattern_id == "DB_MAX_CONN"), None)
    deadlock   = next((p for p in patterns if p.pattern_id == "DB_DEADLOCK"), None)
    circuit    = next((p for p in patterns if p.pattern_id == "CIRCUIT_OPEN"), None)

    if db_timeout:
        signals.append(
            f"Database timeouts appeared {db_timeout.count}x starting {db_timeout.first_seen[:19]}"
        )
    if db_max:
        signals.append(
            f"Database max connections (500) reached at {db_max.first_seen[:19]}"
        )
    if deadlock:
        signals.append(
            f"Database deadlocks detected ({deadlock.count}x) on inventory table"
        )
    if circuit:
        signals.append(
            f"Circuit breakers opened on: {', '.join(circuit.services)}"
        )

    # Cascade depth
    if len(cascade) >= 4:
        svc_chain = " → ".join(dict.fromkeys(e["service"] for e in cascade[:5]))
        signals.append(f"Failure cascade observed: {svc_chain}")

    # Recovery
    recovery = [l for l in logs if l["level"] == "INFO" and "recovered" in l["message"].lower()]
    if recovery:
        signals.append(f"System recovery logged at {recovery[-1]['timestamp'][:19]}")

    return signals


def parsed_logs_to_dict(pl: ParsedLogs) -> Dict[str, Any]:
    return {
        "total_entries": pl.total_entries,
        "error_count": pl.error_count,
        "critical_count": pl.critical_count,
        "warn_count": pl.warn_count,
        "patterns": [vars(p) for p in pl.patterns],
        "error_cascade": pl.error_cascade,
        "affected_services": pl.affected_services,
        "incident_window": list(pl.incident_window),
        "key_signals": pl.key_signals,
    }


if __name__ == "__main__":
    logs = load_logs()
    pl   = parse_logs(logs)
    print(f"Parsed {pl.total_entries} logs: {pl.error_count} errors, {pl.critical_count} critical")
    print(f"Patterns found: {[p.pattern_id for p in pl.patterns]}")
    print(f"Key signals:")
    for s in pl.key_signals:
        print(f"  • {s}")
