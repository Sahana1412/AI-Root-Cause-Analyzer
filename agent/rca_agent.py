"""
rca_agent.py
AI Agent for Root Cause Analysis.
Uses an LLM (Claude or OpenAI) with structured reasoning to:
  - Correlate events
  - Identify root cause
  - Assign confidence score
  - Suggest fixes
  - Generate multiple hypotheses
"""

import os
import json
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# ─────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────

@dataclass
class Hypothesis:
    rank: int
    root_cause: str
    confidence: float          # 0.0 – 1.0
    evidence: List[str]
    affected_services: List[str]
    suggested_fix: str
    recommended_action: str    # restart_service | rollback_deployment | scale_resources | manual_review
    action_target: str         # which service/resource to act on
    explanation: str


@dataclass
class RCAResult:
    incident_summary: str
    primary_hypothesis: Hypothesis
    alternative_hypotheses: List[Hypothesis]
    timeline_correlation: str
    impact_assessment: str
    immediate_steps: List[str]
    prevention_steps: List[str]
    model_used: str
    analysis_duration_ms: int


# ─────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────

def build_agent_prompt(context: Dict[str, Any]) -> str:
    anomaly_summary  = context.get("anomaly_summary", {})
    log_summary      = context.get("log_summary", {})
    timeline_snippet = context.get("timeline_snippet", [])
    events_summary   = context.get("events_summary", [])

    # Format timeline (top 12 most important events)
    tl_lines = []
    for e in timeline_snippet[:12]:
        tl_lines.append(f"  [{e.get('timestamp','')[:19]}] {e.get('icon','')} {e.get('title','')} — {e.get('detail','')[:100]}")
    timeline_str = "\n".join(tl_lines) if tl_lines else "  (no timeline data)"

    # Format patterns
    patterns = log_summary.get("patterns", [])
    pattern_lines = []
    for p in patterns[:8]:
        pattern_lines.append(
            f"  • [{p.get('severity','').upper()}] {p.get('description','')} "
            f"(count={p.get('count',0)}, services={p.get('services',[])})"
        )
    patterns_str = "\n".join(pattern_lines) if pattern_lines else "  (none detected)"

    # Format anomaly summary
    by_svc = anomaly_summary.get("by_service", {})
    by_sev = anomaly_summary.get("by_severity", {})
    anomaly_str = (
        f"  Total anomalies: {anomaly_summary.get('total', 0)}\n"
        f"  By severity: {by_sev}\n"
        f"  By service: {by_svc}\n"
        f"  Peak anomaly time: {anomaly_summary.get('peak_time', 'N/A')}\n"
        f"  Most affected service: {anomaly_summary.get('most_affected_service', 'N/A')}"
    )

    # Format recent deployments
    deploys = [e for e in events_summary if e.get("type") == "deployment"]
    deploy_lines = []
    for d in deploys[-3:]:
        changes = "; ".join(d.get("changes", []))
        note    = d.get("note", "")
        deploy_lines.append(
            f"  • [{d.get('timestamp','')[:19]}] {d.get('service','')} "
            f"{d.get('previous_version','')} → {d.get('version','')} | {changes}"
            + (f" ⚠️ {note}" if note else "")
        )
    deploy_str = "\n".join(deploy_lines) if deploy_lines else "  (none)"

    key_signals = log_summary.get("key_signals", [])
    signals_str = "\n".join(f"  • {s}" for s in key_signals) or "  (none)"

    return f"""You are an expert Site Reliability Engineer (SRE) AI agent performing root cause analysis on a production incident.

## INCIDENT DATA

### Metric Anomalies
{anomaly_str}

### Log Error Patterns
{patterns_str}

### Key Signals
{signals_str}

### Incident Timeline (chronological)
{timeline_str}

### Recent Deployments & Config Changes
{deploy_str}

### Affected Services
{', '.join(log_summary.get('affected_services', []))}

---

## YOUR TASK

Analyze all the above data as a seasoned SRE. Reason step by step:

1. Identify the **root cause** — what was the fundamental trigger?
2. Trace the **failure cascade** — how did the root cause propagate?
3. Consider whether a **recent deployment or config change** contributed.
4. Assign a **confidence score** (0.0–1.0) based on available evidence.
5. Generate **2–3 hypotheses** ordered by likelihood.
6. Recommend the **single best action** to resolve the incident.
7. Provide **prevention recommendations**.

## RESPONSE FORMAT

Respond ONLY with valid JSON (no markdown, no backticks, no preamble):

{{
  "incident_summary": "<2-3 sentence summary of what happened>",
  "timeline_correlation": "<explanation of how events are correlated>",
  "impact_assessment": "<which services were affected and how severely>",
  "hypotheses": [
    {{
      "rank": 1,
      "root_cause": "<concise root cause statement>",
      "confidence": 0.0,
      "evidence": ["<evidence point 1>", "<evidence point 2>"],
      "affected_services": ["<service1>"],
      "suggested_fix": "<specific technical fix>",
      "recommended_action": "<restart_service|rollback_deployment|scale_resources|manual_review>",
      "action_target": "<service or resource name>",
      "explanation": "<detailed SRE explanation>"
    }}
  ],
  "immediate_steps": ["<step 1>", "<step 2>", "<step 3>"],
  "prevention_steps": ["<prevention 1>", "<prevention 2>"]
}}
"""


# ─────────────────────────────────────────────
# LLM Callers
# ─────────────────────────────────────────────

def call_claude(prompt: str, api_key: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def call_openai(prompt: str, api_key: str) -> str:
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.2,
    )
    return resp.choices[0].message.content


def call_mock_llm(prompt: str) -> str:
    """
    Deterministic mock LLM response for demo/testing without an API key.
    Returns a realistic RCA JSON based on the injected incident data.
    """
    return json.dumps({
        "incident_summary": (
            "A production P1 incident occurred on 2024-01-15 between 14:01-14:07 UTC. "
            "The order-service deployment v2.3.2 at 14:00:30 introduced a connection leak "
            "in the new bulk order processing code, rapidly exhausting all 500 database connections. "
            "This caused a cascading failure across order-service, payment-service, and api-gateway."
        ),
        "timeline_correlation": (
            "The sequence is clear: (1) order-service v2.3.2 deployed at 14:00:30 with updated DB queries; "
            "(2) DB connection count spiked from ~62 to 500 within 3 minutes; "
            "(3) DB timeouts cascaded into circuit breaker trips on order-service; "
            "(4) payment-service lost its upstream dependency; "
            "(5) api-gateway hit 94% error rate. "
            "The 4-minute window from deploy to full outage is classic connection leak behavior."
        ),
        "impact_assessment": (
            "Full outage of the checkout flow for ~5 minutes. "
            "api-gateway: 94% error rate. order-service: circuit breaker open (100% fail). "
            "payment-service: order validation failed. db-primary: max connections saturated. "
            "Estimated customer impact: all checkout attempts failed during 14:02-14:07 UTC."
        ),
        "hypotheses": [
            {
                "rank": 1,
                "root_cause": "Connection leak in order-service v2.3.2 bulk order processing code exhausted database connection pool",
                "confidence": 0.91,
                "evidence": [
                    "Deployment of v2.3.2 at 14:00:30 — 90 seconds before first DB timeouts",
                    "DB connections jumped from 62 → 500 in 3 minutes (abnormal ramp)",
                    "Change note: 'hotfix: removed N+1 query' suggests risky DB query changes",
                    "Deadlocks on inventory table (typical of concurrent bulk writes without proper locking)",
                    "DB max connections (500/500) exactly matches the new config limit set earlier"
                ],
                "affected_services": ["order-service", "db-primary", "payment-service", "api-gateway"],
                "suggested_fix": "Rollback order-service to v2.3.1 immediately. Add connection pool limit per service instance. Audit bulk order SQL for missing connection.close() calls.",
                "recommended_action": "rollback_deployment",
                "action_target": "order-service",
                "explanation": (
                    "The v2.3.2 deployment changed DB query patterns for bulk order processing. "
                    "The connection count trajectory (linear ramp to 500) is characteristic of a leak — "
                    "connections opened but not returned to the pool. Rolling back to v2.3.1 will "
                    "stop new connections from leaking. A DB restart will clear existing stale connections. "
                    "Future fix: add connection pool limits per service (max 50), add connection leak detection."
                )
            },
            {
                "rank": 2,
                "root_cause": "Database max_connections config change (300→500) masked earlier saturation, delaying detection of the leak",
                "confidence": 0.61,
                "evidence": [
                    "Config change at 11:30 increased max_connections from 300 to 500",
                    "Warning alert at 13:45 fired at 72% (pre-existing pressure)",
                    "Without the config change, saturation would have occurred earlier and been caught"
                ],
                "affected_services": ["db-primary"],
                "suggested_fix": "Revert max_connections to 300 OR implement per-service connection limits. Add alerting at 60% utilization.",
                "recommended_action": "manual_review",
                "action_target": "db-primary",
                "explanation": (
                    "The connection limit increase was a legitimate capacity change, but it masked "
                    "the underlying pressure. A more aggressive alert threshold would have caught "
                    "the connection ramp before it became critical. This is a contributing factor, not root cause."
                )
            },
            {
                "rank": 3,
                "root_cause": "Missing circuit breaker on db-primary connections allowed cascading failure to downstream services",
                "confidence": 0.38,
                "evidence": [
                    "Circuit breaker on order-service only tripped after 100% connection failure",
                    "No connection-level circuit breaker prevented pool exhaustion",
                    "Cascade spread to payment-service and api-gateway before circuit tripped"
                ],
                "affected_services": ["order-service", "payment-service"],
                "suggested_fix": "Implement connection-level circuit breaker. Add bulkhead pattern to isolate DB connections per service.",
                "recommended_action": "manual_review",
                "action_target": "order-service",
                "explanation": (
                    "A bulkhead pattern limiting each service to a max pool fraction would have "
                    "contained the blast radius. This is an architectural gap rather than the root cause."
                )
            }
        ],
        "immediate_steps": [
            "Rollback order-service to v2.3.1 immediately (est. 3 min)",
            "Restart db-primary to clear all stale connections (est. 2 min, brief downtime)",
            "Monitor db_connections metric — should normalize to <100 within 5 minutes",
            "Verify error rate on api-gateway drops below 5%"
        ],
        "prevention_steps": [
            "Add connection pool limits per service (max 50 connections per instance)",
            "Implement canary deployments for order-service (5% traffic before full rollout)",
            "Lower DB connection alert threshold to 60% utilization",
            "Add integration test that validates connection count under bulk order load",
            "Implement bulkhead pattern to prevent cascade failures"
        ]
    })


# ─────────────────────────────────────────────
# Main Agent
# ─────────────────────────────────────────────

def run_rca_agent(
    context: Dict[str, Any],
    llm_provider: str = "mock",
    api_key: Optional[str] = None,
) -> RCAResult:
    """
    Run the RCA agent with the provided context.
    llm_provider: "claude" | "openai" | "mock"
    """
    prompt = build_agent_prompt(context)
    start  = time.time()

    raw_response = ""
    model_used   = llm_provider

    try:
        if llm_provider == "claude" and api_key and ANTHROPIC_AVAILABLE:
            raw_response = call_claude(prompt, api_key)
            model_used   = "claude-sonnet-4-20250514"
        elif llm_provider == "openai" and api_key and OPENAI_AVAILABLE:
            raw_response = call_openai(prompt, api_key)
            model_used   = "gpt-4o"
        else:
            raw_response = call_mock_llm(prompt)
            model_used   = "mock-sre-agent-v1"
    except Exception as e:
        # Fallback to mock on error
        raw_response = call_mock_llm(prompt)
        model_used   = f"mock-fallback (error: {str(e)[:60]})"

    elapsed_ms = int((time.time() - start) * 1000)

    # Parse JSON response
    parsed = _parse_llm_response(raw_response)
    return _build_rca_result(parsed, model_used, elapsed_ms)


def _parse_llm_response(raw: str) -> Dict:
    """Strip markdown fences and parse JSON."""
    text = raw.strip()
    # Remove ```json ... ``` fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _build_rca_result(data: Dict, model_used: str, elapsed_ms: int) -> RCAResult:
    hypotheses_raw = data.get("hypotheses", [])
    hypotheses     = []
    for h in hypotheses_raw:
        hypotheses.append(Hypothesis(
            rank=h.get("rank", 1),
            root_cause=h.get("root_cause", ""),
            confidence=float(h.get("confidence", 0.5)),
            evidence=h.get("evidence", []),
            affected_services=h.get("affected_services", []),
            suggested_fix=h.get("suggested_fix", ""),
            recommended_action=h.get("recommended_action", "manual_review"),
            action_target=h.get("action_target", ""),
            explanation=h.get("explanation", ""),
        ))

    primary = hypotheses[0] if hypotheses else Hypothesis(
        rank=1, root_cause="Unknown", confidence=0.0,
        evidence=[], affected_services=[], suggested_fix="Manual investigation required",
        recommended_action="manual_review", action_target="",
        explanation="Insufficient data for automated analysis.",
    )
    alternatives = hypotheses[1:] if len(hypotheses) > 1 else []

    return RCAResult(
        incident_summary=data.get("incident_summary", ""),
        primary_hypothesis=primary,
        alternative_hypotheses=alternatives,
        timeline_correlation=data.get("timeline_correlation", ""),
        impact_assessment=data.get("impact_assessment", ""),
        immediate_steps=data.get("immediate_steps", []),
        prevention_steps=data.get("prevention_steps", []),
        model_used=model_used,
        analysis_duration_ms=elapsed_ms,
    )


def rca_result_to_dict(result: RCAResult) -> Dict[str, Any]:
    return {
        "incident_summary": result.incident_summary,
        "primary_hypothesis": vars(result.primary_hypothesis),
        "alternative_hypotheses": [vars(h) for h in result.alternative_hypotheses],
        "timeline_correlation": result.timeline_correlation,
        "impact_assessment": result.impact_assessment,
        "immediate_steps": result.immediate_steps,
        "prevention_steps": result.prevention_steps,
        "model_used": result.model_used,
        "analysis_duration_ms": result.analysis_duration_ms,
    }
