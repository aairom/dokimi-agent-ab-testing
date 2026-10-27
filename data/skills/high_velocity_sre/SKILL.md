---
name: high_velocity_sre_skill
description: Precision SRE Triage & Root Cause Runbook for Kubernetes, PostgreSQL, and Distributed Payment Gateways
version: 2.1.0
---

# High-Velocity SRE Triage Skill

## 1. Kubernetes Rapid Diagnostic Matrix
- **Exit Code 137 (OOMKilled)**:
  - Run: `kubectl top pod -n production --sort-by=memory`
  - Action: Immediately scale up deployment `resources.limits.memory` by 1.5x via `kubectl set resources deployment/<app> --limits=memory=2Gi`.
  - Alert Channel: Post RC trace to `#incident-war-room` with pod memory profile.
- **CrashLoopBackOff (Exit 1/2)**:
  - Run: `kubectl logs <pod> -n production --previous --tail=100`
  - Action: If DNS resolution error, verify CoreDNS `kubectl rollout restart deployment/coredns -n kube-system`.
  - Action: If ConfigMap/Secret drift, run `kubectl rollout undo deployment/<app>`.

## 2. PostgreSQL Connection Pool Storm Mitigation
- **Diagnosis**: Connection ceiling reached (max_connections=300).
- **Execution Script**:
  ```sql
  -- Step 1: Identify blocking transaction PID
  SELECT pid, now() - xact_start AS duration, query 
  FROM pg_stat_activity 
  WHERE state = 'idle in transaction' AND (now() - xact_start) > interval '2 minutes'
  ORDER BY duration DESC;

  -- Step 2: Gracefully terminate stuck sessions
  SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND (now() - xact_start) > interval '2 minutes';
  ```
- **PgBouncer Emergency Tuning**: Execute `RELOAD` after switching `pool_mode = transaction` and `default_pool_size = 80`.

## 3. Payment Gateway Failover & Circuit Breaker Protocol
- **Telemetry Threshold**: P99 Latency > 1200ms for 30s OR Error Rate > 2.5%.
- **Automated Actions**:
  1. Trigger dynamic failover to Secondary Gateway: `curl -X POST http://payment-router.internal/api/v1/routing/failover -d '{"primary":"stripe","fallback":"adyen","reason":"latency_spike_p99"}'`.
  2. Verify webhook queue consumer health on Kafka topic `payment.settlement.events`.
  3. Replay failed idempotent transactions with deduplication key header `X-Idempotency-Key`.
