"""Domain data models and schemas for A/B testing."""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class ContextArmType(str, Enum):
    """Types of context arms supported by Dokimi."""
    BASELINE = "baseline"
    PROFILE = "profile"
    DOCS = "docs"
    SKILL = "skill"
    MCP = "mcp"


class VariantConfig(BaseModel):
    """Configuration for a specific context arm / variant."""
    id: str = Field(..., description="Unique variant identifier (e.g. arm_a, baseline, doc_arm)")
    name: str = Field(..., description="Human-readable name")
    arm_type: ContextArmType = Field(..., description="Dokimi context arm type")
    arm_spec: str = Field(..., description="Dokimi spec string (e.g. baseline, profile:path, docs:local:path, skill:path)")
    description: str = Field(default="", description="Description of context payload")
    system_prompt: Optional[str] = Field(default=None, description="System prompt content if profile")
    context_content: Optional[str] = Field(default=None, description="Injected context content or documentation")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional model or retrieval parameters")


class UseCaseSource(str, Enum):
    """Source origin of a use-case."""
    HARDCODED = "hardcoded"
    ADHOC = "adhoc"


class UseCaseScenario(BaseModel):
    """Specific scenario / test prompt within a use-case."""
    id: str = Field(..., description="Scenario ID (e.g. scn_1, q1)")
    prompt: str = Field(..., description="The user query or scenario prompt to evaluate")
    expected_topics: List[str] = Field(default_factory=list, description="Ground truth key topics or expected outputs")
    category: str = Field(default="general", description="Scenario domain or category tag")


class UseCase(BaseModel):
    """Standardized schema for both hardcoded and ad-hoc use-cases."""
    id: str = Field(..., description="Unique use-case ID")
    name: str = Field(..., description="Human-readable title of the use-case")
    description: str = Field(default="", description="Detailed purpose and scope of the use-case")
    source: UseCaseSource = Field(default=UseCaseSource.ADHOC, description="hardcoded vs adhoc")
    is_mutable: bool = Field(default=True, description="Whether this use-case can be edited or deleted")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Input parameters, model settings, or thresholds")
    expected_outputs: List[str] = Field(default_factory=list, description="Global success criteria or key expected behaviors")
    scenarios: List[UseCaseScenario] = Field(default_factory=list, description="Test scenarios / questions evaluated by Dokimi")
    custom_variants: Optional[List[VariantConfig]] = Field(default=None, description="Optional custom context arms for this use-case")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuestionItem(BaseModel):
    """Evaluation question schema compliant with Dokimi questions.v2."""
    id: str = Field(..., description="Unique question ID")
    question: str = Field(..., description="The user query or prompt")
    expected_topics: List[str] = Field(default_factory=list, description="Ground truth key topics or assertions")
    context_hints: Optional[str] = Field(default=None, description="Reference context for evaluation")
    category: str = Field(default="general", description="Scenario or category tag")
    use_case_id: Optional[str] = Field(default="sre_incident_response", description="Associated use-case ID")


class EvaluationMetric(BaseModel):
    """Performance metrics for an individual variant."""
    mean_score: float = Field(default=0.0, description="Average quality score (0.0 to 1.0)")
    p_value: Optional[float] = Field(default=None, description="P-value against baseline from paired t-test")
    stat_significant: bool = Field(default=False, description="Whether improvement is statistically significant (p < 0.05)")
    accuracy_score: float = Field(default=0.0, description="Factual accuracy / grounding score")
    completeness_score: float = Field(default=0.0, description="Completeness of expected topics")
    conciseness_score: float = Field(default=0.0, description="Efficiency and conciseness score")
    latency_ms: float = Field(default=0.0, description="Average response latency in milliseconds")
    token_usage: int = Field(default=0, description="Total tokens consumed")
    novel_atoms_added: int = Field(default=0, description="Novel facts added to agent knowledge")
    redundant_atoms: int = Field(default=0, description="Redundant facts already known by baseline model")


class ArmResult(BaseModel):
    """Result for a single arm on a single question."""
    question_id: str
    question: str
    arm_name: str
    answer: str
    score: float
    accuracy: float
    completeness: float
    conciseness: float
    latency_ms: float
    token_count: int
    judge_reasoning: str


class ExperimentRun(BaseModel):
    """Complete evaluation run across multiple arms."""
    id: str = Field(..., description="Experiment run ID")
    name: str = Field(..., description="Experiment title")
    use_case_id: Optional[str] = Field(default=None, description="Linked use-case ID")
    product_name: str = Field(default="IncidentCopilot", description="Product or domain name")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="completed", description="pending, running, completed, failed")
    model: str = Field(default="mock-model")
    provider: str = Field(default="mock")
    baseline_arm: str = Field(default="baseline")
    arms: List[str] = Field(default_factory=list)
    variants: List[VariantConfig] = Field(default_factory=list)
    metrics_by_arm: Dict[str, EvaluationMetric] = Field(default_factory=dict)
    detailed_results: List[ArmResult] = Field(default_factory=list)
    dokimi_scorecard_path: Optional[str] = None
    summary_verdict: Optional[str] = None


class ChatRequest(BaseModel):
    """Interactive chat request to test an agent variant."""
    variant_id: str
    message: str
    model: Optional[str] = None
    provider: Optional[str] = None


class ChatResponse(BaseModel):
    """Interactive chat response with execution telemetry."""
    variant_id: str
    variant_name: str
    arm_type: str
    answer: str
    latency_ms: float
    token_count: int
    context_used: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LocalModelInfo(BaseModel):
    """Normalized metadata for a local LLM model (Ollama / llama.cpp)."""
    id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Provider backend (ollama or llamacpp)")
    digest: Optional[str] = Field(default=None, description="Model digest hash if provided")
    size_bytes: Optional[int] = Field(default=None, description="Size in bytes")
    size_gb: Optional[float] = Field(default=None, description="Size in gigabytes (GB)")
    size_human: Optional[str] = Field(default=None, description="Human-readable size (e.g. 4.2 GB)")
    parameter_count: Optional[str] = Field(default=None, description="Model parameter count (e.g. 7B, 8B)")
    quantization_format: Optional[str] = Field(default=None, description="Quantization level (e.g. Q4_K_M, Q8_0, FP16)")
    last_accessed: Optional[str] = Field(default=None, description="Last accessed or modified timestamp")
    status: str = Field(default="available", description="Model status: available, loaded, or offline")


class ModelDiscoveryResponse(BaseModel):
    """Response containing discovered models and backend connection status."""
    provider: str = Field(..., description="Inference engine provider")
    endpoint_url: str = Field(..., description="Target API endpoint queried")
    is_connected: bool = Field(..., description="Whether backend connection succeeded")
    models: List[LocalModelInfo] = Field(default_factory=list, description="List of discovered models")
    total_models: int = Field(default=0, description="Total models found")
    status_message: str = Field(default="OK", description="User-facing status or error message")


class ModelSelectionEvent(BaseModel):
    """Audit log entry for active model selection in Dokimi evaluation session."""
    provider: str = Field(..., description="Provider name")
    model_id: str = Field(..., description="Selected model identifier")
    previous_model: Optional[str] = Field(default=None, description="Previous model identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = Field(default="default_session", description="Session context ID")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskProgress(BaseModel):
    """Real-time progress state for long-running operations."""
    task_id: str
    task_type: str = Field(..., description="e.g. experiment, model_discovery, batch_inference")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    percent: float = Field(default=0.0, ge=0.0, le=100.0)
    current_step: str = Field(default="")
    total_steps: int = Field(default=1)
    completed_steps: int = Field(default=0)
    elapsed_seconds: float = Field(default=0.0)
    estimated_remaining_seconds: Optional[float] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    result_data: Optional[Dict[str, Any]] = Field(default=None)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
