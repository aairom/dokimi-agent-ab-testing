# API Reference: Dokimi Agent Context A/B Testing Platform

This document provides a comprehensive REST API reference for the **Dokimi Agent Context A/B Testing Platform**, including request and response schemas, validation rules, error codes, and practical examples.

Interactive API documentation is also available locally at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Table of Contents
1. [Base Information & Health](#1-base-information--health)
2. [Use-Cases API (Fixtures & Ad-Hoc)](#2-use-cases-api-fixtures--ad-hoc)
3. [Context Variants / Arms API](#3-context-variants--arms-api)
4. [Evaluation Questions API](#4-evaluation-questions-api)
5. [Experiments & Evaluation Runner API](#5-experiments--evaluation-runner-api)
6. [Dual Agent Chat Playground API](#6-dual-agent-chat-playground-api)
7. [Progress Tracking & Tasks API](#7-progress-tracking--tasks-api)
8. [Model Discovery API](#8-model-discovery-api)
9. [Standard Status Codes & Error Handling](#9-standard-status-codes--error-handling)

---

## 1. Base Information & Health

### `GET /health`
Returns system health status and application metadata.

#### Response (`200 OK`)
```json
{
  "status": "healthy",
  "app": "Dokimi Agent Context A/B Testing Platform",
  "dokimi_engine": "online",
  "version": "1.0.0"
}
```

---

## 2. Use-Cases API (Fixtures & Ad-Hoc)

### `GET /api/use-cases`
List all registered use-cases, combining built-in immutable fixtures and dynamic ad-hoc submissions.

#### Response (`200 OK`)
```json
[
  {
    "id": "sre_incident_response",
    "name": "SRE Incident Response Optimization",
    "description": "Evaluate context arms on Kubernetes CrashLoopBackOff, OOMKilled, and connection storm triage.",
    "source": "hardcoded",
    "is_mutable": false,
    "parameters": {
      "domain": "Site Reliability Engineering",
      "alpha": 0.05,
      "min_score_threshold": 0.70
    },
    "expected_outputs": [
      "Identify root cause accurately",
      "Provide actionable kubectl / remediation commands"
    ],
    "scenarios": [
      {
        "id": "sre_sc_1",
        "prompt": "Pod in namespace 'production' restarting with Exit Code 137. How to triage?",
        "expected_topics": ["Exit Code 137", "OOMKilled", "kubectl describe pod", "memory limits"],
        "category": "Kubernetes"
      }
    ],
    "custom_variants": null,
    "created_at": "2026-10-27T10:00:00Z",
    "updated_at": "2026-10-27T10:00:00Z"
  }
]
```

---

### `GET /api/use-cases/{usecase_id}`
Retrieve a specific use-case by its unique identifier.

#### Parameters
- `usecase_id` (path, string, required): ID of the target use-case.

#### Response (`200 OK`)
Returns the complete `UseCase` object.

#### Error Responses
- `404 Not Found`: If `usecase_id` is not registered.

---

### `POST /api/use-cases/submit`
Submit and register a dynamic ad-hoc use-case at runtime without restarting the application.

#### Constraints & Validation
- Guarded by `ALLOW_ADHOC_USECASES` configuration in [`.env`](.env) (returns `403 Forbidden` if disabled).
- `name`: String, minimum 2 characters (`min_length=2`).
- `scenarios`: Array of `UseCaseScenario`, minimum 1 scenario (`min_length=1`).
- `parameters`: Key-value JSON dictionary.
- `expected_outputs`: List of string criteria.

#### Request Body
```json
{
  "name": "Database Failover & Split-Brain Mitigation",
  "description": "Evaluate context arms on Raft consensus recovery and replication lag handling",
  "parameters": {
    "domain": "Database Infrastructure",
    "quorum_type": "Raft",
    "alpha": 0.05
  },
  "expected_outputs": [
    "Prevent split-brain writes",
    "Preserve ACID guarantees"
  ],
  "scenarios": [
    {
      "id": "db_sc_01",
      "prompt": "Leader node in us-east-1a is partitioned from survivors. How do we prevent split-brain writes?",
      "expected_topics": [
        "Verify Raft consensus quorum across surviving AZs",
        "Force step-down or fence partitioned leader node"
      ],
      "category": "High Availability"
    }
  ],
  "custom_variants": null
}
```

#### Response (`200 OK`)
Returns the generated `UseCase` object containing the assigned `id` (e.g. `adhoc_20261027_120000_a1b2`), `source: "adhoc"`, and `is_mutable: true`.

#### Error Responses
- `403 Forbidden`: Ad-hoc use-case submissions disabled by config.
- `422 Unprocessable Entity`: Validation failure on missing or malformed fields.

---

### `DELETE /api/use-cases/{usecase_id}`
Delete a dynamic ad-hoc use-case and remove it from [`data/adhoc_usecases.json`](data/adhoc_usecases.json).

#### Parameters
- `usecase_id` (path, string, required): ID of the ad-hoc use-case to delete.

#### Response (`200 OK`)
```json
{
  "status": "deleted",
  "use_case_id": "adhoc_20261027_120000_a1b2"
}
```

#### Error Responses
- `400 Bad Request`: Attempting to delete an immutable fixture (`sre_incident_response` or `cloud_security_audit`).
- `404 Not Found`: Target ad-hoc use-case ID does not exist.

---

## 3. Context Variants / Arms API

### `GET /api/variants`
Retrieve all configured context arms (e.g. `baseline`, `arm_docs`, `arm_profile`, `arm_skill`, `arm_mcp`).

#### Response (`200 OK`)
```json
[
  {
    "id": "baseline",
    "name": "Standard Unprompted Baseline",
    "arm_type": "baseline",
    "arm_spec": "baseline",
    "description": "Standard base LLM with no additional context injection.",
    "system_prompt": "You are a helpful software engineering assistant.",
    "context_content": null,
    "parameters": {}
  },
  {
    "id": "arm_skill",
    "name": "SRE Incident Runbook Skill",
    "arm_type": "skill",
    "arm_spec": "skill:data/skills/sre_runbook/SKILL.md",
    "description": "Precision incident remediation skill protocol.",
    "system_prompt": "You are a Tier-3 Site Reliability Engineer expert.",
    "context_content": "# SRE Incident Runbook Skill Protocol...",
    "parameters": {}
  }
]
```

---

### `POST /api/variants`
Create or update a custom context arm.

#### Request Body
```json
{
  "id": "arm_custom_guardrail",
  "name": "Compliance Guardrail Persona",
  "arm_type": "profile",
  "arm_spec": "profile:compliance_guardrail.md",
  "description": "Enforces strict least-privilege verification before actions.",
  "system_prompt": "You are a Security Compliance Guardrail Agent.",
  "context_content": "Always verify RBAC permissions and session tokens before command execution.",
  "parameters": {}
}
```

#### Response (`200 OK`)
Returns the saved `VariantConfig`.

---

### `DELETE /api/variants/{variant_id}`
Delete a custom context arm.

#### Error Responses
- `400 Bad Request`: Attempting to delete `baseline` (baseline is required for paired deltas).
- `404 Not Found`: Variant ID not found.

---

## 4. Evaluation Questions API

### `GET /api/questions`
Retrieve golden evaluation questions. Supports filtering by use-case.

#### Query Parameters
- `use_case_id` (query, string, optional): Target use-case identifier. If provided, returns scenario questions for that use-case.

#### Response (`200 OK`)
```json
[
  {
    "id": "q1",
    "question": "A production microservice pod in namespace 'production' is restarting continuously with Exit Code 137. How to triage?",
    "expected_topics": [
      "Identify Exit Code 137 as OOMKilled",
      "Check pod describe and dmesg memory cgroup events",
      "Adjust requests and limits in deployment spec"
    ],
    "context_hints": null,
    "category": "Kubernetes Memory",
    "use_case_id": "sre_incident_response"
  }
]
```

---

## 5. Experiments & Evaluation Runner API

### `POST /api/experiments/run`
Execute a complete Dokimi paired A/B evaluation across active context arms.

#### Query Parameters
- `task_id` (query, string, optional): Tracked task ID for real-time SSE progress streaming.

#### Request Body
```json
{
  "name": "Database Failover Context Optimization",
  "use_case_id": "adhoc_20261027_120000_a1b2",
  "model": "mock-model",
  "provider": "mock",
  "arm_ids": ["baseline", "arm_docs", "arm_profile", "arm_skill"]
}
```

#### Response (`200 OK`)
```json
{
  "id": "exp_20261027_120500_c3d4",
  "name": "Database Failover Context Optimization",
  "use_case_id": "adhoc_20261027_120000_a1b2",
  "timestamp": "2026-10-27T12:05:00Z",
  "model_used": "mock-model",
  "provider": "mock",
  "baseline_arm": "baseline",
  "arms": ["baseline", "arm_docs", "arm_profile", "arm_skill"],
  "total_evaluations": 16,
  "metrics_by_arm": {
    "baseline": {
      "mean_score": 0.525,
      "p_value": null,
      "stat_significant": false,
      "accuracy_score": 0.55,
      "completeness_score": 0.50,
      "conciseness_score": 0.80,
      "latency_ms": 110.0,
      "token_usage": 420,
      "novel_atoms_added": 0,
      "redundant_atoms": 0
    },
    "arm_skill": {
      "mean_score": 0.885,
      "p_value": 0.0021,
      "stat_significant": true,
      "accuracy_score": 0.92,
      "completeness_score": 0.88,
      "conciseness_score": 0.85,
      "latency_ms": 135.0,
      "token_usage": 680,
      "novel_atoms_added": 12,
      "redundant_atoms": 3
    }
  },
  "summary_verdict": "Arm 'arm_skill' achieved highest statistically significant improvement (+68.6% vs baseline, p=0.0021, Holm-corrected).",
  "detailed_results": []
}
```

---

### `GET /api/experiments`
List all historical experiment runs.

### `GET /api/experiments/{experiment_id}`
Retrieve complete experiment scorecard by ID.

### `GET /api/experiments/{experiment_id}/report`
Retrieve a formatted Markdown executive report for the experiment.

---

## 6. Dual Agent Chat Playground API

### `POST /api/chat`
Execute a live query against a specific context arm variant.

#### Request Body
```json
{
  "variant_id": "arm_skill",
  "message": "Pod restarting with Exit Code 137. What are the immediate triage steps?",
  "provider": "mock",
  "model": "mock-model"
}
```

#### Response (`200 OK`)
```json
{
  "variant_id": "arm_skill",
  "prompt": "Pod restarting with Exit Code 137. What are the immediate triage steps?",
  "answer": "### Immediate SRE Incident Response: Pod Exit Code 137 (OOMKilled)\n\n1. **Verify Pod Status & Termination Reason**:\n   ```bash\n   kubectl describe pod <pod-name> -n <namespace>\n   ```\n...",
  "latency_ms": 142.5,
  "token_count": 284,
  "model": "mock-model"
}
```

---

## 7. Progress Tracking & Tasks API

### `POST /api/tasks`
Register a long-running evaluation task.

#### Request Body
```json
{
  "task_type": "experiment",
  "total_steps": 16,
  "initial_step": "Initializing Dokimi evaluation..."
}
```

#### Response (`200 OK`)
```json
{
  "task_id": "task_20261027_120400_e5f6",
  "task_type": "experiment",
  "status": "running",
  "current_step": "Initializing Dokimi evaluation...",
  "completed_steps": 0,
  "total_steps": 16,
  "percent": 0.0,
  "elapsed_seconds": 0.0,
  "estimated_remaining_seconds": null,
  "created_at": "2026-10-27T12:04:00Z",
  "updated_at": "2026-10-27T12:04:00Z"
}
```

### `GET /api/tasks/{task_id}/events`
Server-Sent Events (SSE) live progress stream (`text/event-stream`).

### `POST /api/tasks/{task_id}/cancel`
Cancel an active running evaluation task.

---

## 8. Model Discovery API

### `GET /api/models/local?provider={provider}`
Query live local inference engines (Ollama or llama.cpp) for installed models and metadata.

#### Parameters
- `provider` (query, string, required): `local-ollama` or `local-llamacpp`.

#### Response (`200 OK`)
```json
{
  "provider": "local-ollama",
  "is_connected": true,
  "status_message": "Successfully retrieved 3 models from local Ollama",
  "models": [
    {
      "id": "llama3.2:latest",
      "name": "llama3.2",
      "size_bytes": 2019393184,
      "size_human": "2.0 GB",
      "quantization_format": "Q4_K_M",
      "parameter_count": "3B",
      "modified_at": "2026-10-25T14:30:00Z"
    }
  ]
}
```

---

## 9. Standard Status Codes & Error Handling

All error responses adhere to standard HTTP status codes and return a JSON payload with a `detail` field:

```json
{
  "detail": "Error description explaining the root cause."
}
```

| HTTP Status Code | Scenario |
|---|---|
| `200 OK` | Request succeeded normally. |
| `400 Bad Request` | Invalid deletion attempt (e.g. deleting immutable baseline or hardcoded fixture) or bad parameters. |
| `403 Forbidden` | Action blocked by feature flag (e.g. `ALLOW_ADHOC_USECASES=false`). |
| `404 Not Found` | Requested use-case, variant, or experiment ID does not exist. |
| `422 Unprocessable Entity` | Pydantic validation error (e.g. missing required field or `min_length` violation). |
| `500 Internal Server Error` | Unhandled backend exception during evaluation or inference dispatch. |
