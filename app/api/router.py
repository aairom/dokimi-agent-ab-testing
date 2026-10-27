"""REST API router for Variants, Questions, Experiments, and Interactive Chat."""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.models import (
    VariantConfig,
    QuestionItem,
    ExperimentRun,
    ChatRequest,
    ChatResponse,
    ContextArmType,
    LocalModelInfo,
    ModelDiscoveryResponse,
    TaskProgress,
    TaskStatus,
    UseCase,
    UseCaseScenario,
    UseCaseSource,
)
from fastapi import Query
from fastapi.responses import JSONResponse, StreamingResponse
from app.services.dokimi_engine import DokimiEvaluationEngine
from app.services.llm_service import LLMService
from app.services.progress_manager import progress_manager
from app.services.usecase_service import UseCaseService

logger = logging.getLogger("dokimi_app.api")
router = APIRouter(prefix="/api", tags=["Dokimi A/B Testing"])

# In-memory storage cache backed by filesystem persistence
_VARIANTS_STORE: List[VariantConfig] = []
_EXPERIMENTS_STORE: Dict[str, ExperimentRun] = {}


def _initialize_state():
    """Ensure initial variants and pre-computed demo experiment runs are loaded."""
    global _VARIANTS_STORE, _EXPERIMENTS_STORE
    if not _VARIANTS_STORE:
        _VARIANTS_STORE = DokimiEvaluationEngine.get_default_variants()

    # Load any existing scorecard outputs
    for file in settings.OUTPUT_DIR.glob("*_scorecard.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                exp = ExperimentRun(**data)
                _EXPERIMENTS_STORE[exp.id] = exp
        except Exception as e:
            logger.warning(f"Could not load scorecard {file}: {e}")


_initialize_state()


# --- LOCAL MODEL DISCOVERY ---

@router.get("/models/local", response_model=ModelDiscoveryResponse)
async def get_local_models(
    provider: str = Query(..., description="Provider backend: 'local-ollama' or 'local-llamacpp'")
):
    """
    Discover and return installed models from the selected local inference engine.
    Supports Ollama (GET /api/tags) and llama.cpp (GET /v1/models).
    """
    logger.info(f"API Request: /api/models/local for provider '{provider}'")
    discovery_res = await LLMService.discover_local_models(provider=provider)
    
    # If backend failed to connect, return appropriate 503 or 502 with structured payload
    if not discovery_res.is_connected:
        if "timed out" in discovery_res.status_message.lower():
            return JSONResponse(
                status_code=504,
                content=discovery_res.model_dump(),
            )
        return JSONResponse(
            status_code=503,
            content=discovery_res.model_dump(),
        )

    return discovery_res


# --- VARIANTS / CONTEXT ARMS MANAGEMENT ---

@router.get("/variants", response_model=List[VariantConfig])
async def get_variants():
    """Retrieve all configured A/B test context arms."""
    return _VARIANTS_STORE


@router.post("/variants", response_model=VariantConfig)
async def create_variant(variant: VariantConfig):
    """Register or update an A/B test context arm."""
    for i, v in enumerate(_VARIANTS_STORE):
        if v.id == variant.id:
            _VARIANTS_STORE[i] = variant
            return variant
    _VARIANTS_STORE.append(variant)
    return variant


@router.delete("/variants/{variant_id}")
async def delete_variant(variant_id: str):
    """Remove a variant from testing pool."""
    global _VARIANTS_STORE
    if variant_id == "baseline":
        raise HTTPException(status_code=400, detail="Cannot delete baseline arm.")
    _VARIANTS_STORE = [v for v in _VARIANTS_STORE if v.id != variant_id]
    return {"status": "deleted", "variant_id": variant_id}


# --- EVALUATION QUESTIONS ---

@router.get("/questions", response_model=List[QuestionItem])
async def get_questions(use_case_id: Optional[str] = None):
    """Retrieve the evaluation questions, optionally scoped to a specific use-case."""
    if use_case_id:
        questions = UseCaseService.get_questions_for_usecase(use_case_id)
        if questions:
            return questions
    return DokimiEvaluationEngine.load_evaluation_questions()


@router.post("/questions", response_model=QuestionItem)
async def add_question(item: QuestionItem):
    """Add a new evaluation question to the dataset."""
    questions = DokimiEvaluationEngine.load_evaluation_questions()
    questions.append(item)
    qpath = settings.DATA_DIR / "eval_sets" / "incident_questions.json"
    with open(qpath, "w", encoding="utf-8") as f:
        json.dump([q.model_dump() for q in questions], f, indent=2)
    return item


# --- USE-CASES MANAGEMENT (HARDCODED & AD-HOC) ---

class SubmitUseCaseRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Use-case title")
    description: str = Field(default="", description="Use-case description and goals")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters and evaluation thresholds")
    expected_outputs: List[str] = Field(default_factory=list, description="Global success criteria")
    scenarios: List[UseCaseScenario] = Field(..., min_length=1, description="List of test scenarios to evaluate")
    custom_variants: Optional[List[VariantConfig]] = Field(default=None, description="Optional custom context arms")


@router.get("/use-cases", response_model=List[UseCase])
async def list_use_cases():
    """List all available use-cases (both hardcoded fixtures and submitted ad-hoc use-cases)."""
    return UseCaseService.list_all_usecases()


@router.get("/use-cases/{usecase_id}", response_model=UseCase)
async def get_use_case_details(usecase_id: str):
    """Retrieve details and test scenarios for a specific use-case."""
    uc = UseCaseService.get_usecase(usecase_id)
    if not uc:
        raise HTTPException(status_code=404, detail=f"Use-case '{usecase_id}' not found.")
    return uc


@router.post("/use-cases/submit", response_model=UseCase)
async def submit_ad_hoc_use_case(req: SubmitUseCaseRequest):
    """Submit a dynamic ad-hoc use-case at runtime without code changes."""
    if not settings.ALLOW_ADHOC_USECASES:
        raise HTTPException(status_code=403, detail="Ad-hoc use-case submission is disabled by configuration (ALLOW_ADHOC_USECASES=false).")

    use_case = UseCaseService.submit_adhoc_usecase(
        name=req.name,
        description=req.description,
        scenarios=req.scenarios,
        parameters=req.parameters,
        expected_outputs=req.expected_outputs,
        custom_variants=req.custom_variants
    )
    return use_case


@router.delete("/use-cases/{usecase_id}")
async def delete_ad_hoc_use_case(usecase_id: str):
    """Delete an ad-hoc use-case. Hardcoded use-cases are immutable and cannot be deleted."""
    try:
        deleted = UseCaseService.delete_adhoc_usecase(usecase_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Ad-hoc use-case '{usecase_id}' not found.")
        return {"status": "deleted", "use_case_id": usecase_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- EXPERIMENT RUNNER & METRICS ---

class RunExperimentRequest(BaseModel):
    name: str = "Incident Response Context Optimization"
    use_case_id: Optional[str] = Field(default="sre_incident_response", description="Target use-case ID")
    model: str = "mock-model"
    provider: str = "mock"
    arm_ids: Optional[List[str]] = None


@router.post("/experiments/run", response_model=ExperimentRun)
async def run_experiment(req: RunExperimentRequest, task_id: Optional[str] = Query(None, description="Optional tracked task ID")):
    """Execute a complete Dokimi A/B testing experiment across active context arms."""
    active_variants = [v for v in _VARIANTS_STORE if req.arm_ids is None or v.id in req.arm_ids]
    if not active_variants:
        raise HTTPException(status_code=400, detail="No active variants selected.")

    def progress_callback(step_msg: str, completed: int, total: int, force_pct: Optional[float]):
        if task_id:
            progress_manager.update_step(
                task_id=task_id,
                step_text=step_msg,
                completed_steps=completed,
                total_steps=total,
                force_percent=force_pct
            )

    def cancel_check() -> bool:
        return task_id is not None and progress_manager.is_cancelled(task_id)

    try:
        # Load questions corresponding to target use-case if present
        target_usecase_id = req.use_case_id or "sre_incident_response"
        usecase_questions = UseCaseService.get_questions_for_usecase(target_usecase_id)

        experiment = await DokimiEvaluationEngine.run_experiment(
            name=req.name,
            use_case_id=target_usecase_id,
            variants=active_variants,
            questions=usecase_questions if usecase_questions else None,
            model=req.model,
            provider=req.provider,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        _EXPERIMENTS_STORE[experiment.id] = experiment
        if task_id:
            progress_manager.complete_task(
                task_id=task_id,
                result_data={"experiment_id": experiment.id, "summary": experiment.summary_verdict},
                message=f"Experiment '{experiment.name}' completed successfully."
            )
        return experiment
    except Exception as e:
        if task_id:
            progress_manager.fail_task(task_id=task_id, error_message=str(e))
        raise


@router.get("/experiments", response_model=List[ExperimentRun])
async def get_experiments():
    """List all executed experiments."""
    return list(_EXPERIMENTS_STORE.values())


@router.get("/experiments/{experiment_id}", response_model=ExperimentRun)
async def get_experiment_by_id(experiment_id: str):
    """Get detailed results and metrics for a specific experiment run."""
    if experiment_id not in _EXPERIMENTS_STORE:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return _EXPERIMENTS_STORE[experiment_id]


@router.get("/experiments/{experiment_id}/report")
async def get_experiment_markdown_report(experiment_id: str):
    """Retrieve the generated markdown report for an experiment."""
    if experiment_id not in _EXPERIMENTS_STORE:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    exp = _EXPERIMENTS_STORE[experiment_id]
    return {"markdown": DokimiEvaluationEngine.generate_markdown_report(exp)}


# --- REAL-TIME PROGRESS TRACKING & STREAMING ---

class CreateTaskRequest(BaseModel):
    task_type: str = Field(..., description="Operation type: experiment, model_discovery, batch_inference")
    total_steps: int = Field(default=1, ge=1)
    initial_step: str = Field(default="Initializing task...")


@router.post("/tasks", response_model=TaskProgress)
async def create_tracked_task(req: CreateTaskRequest):
    """Register a new tracked long-running operation."""
    task = progress_manager.create_task(
        task_type=req.task_type,
        total_steps=req.total_steps,
        initial_step=req.initial_step
    )
    return task


@router.get("/tasks/{task_id}", response_model=TaskProgress)
async def get_task_progress(task_id: str):
    """Retrieve current task progress snapshot."""
    task = progress_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_tracked_task(task_id: str):
    """Request cancellation of an active task."""
    cancelled = progress_manager.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found or already completed.")
    return {"status": "cancelled", "task_id": task_id}


@router.get("/tasks/{task_id}/events")
async def stream_task_events(task_id: str):
    """Stream real-time progress updates for a task via Server-Sent Events (SSE)."""
    task = progress_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    
    return StreamingResponse(
        progress_manager.stream_task_sse(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# --- INTERACTIVE VARIANT CHAT ---

@router.post("/chat", response_model=ChatResponse)
async def chat_with_variant(req: ChatRequest):
    """Send an interactive prompt to a specific context arm variant to observe behavior."""
    variant = next((v for v in _VARIANTS_STORE if v.id == req.variant_id), None)
    if not variant:
        raise HTTPException(status_code=404, detail=f"Variant '{req.variant_id}' not found.")

    res = await LLMService.generate_response(
        prompt=req.message,
        system_prompt=variant.system_prompt,
        context=variant.context_content,
        provider=req.provider or settings.DEFAULT_LLM_PROVIDER,
        model=req.model or settings.DEFAULT_LLM_MODEL,
    )

    return ChatResponse(
        variant_id=variant.id,
        variant_name=variant.name,
        arm_type=variant.arm_type.value,
        answer=res["text"],
        latency_ms=res["latency_ms"],
        token_count=res["token_count"],
        context_used=variant.context_content or "(No injected context - baseline / raw prompt)",
    )
