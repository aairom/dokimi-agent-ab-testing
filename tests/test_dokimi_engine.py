"""Unit tests for models, LLM service, and Dokimi evaluation engine."""

import pytest
from app.core.models import (
    VariantConfig,
    ContextArmType,
    QuestionItem,
    ChatRequest,
)
from app.services.llm_service import LLMService
from app.services.dokimi_engine import DokimiEvaluationEngine


@pytest.mark.asyncio
async def test_llm_service_mock_generation():
    """Verify that the mock LLM engine responds appropriately to prompt context variations."""
    # Test baseline response
    res_base = await LLMService.generate_response(
        prompt="A pod crashed with exit code 137.",
        system_prompt=None,
        context=None,
        provider="mock",
    )
    assert res_base["text"] is not None
    assert "137" in res_base["text"]
    assert res_base["token_count"] > 0
    assert res_base["latency_ms"] > 0

    # Test skill arm response
    skill_context = "### High-Velocity SRE Triage Skill\nExit Code 137 (OOMKilled): kubectl top pod"
    res_skill = await LLMService.generate_response(
        prompt="A pod crashed with exit code 137.",
        system_prompt="Senior SRE",
        context=skill_context,
        provider="mock",
    )
    assert "Immediate SRE Mitigation" in res_skill["text"]
    assert "kubectl" in res_skill["text"]


def test_default_variants_loading():
    """Verify default SRE incident response variants load with valid Dokimi arm specs."""
    variants = DokimiEvaluationEngine.get_default_variants()
    assert len(variants) == 4
    
    arm_types = [v.arm_type for v in variants]
    assert ContextArmType.BASELINE in arm_types
    assert ContextArmType.DOCS in arm_types
    assert ContextArmType.PROFILE in arm_types
    assert ContextArmType.SKILL in arm_types

    baseline = next(v for v in variants if v.id == "baseline")
    assert baseline.arm_spec == "baseline"


def test_questions_loading():
    """Verify golden evaluation questions are loaded correctly."""
    questions = DokimiEvaluationEngine.load_evaluation_questions()
    assert len(questions) >= 5
    for q in questions:
        assert q.id is not None
        assert len(q.question) > 0
        assert len(q.expected_topics) > 0


@pytest.mark.asyncio
async def test_run_experiment_evaluation():
    """Verify full Dokimi paired A/B evaluation execution and Holm-Bonferroni correction."""
    run = await DokimiEvaluationEngine.run_experiment(
        name="Test Incident Eval Run",
        model="mock-model",
        provider="mock",
    )
    assert run.id.startswith("exp_")
    assert run.status == "completed"
    assert len(run.metrics_by_arm) == 4
    assert run.baseline_arm == "baseline"

    # Baseline should have no p-value, treatment arms should have p-values
    base_metric = run.metrics_by_arm["baseline"]
    assert base_metric.p_value is None

    skill_metric = run.metrics_by_arm["arm_skill"]
    assert skill_metric.mean_score > base_metric.mean_score
    assert skill_metric.p_value is not None
    assert skill_metric.stat_significant is True

    # Check generated markdown report
    md = DokimiEvaluationEngine.generate_markdown_report(run)
    assert "Dokimi Agent Context A/B Testing Scorecard" in md
    assert "Context Arm Performance Comparison" in md
