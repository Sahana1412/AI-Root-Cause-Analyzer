"""
anomaly_detector.py
Detects anomalies in metrics using z-score and threshold-based methods.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class Anomaly:
    timestamp: str
    service: str
    metric: str
    value: float
    baseline: float
    z_score: float
    severity: str  # low, medium, high, critical
    description: str


THRESHOLDS = {
    "cpu_percent":         {"warn": 70,  "critical": 90},
    "memory_percent":      {"warn": 80,  "critical": 92},
    "latency_ms":          {"warn": 500, "critical": 2000},
    "error_rate_percent":  {"warn": 5,   "critical": 20},
    "db_connections":      {"warn": 350, "critical": 480},
}

ZSCORE_THRESHOLD = 2.5  # Flag if value is >2.5 std devs from rolling mean


def load_metrics(filepath: str = "data/metrics.csv") -> pd.DataFrame:
    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    df.sort_values("timestamp", inplace=True)
    return df


def compute_zscore(series: pd.Series, window: int = 5) -> pd.Series:
    """Rolling z-score relative to a backward-looking window."""
    rolling_mean = series.rolling(window=window, min_periods=2).mean()
    rolling_std  = series.rolling(window=window, min_periods=2).std()
    z = (series - rolling_mean) / (rolling_std + 1e-9)
    return z


def severity_from_value(metric: str, value: float) -> str:
    if metric not in THRESHOLDS:
        return "low"
    crit = THRESHOLDS[metric]["critical"]
    warn = THRESHOLDS[metric]["warn"]
    if value >= crit:
        return "critical"
    elif value >= warn:
        return "high"
    elif value >= warn * 0.7:
        return "medium"
    return "low"


def detect_anomalies(df: pd.DataFrame) -> List[Anomaly]:
    anomalies: List[Anomaly] = []
    numeric_cols = ["cpu_percent", "memory_percent", "latency_ms",
                    "error_rate_percent", "db_connections"]

    for service, group in df.groupby("service"):
        group = group.sort_values("timestamp").reset_index(drop=True)

        for col in numeric_cols:
            if col not in group.columns:
                continue

            zscores = compute_zscore(group[col])
            baseline = group[col].median()

            for i, (_, row) in enumerate(group.iterrows()):
                value = row[col]
                z     = float(zscores.iloc[i]) if not pd.isna(zscores.iloc[i]) else 0.0
                sev   = severity_from_value(col, value)

                # Flag if z-score is high OR threshold is breached
                is_zscore_anomaly   = abs(z) >= ZSCORE_THRESHOLD
                is_threshold_breach = sev in ("high", "critical")

                if is_zscore_anomaly or is_threshold_breach:
                    metric_label = col.replace("_", " ").title()
                    desc = (
                        f"{metric_label} spike on {service}: "
                        f"{value:.1f} (baseline ~{baseline:.1f}, z={z:.2f})"
                    )
                    anomalies.append(Anomaly(
                        timestamp=str(row["timestamp"]),
                        service=service,
                        metric=col,
                        value=round(value, 2),
                        baseline=round(baseline, 2),
                        z_score=round(z, 2),
                        severity=sev,
                        description=desc,
                    ))

    # Sort by timestamp, then severity
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    anomalies.sort(key=lambda a: (a.timestamp, sev_order.get(a.severity, 4)))
    return anomalies


def get_anomaly_summary(anomalies: List[Anomaly]) -> Dict[str, Any]:
    if not anomalies:
        return {"total": 0, "by_severity": {}, "by_service": {}, "peak_time": None}

    by_sev: Dict[str, int] = {}
    by_svc: Dict[str, int] = {}
    for a in anomalies:
        by_sev[a.severity] = by_sev.get(a.severity, 0) + 1
        by_svc[a.service]  = by_svc.get(a.service, 0) + 1

    # Find peak anomaly window (minute with most anomalies)
    from collections import Counter
    minute_counts = Counter(a.timestamp[:16] for a in anomalies)  # truncate to minute
    peak_time = minute_counts.most_common(1)[0][0] if minute_counts else None

    return {
        "total": len(anomalies),
        "by_severity": by_sev,
        "by_service": by_svc,
        "peak_time": peak_time,
        "most_affected_service": max(by_svc, key=by_svc.get) if by_svc else None,
    }


def anomalies_to_dict(anomalies: List[Anomaly]) -> List[Dict]:
    return [vars(a) for a in anomalies]


if __name__ == "__main__":
    df = load_metrics()
    anomalies = detect_anomalies(df)
    summary   = get_anomaly_summary(anomalies)
    print(f"Detected {summary['total']} anomalies")
    print(f"By severity: {summary['by_severity']}")
    print(f"Peak time: {summary['peak_time']}")
