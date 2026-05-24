"""
main.py — FastAPI Backend for AI Incident Root Cause Analyzer
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path setup so modules resolve correctly ──────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from modules.anomaly_detector import load_metrics, detect_anomalies, get_anomaly_summary, anomalies_to_dict
from modules.log_parser       import load_logs, parse_logs, parsed_logs_to_dict
from modules.timeline_builder import load_events, build_timeline, timeline_to_dict, get_incident_phases
from agent.rca_agent          import run_rca_agent, rca_result_to_dict
from agent.decision_module    import build_action_plan, action_plan_to_dict
from agent.action_simulator   import run_simulation, simulation_to_dict
from agent.chat_agent         import build_chat_context, call_llm_chat

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Incident Root Cause Analyzer",
    description="Agentic AI system for incident analysis, RCA, and auto-remediation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = ROOT / "data"

# ── In-memory state (session cache for demo) ─────────────────────────────────
_state: Dict[str, Any] = {}


# ── Request/Response Models ──────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    llm_provider: str = "mock"   # mock | claude | openai
    api_key: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    llm_provider: str = "mock"
    api_key: Optional[str] = None


class SimulateRequest(BaseModel):
    action_type: str
    target_service: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_all_data():
    logs      = load_logs(str(DATA_DIR / "logs.json"))
    metrics   = load_metrics(str(DATA_DIR / "metrics.csv"))
    events    = load_events(str(DATA_DIR / "events.json"))
    anomalies = detect_anomalies(metrics)
    a_summary = get_anomaly_summary(anomalies)
    a_dicts   = anomalies_to_dict(anomalies)
    parsed    = parse_logs(logs)
    log_dict  = parsed_logs_to_dict(parsed)
    timeline  = build_timeline(logs, a_dicts, events)
    tl_dicts  = timeline_to_dict(timeline)
    phases    = get_incident_phases(timeline)
    return {
        "logs": logs,
        "metrics": metrics,
        "events": events,
        "anomalies": a_dicts,
        "anomaly_summary": a_summary,
        "log_summary": log_dict,
        "timeline": tl_dicts,
        "phases": phases,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "AI Incident Root Cause Analyzer API"}


@app.get("/data/overview")
def get_data_overview():
    """Load raw data and return summaries for the dashboard."""
    try:
        data = _load_all_data()
        _state["data"] = data  # cache
        return {
            "log_summary":      data["log_summary"],
            "anomaly_summary":  data["anomaly_summary"],
            "anomalies":        data["anomalies"],
            "timeline":         data["timeline"],
            "phases":           data["phases"],
            "events_count":     len(data["events"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/logs")
def get_logs():
    try:
        return {"logs": load_logs(str(DATA_DIR / "logs.json"))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/metrics")
def get_metrics():
    try:
        df = load_metrics(str(DATA_DIR / "metrics.csv"))
        return {"metrics": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/events")
def get_events():
    try:
        return {"events": load_events(str(DATA_DIR / "events.json"))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze")
def run_analysis(req: AnalyzeRequest):
    """
    Run the full AI RCA pipeline:
    1. Load & parse data
    2. Detect anomalies
    3. Build timeline
    4. Run AI agent
    5. Build action plan
    """
    try:
        data = _load_all_data()
        _state["data"] = data

        # Build agent context
        context = {
            "anomaly_summary":   data["anomaly_summary"],
            "log_summary":       data["log_summary"],
            "timeline_snippet":  data["timeline"],
            "events_summary":    data["events"],
        }

        # Run RCA agent
        rca_result = run_rca_agent(
            context,
            llm_provider=req.llm_provider,
            api_key=req.api_key,
        )
        rca_dict = rca_result_to_dict(rca_result)
        _state["rca"] = rca_dict

        # Build action plan from primary hypothesis
        primary = rca_result.primary_hypothesis
        plan    = build_action_plan(
            recommended_action=primary.recommended_action,
            target_service=primary.action_target,
            confidence=primary.confidence,
            incident_severity="critical",
        )
        plan_dict = action_plan_to_dict(plan)
        _state["action_plan"] = plan_dict

        return {
            "rca":         rca_dict,
            "action_plan": plan_dict,
            "timeline":    data["timeline"],
            "phases":      data["phases"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/simulate")
def simulate_action(req: SimulateRequest):
    """Simulate the effect of applying the recommended action."""
    try:
        sim      = run_simulation(req.action_type, req.target_service)
        sim_dict = simulation_to_dict(sim)
        _state["simulation"] = sim_dict
        return sim_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def chat(req: ChatRequest):
    """Conversational Q&A about the incident."""
    try:
        rca  = _state.get("rca", {})
        tl   = _state.get("data", {}).get("timeline", [])
        ctx  = build_chat_context(rca, tl)

        messages = req.history + [{"role": "user", "content": req.message}]
        response = call_llm_chat(
            messages=messages,
            context=ctx,
            llm_provider=req.llm_provider,
            api_key=req.api_key,
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "healthy", "cached_analysis": "rca" in _state}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
