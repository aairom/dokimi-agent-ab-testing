# Context Arm: Raw Standard SRE (Variant B)

## Kubernetes Incident Response Guidelines
1. Check pod status using `kubectl get pods -n <namespace>`.
2. Inspect events with `kubectl describe pod <pod_name> -n <namespace>`.
3. Check container logs using `kubectl logs <pod_name> -c <container> --previous`.
4. If OOMKilled (Exit Code 137), check node resource pressure and increase container memory limits in Deployment YAML.
5. If CrashLoopBackOff (Exit Code 1/2), check application logs for uncaught exceptions, DB connection errors, or missing config secrets.

## Database Connection Exhaustion (PostgreSQL)
1. Query active connections: `SELECT count(*), state FROM pg_stat_activity GROUP BY state;`.
2. Terminate idle connections: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < now() - INTERVAL '5 minutes';`.
3. Adjust PgBouncer pool mode to 'transaction' and max_client_conn to 500.

## Payment Gateway Latency Spikes
1. Check Stripe/Adyen API status dashboard.
2. Inspect egress proxy connection timeouts.
3. If circuit breaker is tripped (503 Service Unavailable), switch gateway routing to fallback processor (Adyen Secondary).
4. Flush stuck idempotent transaction queue.
