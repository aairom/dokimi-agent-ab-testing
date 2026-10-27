# Getting Started: Dokimi Agent Context A/B Testing Platform

Welcome to the **Dokimi Agent Context A/B Testing Platform**! This guide will help you understand the platform's core concepts, launch the application locally, submit your first ad-hoc use-case, and interpret statistical A/B evaluation results.

---

## Table of Contents
1. [Core Concepts](#1-core-concepts)
2. [Quick Installation & Launch](#2-quick-installation--launch)
3. [Tour of the Dashboard](#3-tour-of-the-dashboard)
4. [Submitting Your First Ad-Hoc Use-Case](#4-submitting-your-first-ad-hoc-use-case)
5. [Running an A/B Evaluation Experiment](#5-running-an-ab-evaluation-experiment)
6. [Interactive Dual Agent Chat Playground](#6-interactive-dual-agent-chat-playground)
7. [Next Steps & Resources](#7-next-steps--resources)

---

## 1. Core Concepts

When building AI coding and operations agents, developers often inject large prompt templates, extensive markdown documentation, or complex tool suites. However, without systematic testing, it is impossible to know whether that extra context actually improves performance or merely adds latency and cost.

The platform implements Intel's [Dokimi](https://github.com/intel/dokimi) evaluation principles:
- **Treatment Arms**: Different context configurations tested in parallel:
  - `baseline`: Unprompted model baseline.
  - `arm_docs`: Static procedural documentation injection.
  - `arm_profile`: Domain persona and behavioral guidelines.
  - `arm_skill`: Precision action protocols and step-by-step remediation commands.
  - `arm_mcp`: Model Context Protocol server capabilities.
- **Paired On/Off Arm Testing**: Every arm is tested against the exact same scenario queries under identical conditions.
- **Statistical Significance**: Computes paired Student's $t$-test $p$-values with Holm-Bonferroni multi-arm corrections ($\alpha=0.05$).
- **Knowledge Atom Decomposition**: Distinguishes novel actionable facts from redundant base knowledge.

---

## 2. Quick Installation & Launch

### Step 1: Create Virtual Environment & Install Dependencies
```bash
# Clone and enter the repository
cd dokimi-agent-ab-testing

# Create virtual environment with uv (or python3 -m venv)
uv venv .venv --python 3.12
source .venv/bin/activate

# Install requirements
uv pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
cp .env.example .env
```
*Note: The platform is pre-configured with a built-in Domain Mock Engine so you can run evaluations immediately without external API keys.*

### Step 3: Launch in Detached Mode
```bash
./scripts/start.sh
```

Console output displays all available URLs:
```text
=====================================================================
✅ Dokimi Agent A/B Testing Platform is LIVE and HEALTHY!
📌 Process PID:         63870
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

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser.

---

## 3. Tour of the Dashboard

The platform navigation tabs provide full control over the evaluation lifecycle:
1. **📊 A/B Experiment Dashboard**: Run paired evaluations, view top performing arms, delta improvements, statistical significance badges, and interactive ECharts (Bar & Radar).
2. **🎯 Use-Case Library**: Browse immutable built-in fixtures (`SRE Incident Response`, `Cloud Security Audit`) and submit dynamic ad-hoc use-cases.
3. **💬 Dual Agent Chat Playground**: Query two context arms side-by-side in real-time.
4. **🧬 Context Arms & Variants**: Inspect and configure custom system prompts, documentation payloads, and skill protocols.
5. **📋 Evaluation Question Set**: Inspect golden evaluation questions and ground truth assertion keywords.

---

## 4. Submitting Your First Ad-Hoc Use-Case

You can submit a custom domain use-case directly from the Web UI or via the REST API.

### Method A: Using the Web UI
1. Navigate to the **"🎯 Use-Case Library"** tab.
2. Click the blue **"+ Submit Ad-Hoc Use-Case"** button.
3. Fill in the modal form:
   - **Use-Case Title**: `Database Split-Brain Failover Drill`
   - **Description**: `Evaluate context arms on Raft consensus quorum recovery during AZ network partition.`
   - **Parameters / Thresholds (JSON)**: `{"domain": "Database", "alpha": 0.05, "min_score_threshold": 0.70}`
   - **Expected Outputs**: 
     ```
     Verify Raft consensus quorum
     Prevent split-brain writes
     ```
   - **Evaluation Scenarios**:
     - Click **"+ Add Scenario"** and enter:
       - **Prompt**: `Leader node in us-east-1a is partitioned from survivors. How do we prevent split-brain writes?`
       - **Category**: `High Availability`
       - **Expected Keywords**: `Raft quorum, step-down, fence, isolate`
4. Click **"Register Use-Case"**.
5. Your use-case is now registered, saved in `data/adhoc_usecases.json`, and displayed with an `AD-HOC` badge.

### Method B: Using cURL
```bash
curl -X POST http://127.0.0.1:8000/api/use-cases/submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Database Split-Brain Failover Drill",
    "description": "Evaluate context arms on Raft consensus quorum recovery during AZ network partition.",
    "parameters": {"domain": "Database", "alpha": 0.05},
    "expected_outputs": ["Verify Raft quorum", "Prevent split-brain writes"],
    "scenarios": [
      {
        "id": "db_sc_1",
        "prompt": "Leader node in us-east-1a is partitioned from survivors. How do we prevent split-brain writes?",
        "expected_topics": ["Raft quorum", "step-down", "fence", "isolate"],
        "category": "High Availability"
      }
    ]
  }'
```

---

## 5. Running an A/B Evaluation Experiment

1. Return to the **"📊 A/B Experiment Dashboard"** tab.
2. In the use-case dropdown on the top-right toolbar, select your newly created use-case (`⚡ [Ad-Hoc] Database Split-Brain Failover Drill`).
3. Click **"▶ Run Full Dokimi A/B Eval"**.
4. Watch the real-time progress bar stream live evaluation steps via Server-Sent Events (SSE).
5. Once complete, inspect:
   - **Top KPI Cards**: Top Performing Arm, Score Delta (% vs Baseline), Statistical Significance ($p$-value), and Novel Atoms Added.
   - **Dokimi Executive Verdict**: Summary of whether the context intervention proved statistically effective.
   - **Comparison Table**: Granular breakdown of Accuracy, Completeness, Conciseness, and Latency per arm.

---

## 6. Interactive Dual Agent Chat Playground

To see how individual context arms respond in practice:
1. Navigate to the **"💬 Dual Agent Chat Playground"** tab.
2. Select **Agent Variant A** (e.g. `baseline`) and **Agent Variant B** (e.g. `arm_skill`).
3. Select a scenario from the preset dropdown or type a custom question.
4. Click **"🚀 Send to Both Arms"**.
5. Observe side-by-side differences in reasoning, command accuracy, latency (ms), and token count.

---

## 7. Next Steps & Resources

- 📖 **[Ad-Hoc Use-Cases Technical Guide](AdHoc_UseCases.md)**: Deep dive into schema details, validation rules, persistence mechanics, and troubleshooting.
- 💻 **[Code Examples & Integration Samples](Examples.md)**: Executable Python, JavaScript, and Bash scripts.
- 📐 **[System Architecture](Architecture.md)**: Architectural diagrams and component breakdown.
- 🌐 **[REST API Reference](API.md)**: Full endpoint specification.
- 🛑 **Graceful Shutdown**: When finished, stop background processes using `./scripts/stop.sh`.
