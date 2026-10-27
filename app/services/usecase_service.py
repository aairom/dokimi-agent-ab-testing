"""Use-Case Service managing hardcoded demo fixtures and dynamic ad-hoc submissions."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

from app.core.config import settings
from app.core.models import UseCase, UseCaseScenario, UseCaseSource, QuestionItem, VariantConfig

logger = logging.getLogger("dokimi_app.usecases")


class UseCaseService:
    """Manages hardcoded fixtures and persistent ad-hoc use-cases."""

    _ADHOC_STORAGE_FILE: Path = settings.DATA_DIR / "adhoc_usecases.json"
    _ADHOC_STORE: Dict[str, UseCase] = {}

    @classmethod
    def get_hardcoded_usecases(cls) -> List[UseCase]:
        """Return pre-configured, immutable hardcoded demonstration use-cases."""
        return [
            UseCase(
                id="sre_incident_response",
                name="SRE Incident Response Optimization",
                description="Evaluate context augmentation (Runbook Docs, SRE Persona Profile, Actionable SRE Skill) for production incidents.",
                source=UseCaseSource.HARDCODED,
                is_mutable=False,
                parameters={
                    "domain": "DevOps & SRE",
                    "alpha_threshold": 0.05,
                    "target_latency_ms": 350.0,
                    "expected_arms": ["baseline", "arm_docs", "arm_profile", "arm_skill"],
                },
                expected_outputs=[
                    "Exact Kubernetes kubectl commands and flag parameters",
                    "Root cause identification (e.g. Exit Code 137 -> OOMKilled)",
                    "PostgreSQL lock remediation (pg_stat_activity query)",
                    "Automated payment gateway failover protocols"
                ],
                scenarios=[
                    UseCaseScenario(
                        id="scn_k8s_oom",
                        prompt="A production microservice pod in namespace 'production' is restarting continuously with Exit Code 137. How do I immediately diagnose and remediate this?",
                        expected_topics=[
                            "Exit code 137 indicates OOMKilled (Out of Memory)",
                            "kubectl top pod or describe to check memory limits and termination reason",
                            "Increase container memory limit resources in Deployment YAML or kubectl set resources",
                            "Check previous container logs using kubectl logs --previous"
                        ],
                        category="kubernetes"
                    ),
                    UseCaseScenario(
                        id="scn_pg_pool",
                        prompt="PostgreSQL database connection pool is completely exhausted, causing application HTTP 500 errors. How do we identify the culprit connections and unblock the system?",
                        expected_topics=[
                            "Query pg_stat_activity to find idle in transaction connections",
                            "Terminate long-running or blocking connections with pg_terminate_backend or pg_cancel_backend",
                            "Check connection pool settings like PgBouncer pool_mode = transaction and connection limits",
                            "Measure transaction duration using now() - xact_start"
                        ],
                        category="database"
                    ),
                    UseCaseScenario(
                        id="scn_payment_spike",
                        prompt="Our primary payment gateway is experiencing severe latency spikes (P99 > 1500ms) and 503 errors. What are the triage steps and automated failover procedure?",
                        expected_topics=[
                            "Verify circuit breaker threshold and error rate / latency metrics",
                            "Trigger gateway failover to secondary processor (Adyen/Stripe fallback)",
                            "Replay or flush idempotent transactions using idempotency key",
                            "Check Kafka consumer queue health for settlement events"
                        ],
                        category="payments"
                    ),
                    UseCaseScenario(
                        id="scn_k8s_crashloop",
                        prompt="A newly deployed frontend pod is failing with CrashLoopBackOff and Exit Code 1. What is the systematic debugging sequence?",
                        expected_topics=[
                            "Fetch previous logs with kubectl logs <pod> --previous --tail=100",
                            "Inspect Kubernetes events with kubectl describe pod",
                            "Verify ConfigMap, Secret environment bindings and DNS resolution",
                            "Execute rollback with kubectl rollout undo if deployment is poisoned"
                        ],
                        category="kubernetes"
                    ),
                    UseCaseScenario(
                        id="scn_db_deadlock",
                        prompt="How do we mitigate database deadlocks and slow queries blocking critical checkout transactions during a flash sale?",
                        expected_topics=[
                            "Inspect pg_stat_activity and pg_locks for lock contention",
                            "Identify blocking queries ordered by duration",
                            "Cancel blocking backend PIDs safely",
                            "Ensure query indexes and connection pool transaction isolation"
                        ],
                        category="database"
                    )
                ]
            ),
            UseCase(
                id="cloud_security_audit",
                name="Cloud Security Compliance & IAM Auditing",
                description="Assess agent precision in identifying overly permissive IAM roles, misconfigured S3 buckets, and open security groups.",
                source=UseCaseSource.HARDCODED,
                is_mutable=False,
                parameters={
                    "domain": "Cloud Security",
                    "compliance_standard": "CIS Benchmarks v3.0",
                    "alpha_threshold": 0.05
                },
                expected_outputs=[
                    "Identification of wildcard '*' IAM permissions",
                    "Enforcement of TLS 1.3 and bucket encryption at rest",
                    "Remediation CLI commands for AWS/IBM Cloud security groups"
                ],
                scenarios=[
                    UseCaseScenario(
                        id="scn_sec_iam",
                        prompt="A CI/CD service account IAM role has AdministratorAccess policy attached. How do we apply least-privilege scoping without breaking the build pipeline?",
                        expected_topics=[
                            "Analyze CloudTrail or IAM Access Advisor for actual permission usage over 90 days",
                            "Generate scoped policy with specific Actions and Resource ARNs",
                            "Replace AdministratorAccess with scoped role and permission boundary",
                            "Use temporary credential STS AssumeRole instead of long-lived access keys"
                        ],
                        category="security"
                    ),
                    UseCaseScenario(
                        id="scn_sec_s3",
                        prompt="Security scanner flagged an Object Storage bucket with public read access. What is the immediate lockdown command and validation step?",
                        expected_topics=[
                            "Enable S3 Block Public Access at bucket and account level",
                            "Apply restrictive Bucket Policy denying Principal: *",
                            "Verify bucket ACLs do not grant AllUsers or AuthenticatedUsers Read permissions",
                            "Enable default AES256 or KMS encryption with bucket key"
                        ],
                        category="security"
                    )
                ]
            )
        ]

    @classmethod
    def load_adhoc_usecases(cls) -> Dict[str, UseCase]:
        """Load persistent ad-hoc use-cases from disk into cache."""
        if cls._ADHOC_STORAGE_FILE.exists():
            try:
                with open(cls._ADHOC_STORAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cls._ADHOC_STORE = {
                        item["id"]: UseCase(**item) for item in data
                    }
                    logger.info(f"Loaded {len(cls._ADHOC_STORE)} ad-hoc use-cases from disk.")
            except Exception as e:
                logger.error(f"Failed to load ad-hoc use-cases from {cls._ADHOC_STORAGE_FILE}: {e}")
                cls._ADHOC_STORE = {}
        return cls._ADHOC_STORE

    @classmethod
    def save_adhoc_usecases(cls) -> None:
        """Persist ad-hoc use-cases to disk."""
        try:
            cls._ADHOC_STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(cls._ADHOC_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump([uc.model_dump(mode="json") for uc in cls._ADHOC_STORE.values()], f, indent=2)
            logger.info(f"Saved {len(cls._ADHOC_STORE)} ad-hoc use-cases to disk.")
        except Exception as e:
            logger.error(f"Failed to persist ad-hoc use-cases: {e}")

    @classmethod
    def list_all_usecases(cls) -> List[UseCase]:
        """Retrieve unified list of hardcoded and dynamic ad-hoc use-cases."""
        hardcoded = cls.get_hardcoded_usecases()
        cls.load_adhoc_usecases()
        return hardcoded + list(cls._ADHOC_STORE.values())

    @classmethod
    def get_usecase(cls, usecase_id: str) -> Optional[UseCase]:
        """Retrieve a specific use-case by ID."""
        for hc in cls.get_hardcoded_usecases():
            if hc.id == usecase_id:
                return hc
        cls.load_adhoc_usecases()
        return cls._ADHOC_STORE.get(usecase_id)

    @classmethod
    def submit_adhoc_usecase(
        cls,
        name: str,
        description: str,
        scenarios: List[UseCaseScenario],
        parameters: Optional[Dict[str, Any]] = None,
        expected_outputs: Optional[List[str]] = None,
        custom_variants: Optional[List[VariantConfig]] = None,
        usecase_id: Optional[str] = None
    ) -> UseCase:
        """Create or update an ad-hoc use-case."""
        cls.load_adhoc_usecases()
        now = datetime.now(timezone.utc)
        uid = usecase_id or f"adhoc_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

        use_case = UseCase(
            id=uid,
            name=name,
            description=description,
            source=UseCaseSource.ADHOC,
            is_mutable=True,
            parameters=parameters or {},
            expected_outputs=expected_outputs or [],
            scenarios=scenarios,
            custom_variants=custom_variants,
            created_at=now,
            updated_at=now,
        )

        cls._ADHOC_STORE[uid] = use_case
        cls.save_adhoc_usecases()
        logger.info(f"Ad-hoc use-case '{name}' ({uid}) submitted with {len(scenarios)} scenarios.")
        return use_case

    @classmethod
    def delete_adhoc_usecase(cls, usecase_id: str) -> bool:
        """Delete a dynamic ad-hoc use-case. Hardcoded use-cases cannot be deleted."""
        # Check hardcoded
        for hc in cls.get_hardcoded_usecases():
            if hc.id == usecase_id:
                raise ValueError("Hardcoded demonstration use-cases are immutable and cannot be deleted.")

        cls.load_adhoc_usecases()
        if usecase_id in cls._ADHOC_STORE:
            del cls._ADHOC_STORE[usecase_id]
            cls.save_adhoc_usecases()
            logger.info(f"Deleted ad-hoc use-case {usecase_id}.")
            return True
        return False

    @classmethod
    def get_questions_for_usecase(cls, usecase_id: str) -> List[QuestionItem]:
        """Convert use-case scenarios into QuestionItem objects for Dokimi engine."""
        uc = cls.get_usecase(usecase_id)
        if not uc:
            return []
        return [
            QuestionItem(
                id=scn.id,
                question=scn.prompt,
                expected_topics=scn.expected_topics,
                category=scn.category,
                use_case_id=uc.id,
            )
            for scn in uc.scenarios
        ]


# Initialize store on module load
UseCaseService.load_adhoc_usecases()
