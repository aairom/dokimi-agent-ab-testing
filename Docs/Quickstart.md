# Quickstart Guide: Dokimi Agent Context A/B Testing Platform

This guide will walk you through setting up and running the Dokimi Agent Context A/B Testing platform locally in under 2 minutes.

---

## 1. Prerequisites
- **Python**: 3.11, 3.12, 3.13, or 3.14
- **Package Manager**: `uv` (recommended) or `pip`
- **Optional**: Podman or Docker for containerized deployment

---

## 2. Environment Setup

### Using `uv` (Fastest):
```bash
# Create virtual environment
uv venv .venv --python 3.12

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### Configuration:
Copy the example environment file:
```bash
cp .env.example .env
```
*Note: The platform is configured to run out-of-the-box using the built-in Domain Mock Engine without requiring external API keys. To use live LLM models, fill in `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`.*

---

## 3. Running the Application

### Option A: Using the Automation Scripts (Recommended)
Launch the server in detached mode:
```bash
./scripts/start.sh
```
This displays the active PID and Web URL:
```
=====================================================================
✅ Dokimi Agent A/B Testing Platform is LIVE and HEALTHY!
📌 Process PID:         12345
🌐 Web Dashboard URL:   http://127.0.0.1:8000
📚 API Swagger Docs:    http://127.0.0.1:8000/docs
📖 API Redoc:           http://127.0.0.1:8000/redoc
❤️ Health Check:        http://127.0.0.1:8000/health
🎯 Use-Cases Endpoint:  http://127.0.0.1:8000/api/use-cases
🧬 Variants Endpoint:   http://127.0.0.1:8000/api/variants
📋 Questions Endpoint:  http://127.0.0.1:8000/api/questions
📊 Experiments API:     http://127.0.0.1:8000/api/experiments
📄 Application Logs:    output/app.log
=====================================================================
```

To stop the background server:
```bash
./scripts/stop.sh
```

### Option B: Direct CLI Execution
```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. Using the Platform

Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Key Features to Explore:
1. **A/B Experiment Dashboard**:
   - Select any registered use-case (e.g. *SRE Incident Response*, *Cloud Security Audit*, or your submitted *Ad-Hoc Use-Cases*).
   - Click **"Run Full Dokimi A/B Eval"** to execute a paired evaluation of context arms with real-time SSE progress streaming.
   - Inspect the **Performance Comparison Bar Chart** and **Multi-Dimensional Context Radar**.
   - Review statistical significance, $p$-values (paired $t$-test), Holm-Bonferroni corrections, and novel knowledge atom metrics.
2. **Use-Case Library (Hardcoded & Dynamic Ad-Hoc)**:
   - View immutable built-in demonstration fixtures (`SRE Incident Response`, `Cloud Security Compliance Audit`).
   - Click **"+ Submit Ad-Hoc Use-Case"** to register custom evaluation domains, thresholds, and scenario questions on the fly.
   - For complete technical documentation and API reference, see [`Docs/AdHoc_UseCases.md`](AdHoc_UseCases.md).
3. **Dual Agent Chat Playground**:
   - Compare two variants side-by-side (e.g. `baseline` vs `arm_skill`).
   - Select quick incident scenarios (e.g. *Exit Code 137 OOMKilled* or *Postgres Connection Storm*) to observe direct differences in response quality.
4. **Context Arms & Variants**:
   - View, create, and configure new treatment arms with custom system prompts or injected documentation.
5. **Evaluation Questions**:
   - Manage standardized ground truth questions and topic assertions dynamically filtered by active use-case.

---

## 5. Running Tests
To verify all unit tests:
```bash
.venv/bin/pytest tests/ -v
```

---

## 6. Container Deployment (Podman / Docker)

Build and run using Podman or Docker:
```bash
# Build container image
podman build -t dokimi-agent-ab-testing -f Containerfile .

# Run container
podman run -d -p 8000:8000 --name dokimi-app dokimi-agent-ab-testing
```
Access the application at `http://localhost:8000`.

To clean container images:
```bash
./scripts/clean_containers.sh
```
