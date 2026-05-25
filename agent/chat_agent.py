"""
chat_agent.py
Conversational Q&A agent for incident follow-up questions.
Supports context-aware responses about the analyzed incident.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional


SYSTEM_PROMPT = """You are an expert SRE (Site Reliability Engineer) assistant analyzing a production incident.
You have full context about the incident: logs, metrics, deployment events, and root cause analysis.
Answer questions clearly and technically. Be concise but thorough.
When relevant, reference specific timestamps, services, or metrics from the incident data.
If asked about next steps, reference the recommended action plan.
Never make up data — only reference what's in the context provided."""


def build_chat_context(rca_result: Dict, timeline: List[Dict]) -> str:
    """Build a compact context string from the analysis results."""
    primary = rca_result.get("primary_hypothesis", {})
    tl_lines = [
        f"  [{e.get('timestamp','')[:19]}] {e.get('title','')} — {e.get('detail','')[:80]}"
        for e in timeline[:10]
    ]

    return f"""
INCIDENT CONTEXT:
Summary: {rca_result.get('incident_summary', '')}

ROOT CAUSE (confidence {primary.get('confidence', 0):.0%}):
{primary.get('root_cause', '')}

EVIDENCE:
{chr(10).join('• ' + e for e in primary.get('evidence', []))}

RECOMMENDED ACTION: {primary.get('recommended_action', '')} on {primary.get('action_target', '')}

IMMEDIATE STEPS:
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(rca_result.get('immediate_steps', [])))}

TIMELINE SAMPLE:
{chr(10).join(tl_lines)}

IMPACT: {rca_result.get('impact_assessment', '')}
"""


def get_mock_chat_response(question: str, context: str) -> str:
    """Rule-based mock responses for demo without API key."""
    q = question.lower()

    if any(w in q for w in ["why", "cause", "happen", "root"]):
        return (
            "Based on the analysis, the root cause was a **connection leak in order-service v2.3.2**. "
            "The deployment at 14:00:30 introduced bulk order processing code that opened database connections "
            "without properly returning them to the pool. Within 3 minutes, all 500 DB connections were exhausted, "
            "causing timeouts that cascaded through payment-service and api-gateway. "
            "The 91% confidence comes from the tight temporal correlation between the deploy and the DB connection spike."
        )
    elif any(w in q for w in ["fix", "resolve", "action", "do", "recommend"]):
        return (
            "The recommended action is to **rollback order-service to v2.3.1** immediately. Here's the plan:\n\n"
            "1. Trigger rollback via CI/CD (`kubectl rollout undo deployment/order-service`)\n"
            "2. Restart db-primary to clear stale connections (~2 min downtime)\n"
            "3. Verify DB connections drop below 100 within 5 minutes\n"
            "4. Confirm error rate on api-gateway returns below 2%\n\n"
            "Total estimated recovery time: **~5 minutes** with low risk."
        )
    elif any(w in q for w in ["prevent", "future", "avoid", "next time"]):
        return (
            "To prevent this in the future:\n\n"
            "• **Connection pool limits** — cap each service at max 50 DB connections\n"
            "• **Canary deployments** — roll out order-service changes to 5% traffic first\n"
            "• **Earlier alerting** — alert at 60% connection utilization (not 70%)\n"
            "• **Integration tests** — test connection count under bulk order load in CI\n"
            "• **Bulkhead pattern** — isolate DB connection pools per service to limit blast radius"
        )
    elif any(w in q for w in ["timeline", "when", "sequence", "cascade"]):
        return (
            "The failure sequence was:\n\n"
            "• **14:00:30** — order-service v2.3.2 deployed (connection leak introduced)\n"
            "• **14:01:03** — First DB latency warnings (850ms queries)\n"
            "• **14:02:10** — First DB timeout errors on order-service\n"
            "• **14:02:50** — DB max connections reached (500/500)\n"
            "• **14:03:00** — Circuit breaker opened on order-service\n"
            "• **14:03:15** — api-gateway hit 94% error rate (full outage)\n"
            "• **14:05:00** — DB restarted by ops team\n"
            "• **14:07:00** — System recovered\n\n"
            "Total incident duration: **~5 minutes** of full outage."
        )
    elif any(w in q for w in ["impact", "affected", "service", "who"]):
        return (
            "The incident affected **4 services** in a cascade:\n\n"
            "1. **db-primary** — Max connections exhausted (500/500), deadlocks on inventory table\n"
            "2. **order-service** — 98% error rate, circuit breaker opened\n"
            "3. **payment-service** — 85% error rate, order validation failed\n"
            "4. **api-gateway** — 94% error rate, returning 503s to all checkout customers\n\n"
            "All checkout attempts failed during the 5-minute outage window."
        )
    elif any(w in q for w in ["confidence", "sure", "certain", "probability"]):
        return (
            "The primary hypothesis (connection leak in v2.3.2) has **91% confidence**. "
            "The key factors driving high confidence:\n"
            "• Deployment happened exactly 90 seconds before the first DB errors\n"
            "• DB connections ramped linearly from 62 → 500 (classic leak pattern)\n"
            "• The deploy note mentioned 'removed N+1 query' — risky DB query changes\n"
            "• Deadlocks appeared on the same table the bulk order code writes to\n\n"
            "Alternative hypothesis (config change masking issue) scores 61% confidence — "
            "it's a contributing factor, not root cause."
        )
    else:
        return (
            f"Great question. Based on the incident analysis:\n\n"
            f"The incident was caused by a connection leak in order-service v2.3.2 deployed at 14:00:30. "
            f"The recommended fix is to rollback to v2.3.1. "
            f"Is there a specific aspect you'd like me to dig deeper into — "
            f"root cause evidence, the failure cascade, prevention steps, or the action plan?"
        )


def call_llm_chat(
    messages: List[Dict],
    context: str,
    llm_provider: str = "mock",
    api_key: Optional[str] = None,
) -> str:
    """Call LLM with conversation history."""
    full_system = SYSTEM_PROMPT + "\n\n" + context
    last_question = messages[-1]["content"] if messages else ""

    if llm_provider == "claude" and api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                system=full_system,
                messages=messages,
            )
            return resp.content[0].text
        except Exception as e:
            return get_mock_chat_response(last_question, context)

    elif llm_provider == "openai" and api_key:
        try:
            import openai as oa
            client = oa.OpenAI(api_key=api_key)
            oai_msgs = [{"role": "system", "content": full_system}] + messages
            resp = client.chat.completions.create(
                model="gpt-4o", messages=oai_msgs, max_tokens=800, temperature=0.3
            )
            return resp.choices[0].message.content
        except Exception as e:
            return get_mock_chat_response(last_question, context)

    else:
        return get_mock_chat_response(last_question, context)
