# Executable Code Examples: Dokimi Agent Context A/B Testing

This document contains fully tested, executable code samples in **Python**, **JavaScript / Node.js**, **cURL / Bash**, and **Shell scripting** demonstrating how to interact programmatically with the **Dokimi Agent Context A/B Testing Platform**.

All samples assume the local application is running at `http://127.0.0.1:8000` (started via `./scripts/start.sh`).

---

## Table of Contents
1. [Python: End-to-End Ad-Hoc Use-Case Submission & Evaluation](#1-python-end-to-end-ad-hoc-use-case-submission--evaluation)
2. [Python: Async Client with httpx](#2-python-async-client-with-httpx)
3. [JavaScript / Node.js: Fetch & Axios Integration](#3-javascript--nodejs-fetch--axios-integration)
4. [cURL & jq: Command-Line Workflow](#4-curl--jq-command-line-workflow)
5. [Bash Script: Batch Use-Case Submission & Clean-up](#5-bash-script-batch-use-case-submission--clean-up)

---

## 1. Python: End-to-End Ad-Hoc Use-Case Submission & Evaluation

This script uses only the Python standard library (`urllib.request`, `json`) with no third-party dependencies required.

```python
#!/usr/bin/env python3
"""
End-to-End Dokimi A/B Testing Workflow:
1. Submits an ad-hoc use-case (Kafka consumer group rebalancing)
2. Triggers a full Dokimi A/B evaluation across all context arms
3. Inspects statistical significance (p-values, Holm-Bonferroni) and score deltas
4. Cleans up the ad-hoc use-case
"""

import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"


def http_post(endpoint: str, data: dict) -> dict:
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get(endpoint: str) -> dict:
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def http_delete(endpoint: str) -> dict:
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    print("=" * 70)
    print("🧪 Dokimi A/B Testing Platform - Programmatic Evaluation")
    print("=" * 70)

    # 1. Define Ad-Hoc Use-Case
    use_case_payload = {
        "name": "Kafka Consumer Lag & Rebalancing Storm Triage",
        "description": "Evaluate context arms on diagnosing consumer rebalance loops and partition skew.",
        "parameters": {
            "domain": "Event Streaming / Messaging",
            "cluster_type": "Apache Kafka / Strimzi",
            "alpha": 0.05
        },
        "expected_outputs": [
            "Diagnose max.poll.interval.ms timeout causes",
            "Tune session.timeout.ms and heartbeat.interval.ms",
            "Provide cooperative-sticky assignor configuration"
        ],
        "scenarios": [
            {
                "id": "kafka_sc_01",
                "prompt": "Consumer group 'order-processing' is stuck in continuous rebalancing loop. Lag is growing by 5k msg/sec. How to mitigate?",
                "expected_topics": [
                    "Check max.poll.interval.ms vs message processing time",
                    "Switch to CooperativeStickyAssignor to prevent stop-the-world rebalance",
                    "Inspect GC pauses on consumer JVM instances",
                    "Scale out partitions and consumers proportionally"
                ],
                "category": "Consumer Rebalance"
            },
            {
                "id": "kafka_sc_02",
                "prompt": "Two partitions in topic 'payments' have 20x higher lag than all other partitions. How to rebalance data distribution?",
                "expected_topics": [
                    "Inspect partition key hashing skew",
                    "Check for hot keys in upstream producer payload",
                    "Verify consumer group partition assignment with kafka-consumer-groups.sh"
                ],
                "category": "Partition Skew"
            }
        ]
    }

    # 2. Submit Use-Case
    print("\n1. Submitting Ad-Hoc Use-Case...")
    use_case = http_post("/api/use-cases/submit", use_case_payload)
    uc_id = use_case["id"]
    print(f"   ✅ Registered: '{use_case['name']}' (ID: {uc_id})")

    # 3. Trigger Dokimi Experiment Run
    print(f"\n2. Executing Dokimi Paired A/B Experiment against use-case '{uc_id}'...")
    exp_payload = {
        "name": "Kafka Rebalance Context Optimization",
        "use_case_id": uc_id,
        "model": "mock-model",
        "provider": "mock"
    }

    start_time = time.time()
    experiment = http_post("/api/experiments/run", exp_payload)
    elapsed = time.time() - start_time

    print(f"   ✅ Experiment Complete (ID: {experiment['id']}) in {elapsed:.2f}s")
    print(f"   📢 Verdict: {experiment['summary_verdict']}\n")

    # 4. Display Results Table
    print(f"{'Arm Spec ID':<16} | {'Mean Score':<10} | {'Delta vs Base':<14} | {'p-value':<10} | {'Sig (p<0.05)':<12} | {'Novel Atoms':<12}")
    print("-" * 88)

    base_score = experiment["metrics_by_arm"]["baseline"]["mean_score"]
    for arm_id, m in experiment["metrics_by_arm"].items():
        delta = m["mean_score"] - base_score
        delta_str = f"+{delta:.4f}" if delta >= 0 else f"{delta:.4f}"
        pval_str = f"{m['p_value']:.4f}" if m["p_value"] is not None else "— (Base)"
        sig_str = "✅ YES" if m["stat_significant"] else ("Base" if arm_id == "baseline" else "❌ NO")
        print(f"{arm_id:<16} | {m['mean_score']:<10.4f} | {delta_str:<14} | {pval_str:<10} | {sig_str:<12} | +{m['novel_atoms_added']:<11}")

    # 5. Clean Up Use-Case
    print(f"\n3. Cleaning up ad-hoc use-case '{uc_id}'...")
    del_res = http_delete(f"/api/use-cases/{uc_id}")
    print(f"   ✅ Cleaned up: {del_res['status']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
```

---

## 2. Python: Async Client with `httpx`

```python
import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"


async def run_async_evaluation():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Health check
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200

        # 2. Submit use-case
        payload = {
            "name": "Cloud IAM Least Privilege Enforcement",
            "description": "Evaluate context arms on AWS/GCP wildcard permission pruning.",
            "parameters": {"domain": "Cloud Security", "alpha": 0.05},
            "expected_outputs": ["Remove Action: *", "Enforce resource ARNs"],
            "scenarios": [
                {
                    "id": "iam_01",
                    "prompt": "An IAM role has Action: 's3:*' on Resource: '*'. How to remediate to read-only access for bucket 'app-data'?",
                    "expected_topics": [
                        "Replace 's3:*' with 's3:GetObject' and 's3:ListBucket'",
                        "Scope Resource to 'arn:aws:s3:::app-data' and 'arn:aws:s3:::app-data/*'",
                        "Validate using AWS Access Analyzer"
                    ],
                    "category": "IAM Security"
                }
            ]
        }
        res = await client.post("/api/use-cases/submit", json=payload)
        uc = res.json()
        print(f"Registered use-case: {uc['id']}")

        # 3. Run evaluation
        exp_res = await client.post(
            "/api/experiments/run",
            json={
                "name": "IAM Security Eval",
                "use_case_id": uc["id"],
                "model": "mock-model",
                "provider": "mock"
            }
        )
        exp = exp_res.json()
        print(f"Top arm: {exp['summary_verdict']}")

        # 4. Clean up
        await client.delete(f"/api/use-cases/{uc['id']}")
        print("Cleaned up successfully.")

if __name__ == "__main__":
    asyncio.run(run_async_evaluation())
```

---

## 3. JavaScript / Node.js: Fetch & Axios Integration

### Using native `fetch` (Node.js 18+ or Browser):

```javascript
const BASE_URL = "http://127.0.0.1:8000";

async function runDokimiUseCase() {
    try {
        // 1. Submit Ad-Hoc Use-Case
        const submitResponse = await fetch(`${BASE_URL}/api/use-cases/submit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: "Postgres Connection Pool Saturation Drill",
                description: "Assess context arms on PgBouncer connection queuing and backend worker starvation.",
                parameters: { domain: "Database SRE", alpha: 0.05 },
                expected_outputs: ["Configure transaction pooling", "Tune max_connections"],
                scenarios: [
                    {
                        id: "pg_pool_01",
                        prompt: "Postgres server reached max_connections (500). Applications receiving 'FATAL: remaining connection slots are reserved'. What is the immediate fix?",
                        expected_topics: [
                            "Deploy PgBouncer in transaction pooling mode",
                            "Identify idle in transaction connections",
                            "Tune application pool maxActive limits",
                            "Terminate non-essential idle backend connections"
                        ],
                        category: "Postgres Tuning"
                    }
                ]
            })
        });

        const useCase = await submitResponse.json();
        console.log(`✅ Registered use-case: ${useCase.name} (ID: ${useCase.id})`);

        // 2. Run A/B Experiment
        const expResponse = await fetch(`${BASE_URL}/api/experiments/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: "Postgres Pooling Evaluation",
                use_case_id: useCase.id,
                model: "mock-model",
                provider: "mock"
            })
        });

        const experiment = await expResponse.json();
        console.log("📊 Experiment Result:", experiment.summary_verdict);

        // 3. Delete Ad-Hoc Use-Case
        await fetch(`${BASE_URL}/api/use-cases/${encodeURIComponent(useCase.id)}`, {
            method: "DELETE"
        });
        console.log("🧹 Cleaned up temporary use-case.");

    } catch (err) {
        console.error("❌ Error running Dokimi integration:", err);
    }
}

runDokimiUseCase();
```

---

## 4. cURL & jq: Command-Line Workflow

```bash
# 1. Health check
curl -s http://127.0.0.1:8000/health | jq .

# 2. Submit new ad-hoc use-case
UC_RESP=$(curl -s -X POST http://127.0.0.1:8000/api/use-cases/submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Redis Memory Eviction Storm Triage",
    "description": "Assess agent triage on maxmemory policy OOM errors.",
    "parameters": {"domain": "Cache Infrastructure", "alpha": 0.05},
    "expected_outputs": ["Identify keys without TTL", "Tune volatile-lru"],
    "scenarios": [
      {
        "id": "redis_sc_1",
        "prompt": "Redis cluster returning (error) OOM command not allowed when used memory > maxmemory. How to triage?",
        "expected_topics": [
          "Check INFO memory and maxmemory-policy",
          "Identify big keys with redis-cli --bigkeys",
          "Enable volatile-lru or allkeys-lru eviction",
          "Set TTLs on unbounded cache keys"
        ],
        "category": "Redis Caching"
      }
    ]
  }')

echo "$UC_RESP" | jq .
UC_ID=$(echo "$UC_RESP" | jq -r .id)

# 3. Run Dokimi A/B experiment
curl -s -X POST http://127.0.0.1:8000/api/experiments/run \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Redis Eviction Context Optimization\",
    \"use_case_id\": \"$UC_ID\",
    \"model\": \"mock-model\",
    \"provider\": \"mock\"
  }" | jq '{id: .id, summary: .summary_verdict, metrics: .metrics_by_arm}'

# 4. Clean up use-case
curl -s -X DELETE "http://127.0.0.1:8000/api/use-cases/$UC_ID" | jq .
```

---

## 5. Bash Script: Batch Use-Case Submission & Clean-up

Save as `scripts/batch_usecase_test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://127.0.0.1:8000"

echo "=== Submitting Multiple Use-Cases ==="

DOMAINS=("Networking" "Storage" "CI_CD")

for DOMAIN in "${DOMAINS[@]}"; do
  echo "Submitting domain: $DOMAIN..."
  RESP=$(curl -s -X POST "${BASE_URL}/api/use-cases/submit" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"Domain Benchmark: ${DOMAIN}\",
      \"description\": \"Automated batch validation for ${DOMAIN}\",
      \"parameters\": {\"domain\": \"${DOMAIN}\", \"alpha\": 0.05},
      \"expected_outputs\": [\"Accuracy > 80%\", \"Valid triage sequence\"],
      \"scenarios\": [
        {
          \"id\": \"${DOMAIN,,}_sc_1\",
          \"prompt\": \"How to diagnose common ${DOMAIN} failure modes?\",
          \"expected_topics\": [\"metrics\", \"logs\", \"remediation\"],
          \"category\": \"${DOMAIN}\"
        }
      ]
    }")
  
  UC_ID=$(echo "$RESP" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
  echo "  -> Created: $UC_ID"
done

echo "=== Current Registered Use-Cases ==="
curl -s "${BASE_URL}/api/use-cases" | grep -o '"id":"[^"]*' | cut -d'"' -f4
```
