"""Unit tests for FastAPI REST endpoints and interactive chat."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Verify health check returns healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "Dokimi" in data["app"]


@pytest.mark.asyncio
async def test_get_variants_endpoint():
    """Verify retrieving configured context variants."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test GET / root page render
        resp_index = await client.get("/")
        assert resp_index.status_code == 200
        assert "Dokimi Agent Context A/B Testing" in resp_index.text

        response = await client.get("/api/variants")
        assert response.status_code == 200
        variants = response.json()
        assert len(variants) >= 4
        ids = [v["id"] for v in variants]
        assert "baseline" in ids
        assert "arm_skill" in ids


@pytest.mark.asyncio
async def test_get_questions_endpoint():
    """Verify retrieving evaluation questions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/questions")
        assert response.status_code == 200
        questions = response.json()
        assert len(questions) >= 5


@pytest.mark.asyncio
async def test_run_experiment_endpoint():
    """Verify running an A/B testing experiment via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/experiments/run",
            json={
                "name": "API Test Experiment",
                "model": "mock-model",
                "provider": "mock",
            },
        )
        assert response.status_code == 200
        exp = response.json()
        assert exp["id"] is not None
        assert "arm_skill" in exp["metrics_by_arm"]
        assert exp["metrics_by_arm"]["arm_skill"]["mean_score"] > 0.8


@pytest.mark.asyncio
async def test_chat_endpoint():
    """Verify interactive dual agent chat endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "variant_id": "arm_skill",
                "message": "Pod restarting with Exit Code 137",
            },
        )
        assert response.status_code == 200
        chat_data = response.json()
        assert chat_data["variant_id"] == "arm_skill"
        assert "kubectl" in chat_data["answer"]
        assert chat_data["latency_ms"] > 0
        assert chat_data["token_count"] > 0


@pytest.mark.asyncio
async def test_variant_crud_endpoints():
    """Verify creating and deleting custom variants via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create custom variant
        payload = {
            "id": "custom_test_arm",
            "name": "Custom Test Arm",
            "arm_type": "profile",
            "arm_spec": "profile:test.md",
            "description": "Test description",
            "system_prompt": "You are a test agent",
            "context_content": "Context test"
        }
        res_create = await client.post("/api/variants", json=payload)
        assert res_create.status_code == 200
        assert res_create.json()["id"] == "custom_test_arm"

        # Delete custom variant
        res_del = await client.delete("/api/variants/custom_test_arm")
        assert res_del.status_code == 200

        # Attempt deleting baseline should fail with 400
        res_del_base = await client.delete("/api/variants/baseline")
        assert res_del_base.status_code == 400


@pytest.mark.asyncio
async def test_experiment_report_endpoints():
    """Verify fetching experiment by ID and markdown report."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # List experiments
        res_list = await client.get("/api/experiments")
        assert res_list.status_code == 200
        exps = res_list.json()
        if exps:
            exp_id = exps[0]["id"]
            res_single = await client.get(f"/api/experiments/{exp_id}")
            assert res_single.status_code == 200


@pytest.mark.asyncio
async def test_usecase_api_endpoints():
    """Verify listing, submitting, retrieving, and deleting use-cases."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List use cases (should include hardcoded fixtures)
        res_list = await client.get("/api/use-cases")
        assert res_list.status_code == 200
        usecases = res_list.json()
        assert len(usecases) >= 2
        ids = [uc["id"] for uc in usecases]
        assert "sre_incident_response" in ids
        assert "cloud_security_audit" in ids

        # 2. Get specific hardcoded use case
        res_sre = await client.get("/api/use-cases/sre_incident_response")
        assert res_sre.status_code == 200
        assert res_sre.json()["source"] == "hardcoded"
        assert res_sre.json()["is_mutable"] is False

        # 3. Submit dynamic ad-hoc use-case
        adhoc_payload = {
            "name": "Database Failover Drill",
            "description": "Evaluate multi-region recovery and consensus",
            "parameters": {"domain": "Database", "alpha": 0.05},
            "expected_outputs": ["Quorum recovery", "Data consistency"],
            "scenarios": [
                {
                    "id": "db_failover_1",
                    "category": "High Availability",
                    "prompt": "Primary node unresponsive, how to promote replica?",
                    "expected_topics": ["promote", "failover", "quorum"]
                }
            ]
        }
        res_submit = await client.post("/api/use-cases/submit", json=adhoc_payload)
        assert res_submit.status_code == 200
        adhoc_uc = res_submit.json()
        adhoc_id = adhoc_uc["id"]
        assert adhoc_uc["source"] == "adhoc"
        assert adhoc_uc["is_mutable"] is True
        assert len(adhoc_uc["scenarios"]) == 1

        # 4. Filter questions by new adhoc use-case
        res_q = await client.get(f"/api/questions?use_case_id={adhoc_id}")
        assert res_q.status_code == 200
        q_list = res_q.json()
        assert len(q_list) == 1
        assert q_list[0]["id"] == "db_failover_1"

        # 5. Run experiment with adhoc use-case
        res_exp = await client.post(
            "/api/experiments/run",
            json={
                "name": "Database Failover A/B Eval",
                "use_case_id": adhoc_id,
                "model": "mock-model",
                "provider": "mock"
            }
        )
        assert res_exp.status_code == 200
        exp_data = res_exp.json()
        assert exp_data["use_case_id"] == adhoc_id

        # 6. Delete ad-hoc use-case
        res_del = await client.delete(f"/api/use-cases/{adhoc_id}")
        assert res_del.status_code == 200

        # 7. Attempting to delete hardcoded fixture must fail with 400
        res_del_hardcoded = await client.delete("/api/use-cases/sre_incident_response")
        assert res_del_hardcoded.status_code == 400
