# 🔬 AI Incident Root Cause Analyzer

> Hackathon Project · Agentic AI for Production Incident Analysis

An end-to-end AI system that ingests simulated logs, metrics, and deployment events to automatically detect anomalies, reason about root causes, and recommend + simulate remediation actions.

---

## Architecture

```
ai-incident-analyzer/
├── data/
│   ├── logs.json          # Simulated error logs (24 entries)
│   ├── metrics.csv        # CPU, latency, memory, DB metrics (42 rows)
│   └── events.json        # Deployments, alerts, incidents (10 events)
│
├── modules/
│   ├── anomaly_detector.py    # Z-score + threshold anomaly detection
│   ├── log_parser.py          # Pattern matching & cascade extraction
│   └── timeline_builder.py    # Unified chronological event timeline
│
├── agent/
│   ├── rca_agent.py           # LLM-powered root cause analysis
│   ├── decision_module.py     # Action plan builder
│   ├── action_simulator.py    # Recovery simulation
│   └── chat_agent.py          # Conversational Q&A
│
├── ui/
│   └── app.py                 # Streamlit frontend
│
├── main.py                    # FastAPI backend
├── requirements.txt
└── README.md
```

---

##  Quick Start

### 1. Install dependencies

```bash
cd ai-incident-analyzer
pip install -r requirements.txt
```

### 2. Start the FastAPI backend

```bash
# From the project root
python main.py
# OR
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at: http://localhost:8000  
API docs at: http://localhost:8000/docs

### 3. Start the Streamlit frontend

```bash
# In a new terminal, from the project root
streamlit run ui/app.py
```

Frontend runs at: http://localhost:8501

---

##  LLM Configuration

The app works in **3 modes**:

| Mode | Description | Requirement |
|------|-------------|-------------|
| `mock` | Deterministic responses — **works without API keys** | None |
| `claude` | Uses Claude claude-sonnet-4-20250514 via Anthropic API | `ANTHROPIC_API_KEY` |
| `openai` | Uses GPT-4o via OpenAI API | `OPENAI_API_KEY` |

To use a real LLM:
1. Select it in the sidebar dropdown
2. Paste your API key in the text field
3. Click "Run AI Root Cause Analysis"

---

##  Demo Walkthrough

1. **Dashboard** — See incident overview (24 logs, 42 metric rows, 10 events)
2. **Metrics & Anomalies** — Interactive charts showing the incident spike at 14:01-14:03
3. **Logs** — Filterable log explorer with level/service filters
4. **Timeline** — Chronological incident timeline with phase markers
5. ** AI Analysis** — Root cause, confidence score, evidence, multiple hypotheses
6. ** Action & Recovery** — Action plan + "Approve Action" button + recovery charts
7. ** Chat** — Ask follow-up questions ("Why did this happen?", "What's the fix?")

---

## 📊 Simulated Incident Summary

The demo dataset simulates a **real-world production incident**:

```
14:00:30  order-service v2.3.2 deployed (connection leak bug introduced)
14:01:03  DB query latency starts rising (850ms)
14:02:10  Database timeout errors begin
14:02:50  DB max connections reached (500/500)  
14:03:00  Circuit breaker opens on order-service
14:03:15  api-gateway hits 94% error rate → full outage
14:05:00  Ops team restarts DB
14:07:00  System recovers
```

**Root Cause:** Connection leak in bulk order processing code in v2.3.2  
**Confidence:** 91%  
**Recommended Action:** Rollback order-service to v2.3.1

---

## 🔧 Key Technical Decisions

- **No ML model training** — anomaly detection uses z-scores + thresholds (fast, interpretable)
- **LLM for reasoning** — structured prompt with all context → JSON-structured RCA
- **Mock LLM** — deterministic responses for offline demos without API keys
- **Modular design** — each module can be tested/replaced independently
- **FastAPI** — async, auto-docs, easy to extend
- **Streamlit** — rapid UI prototyping

---

## 🧪 Running Tests

```bash
# Test individual modules
python -m modules.anomaly_detector
python -m modules.log_parser
python -m modules.timeline_builder

# Test the full pipeline
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"llm_provider": "mock"}'
```

