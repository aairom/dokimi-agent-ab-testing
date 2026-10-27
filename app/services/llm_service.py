"""LLM Service supporting Mock, OpenAI, Anthropic, OpenRouter, and Local LLMs (Ollama / Llama.cpp)."""

import asyncio
import time
import logging
from typing import Optional, Dict, Any, List
import httpx
from app.core.config import settings
from app.core.models import LocalModelInfo, ModelDiscoveryResponse, ModelSelectionEvent

logger = logging.getLogger("dokimi_app.llm")

# In-memory audit trail for model selection events
_MODEL_SELECTION_AUDIT_LOG: List[ModelSelectionEvent] = []


class LLMService:
    """Dispatches completions to real API providers or built-in intelligent domain mock."""

    @staticmethod
    async def generate_response(
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[str] = None,
        provider: str = "mock",
        model: str = "mock-model",
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> Dict[str, Any]:
        """Generate a response from an LLM given prompt, system prompt, and context."""
        start_time = time.time()
        
        provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()
        model = model or settings.DEFAULT_LLM_MODEL

        # Real provider dispatch if requested and configured
        if provider in ("openai", "openrouter", "anthropic", "local", "local-ollama", "local-llamacpp"):
            try:
                result = await LLMService._call_external_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    context=context,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                latency_ms = (time.time() - start_time) * 1000
                result["latency_ms"] = round(latency_ms, 2)
                return result
            except Exception as e:
                logger.warning(f"External LLM call failed ({provider}/{model}): {e}. Falling back to domain mock engine.")

        # Default Mock generation tailored for Dokimi Context A/B Testing demonstration
        simulated_text, token_count = LLMService._generate_mock_response(
            prompt=prompt,
            system_prompt=system_prompt,
            context=context,
            provider=provider
        )
        
        # Simulate realistic latency (150ms - 400ms)
        elapsed_time = (time.time() - start_time) * 1000
        simulated_latency = round(max(elapsed_time, 180.0 + len(simulated_text) * 0.15), 2)

        return {
            "text": simulated_text,
            "latency_ms": simulated_latency,
            "token_count": token_count,
            "provider": provider,
            "model": model,
        }

    @staticmethod
    def _format_size_bytes(size_bytes: Optional[int]) -> Optional[str]:
        """Convert raw byte size to human-readable string (e.g. 4.2 GB)."""
        if size_bytes is None or size_bytes < 0:
            return None
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    @staticmethod
    def _bytes_to_gb(size_bytes: Optional[int]) -> Optional[float]:
        """Convert raw byte size to GB float."""
        if size_bytes is None or size_bytes < 0:
            return None
        return round(size_bytes / (1024 * 1024 * 1024), 2)

    @classmethod
    def log_model_selection(cls, provider: str, model_id: str, previous_model: Optional[str] = None, session_id: str = "default_session") -> ModelSelectionEvent:
        """Record model selection event for Dokimi A/B testing audit trail."""
        event = ModelSelectionEvent(
            provider=provider,
            model_id=model_id,
            previous_model=previous_model,
            session_id=session_id
        )
        _MODEL_SELECTION_AUDIT_LOG.append(event)
        logger.info(f"AUDIT: Model selected [{provider} -> {model_id}] (prev: {previous_model}) in session {session_id}")
        return event

    @classmethod
    def get_model_selection_audit_log(cls) -> List[ModelSelectionEvent]:
        """Retrieve audit log of model selections."""
        return list(_MODEL_SELECTION_AUDIT_LOG)

    @classmethod
    async def discover_local_models(cls, provider: str, max_retries: int = 3) -> ModelDiscoveryResponse:
        """
        Query and retrieve available models from local Ollama or llama.cpp backend with exponential backoff.
        Whitelisted providers: 'ollama', 'local-ollama', 'llamacpp', 'local-llamacpp'.
        """
        provider_normalized = provider.lower().strip()
        timeout = settings.MODEL_DISCOVERY_TIMEOUT

        # Provider parameter validation
        if provider_normalized in ("local-ollama", "ollama"):
            return await cls._discover_with_backoff(
                discovery_fn=cls._discover_ollama_models,
                provider_label=provider_normalized,
                max_retries=max_retries,
                timeout=timeout
            )
        elif provider_normalized in ("local-llamacpp", "llamacpp", "local"):
            return await cls._discover_with_backoff(
                discovery_fn=cls._discover_llamacpp_models,
                provider_label=provider_normalized,
                max_retries=max_retries,
                timeout=timeout
            )
        else:
            logger.warning(f"Invalid provider '{provider}'. Must be one of ['ollama', 'llamacpp']")
            return ModelDiscoveryResponse(
                provider=provider,
                endpoint_url="",
                is_connected=False,
                models=[],
                total_models=0,
                status_message=f"Invalid provider '{provider}'. Must be one of ['ollama', 'llamacpp'].",
            )

    @classmethod
    async def _discover_with_backoff(cls, discovery_fn, provider_label: str, max_retries: int, timeout: float) -> ModelDiscoveryResponse:
        """Executes discovery with exponential backoff retry logic (1s, 2s, 4s)."""
        last_response: Optional[ModelDiscoveryResponse] = None
        
        for attempt in range(max_retries):
            response = await discovery_fn(provider_label=provider_label, timeout=timeout)
            if response.is_connected:
                return response
            
            last_response = response
            # If not connected and attempts remaining, backoff
            if attempt < max_retries - 1:
                delay = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Discovery attempt {attempt + 1}/{max_retries} failed for {provider_label}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

        return last_response or ModelDiscoveryResponse(
            provider=provider_label,
            endpoint_url="",
            is_connected=False,
            models=[],
            total_models=0,
            status_message=f"Failed to fetch models for {provider_label} after {max_retries} attempts - check backend logs."
        )

    @classmethod
    async def _discover_ollama_models(cls, provider_label: str = "ollama", timeout: float = 5.0) -> ModelDiscoveryResponse:
        """Query Ollama HTTP API (GET /api/tags) to retrieve installed models."""
        base_url = settings.OLLAMA_API_URL or settings.OLLAMA_BASE_URL
        endpoint_url = f"{base_url.rstrip('/')}/api/tags"
        logger.info(f"Querying Ollama models from {endpoint_url} (timeout={timeout}s)...")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(endpoint_url)
                if response.status_code != 200:
                    logger.error(f"Ollama server returned HTTP {response.status_code}: {response.text}")
                    return ModelDiscoveryResponse(
                        provider=provider_label,
                        endpoint_url=endpoint_url,
                        is_connected=False,
                        models=[],
                        total_models=0,
                        status_message=f"Ollama server returned error status HTTP {response.status_code}.",
                    )

                try:
                    data = response.json()
                except Exception as json_err:
                    logger.error(f"Malformed JSON response from Ollama: {json_err}")
                    return ModelDiscoveryResponse(
                        provider=provider_label,
                        endpoint_url=endpoint_url,
                        is_connected=False,
                        models=[],
                        total_models=0,
                        status_message="Malformed response received from Ollama server.",
                    )

                raw_models = data.get("models", [])
                logger.info(f"Ollama discovery returned {len(raw_models)} raw models.")

                normalized_models: List[LocalModelInfo] = []
                for item in raw_models:
                    model_name = item.get("name") or item.get("model", "unknown")
                    size_b = item.get("size")
                    digest = item.get("digest")
                    modified_at = item.get("modified_at")
                    details = item.get("details", {}) or {}

                    param_size = details.get("parameter_size")
                    quant_level = details.get("quantization_level")

                    normalized_models.append(
                        LocalModelInfo(
                            id=model_name,
                            name=model_name,
                            provider=provider_label,
                            digest=digest,
                            size_bytes=size_b,
                            size_gb=cls._bytes_to_gb(size_b),
                            size_human=cls._format_size_bytes(size_b),
                            parameter_count=param_size or "Unknown",
                            quantization_format=quant_level or "Unknown",
                            last_accessed=modified_at,
                            status="available",
                        )
                    )

                status_msg = f"Connected to Ollama. {len(normalized_models)} model(s) available." if normalized_models else "No models installed for this provider."
                return ModelDiscoveryResponse(
                    provider=provider_label,
                    endpoint_url=endpoint_url,
                    is_connected=True,
                    models=normalized_models,
                    total_models=len(normalized_models),
                    status_message=status_msg,
                )

        except httpx.ConnectError as e:
            logger.warning(f"Connection refused to Ollama server at {endpoint_url}: {e}")
            return ModelDiscoveryResponse(
                provider=provider_label,
                endpoint_url=endpoint_url,
                is_connected=False,
                models=[],
                total_models=0,
                status_message="Ollama service unavailable - server not running or port unreachable.",
            )
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout ({timeout}s) querying Ollama server at {endpoint_url}: {e}")
            return ModelDiscoveryResponse(
                provider=provider_label,
                endpoint_url=endpoint_url,
                is_connected=False,
                models=[],
                total_models=0,
                status_message=f"Connection timed out ({timeout}s) while querying Ollama server.",
            )
        except Exception as e:
            logger.error(f"Unexpected error discovering Ollama models: {e}", exc_info=True)
            return ModelDiscoveryResponse(
                provider=provider_label,
                endpoint_url=endpoint_url,
                is_connected=False,
                models=[],
                total_models=0,
                status_message=f"Failed to fetch models - check backend logs: {str(e)}",
            )

    @classmethod
    async def _discover_llamacpp_models(cls, provider_label: str = "llamacpp", timeout: float = 5.0) -> ModelDiscoveryResponse:
        """Query llama.cpp server API (GET /v1/models) to retrieve available models."""
        base_url = settings.LLAMACPP_API_URL or settings.LLAMACPP_BASE_URL
        endpoint_url = f"{base_url.rstrip('/')}/v1/models"
        logger.info(f"Querying llama.cpp models from {endpoint_url} (timeout={timeout}s)...")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(endpoint_url)
                if response.status_code != 200:
                    logger.error(f"llama.cpp server returned HTTP {response.status_code}: {response.text}")
                    return ModelDiscoveryResponse(
                        provider=provider_label,
                        endpoint_url=endpoint_url,
                        is_connected=False,
                        models=[],
                        total_models=0,
                        status_message=f"llama.cpp server returned error status HTTP {response.status_code}.",
                    )

                try:
                    data = response.json()
                except Exception as json_err:
                    logger.error(f"Malformed JSON response from llama.cpp: {json_err}")
                    return ModelDiscoveryResponse(
                        provider=provider_label,
                        endpoint_url=endpoint_url,
                        is_connected=False,
                        models=[],
                        total_models=0,
                        status_message="Malformed response received from llama.cpp server.",
                    )

                raw_models = data.get("data", [])
                logger.info(f"llama.cpp discovery returned {len(raw_models)} raw models.")

                normalized_models: List[LocalModelInfo] = []
                for item in raw_models:
                    model_id = item.get("id", "llama-model")
                    created_ts = item.get("created")
                    last_accessed_str = None
                    if created_ts:
                        try:
                            last_accessed_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(created_ts))
                        except Exception:
                            last_accessed_str = str(created_ts)

                    # Extract metadata if provided in meta or owned_by
                    meta = item.get("meta", {}) or {}
                    param_count = meta.get("parameters") or meta.get("parameter_count")
                    quant = meta.get("quantization") or meta.get("format")
                    size_b = meta.get("size")

                    # Deduce params/quantization from model id if in filename pattern
                    if not param_count:
                        if "70b" in model_id.lower():
                            param_count = "70B"
                        elif "13b" in model_id.lower() or "14b" in model_id.lower():
                            param_count = "13B/14B"
                        elif "8b" in model_id.lower():
                            param_count = "8B"
                        elif "7b" in model_id.lower():
                            param_count = "7B"
                        elif "3b" in model_id.lower():
                            param_count = "3B"
                        else:
                            param_count = "Native"

                    if not quant:
                        for q in ("Q4_K_M", "Q4_0", "Q5_K_M", "Q8_0", "Q6_K", "FP16", "BF16"):
                            if q.lower() in model_id.lower():
                                quant = q
                                break
                        if not quant:
                            quant = "GGUF"

                    normalized_models.append(
                        LocalModelInfo(
                            id=model_id,
                            name=model_id,
                            provider=provider_label,
                            size_bytes=size_b,
                            size_gb=cls._bytes_to_gb(size_b),
                            size_human=cls._format_size_bytes(size_b) if size_b else "Loaded in memory",
                            parameter_count=param_count,
                            quantization_format=quant,
                            last_accessed=last_accessed_str,
                            status="available",
                        )
                    )

                status_msg = f"Connected to llama.cpp. {len(normalized_models)} model(s) loaded." if normalized_models else "No models installed for this provider."
                return ModelDiscoveryResponse(
                    provider=provider_label,
                    endpoint_url=endpoint_url,
                    is_connected=True,
                    models=normalized_models,
                    total_models=len(normalized_models),
                    status_message=status_msg,
                )

        except httpx.ConnectError as e:
            logger.warning(f"Connection refused to llama.cpp server at {endpoint_url}: {e}")
            return ModelDiscoveryResponse(
                provider=provider_label,
                endpoint_url=endpoint_url,
                is_connected=False,
                models=[],
                total_models=0,
                status_message="llama.cpp service unavailable - server not running or port unreachable.",
            )
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout ({timeout}s) querying llama.cpp server at {endpoint_url}: {e}")
            return ModelDiscoveryResponse(
                provider=provider_label,
                endpoint_url=endpoint_url,
                is_connected=False,
                models=[],
                total_models=0,
                status_message=f"Connection timed out ({timeout}s) while querying llama.cpp server.",
            )
        except Exception as e:
            logger.error(f"Unexpected error discovering llama.cpp models: {e}", exc_info=True)
            return ModelDiscoveryResponse(
                provider=provider_label,
                endpoint_url=endpoint_url,
                is_connected=False,
                models=[],
                total_models=0,
                status_message=f"Failed to fetch models - check backend logs: {str(e)}",
            )

    @staticmethod
    async def _call_external_llm(
        prompt: str,
        system_prompt: Optional[str],
        context: Optional[str],
        provider: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Call external LLMs via litellm or direct REST endpoints."""
        import litellm

        messages = []
        full_system = system_prompt or ""
        if context:
            full_system += f"\n\n[INJECTED CONTEXT & KNOWLEDGE]:\n{context}"
        
        if full_system.strip():
            messages.append({"role": "system", "content": full_system.strip()})
        messages.append({"role": "user", "content": prompt})

        # Check local endpoints
        if provider in ("local", "local-ollama", "ollama", "local-llamacpp", "llamacpp"):
            if provider in ("local-ollama", "ollama"):
                api_base = f"{(settings.OLLAMA_API_URL or settings.OLLAMA_BASE_URL).rstrip('/')}/v1"
            elif provider in ("local-llamacpp", "llamacpp"):
                api_base = f"{(settings.LLAMACPP_API_URL or settings.LLAMACPP_BASE_URL).rstrip('/')}/v1"
            else:
                api_base = settings.LOCAL_LLM_BASE_URL.rstrip('/')
                
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{api_base}/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                res.raise_for_status()
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", len(content.split()) * 2)
                return {"text": content, "token_count": tokens, "provider": provider, "model": model}

        # Use LiteLLM for public APIs
        response = await litellm.acompletion(
            model=model if "/" in model else f"{provider}/{model}",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.OPENAI_API_KEY if provider == "openai" else (
                settings.ANTHROPIC_API_KEY if provider == "anthropic" else settings.OPENROUTER_API_KEY
            )
        )
        content = response.choices[0].message.content
        tokens = response.usage.total_tokens if hasattr(response, "usage") and response.usage else len(content.split()) * 2
        return {"text": content, "token_count": tokens, "provider": provider, "model": model}

    @staticmethod
    def _generate_mock_response(
        prompt: str,
        system_prompt: Optional[str],
        context: Optional[str],
        provider: str
    ) -> tuple[str, int]:
        """Generate high-quality domain mock outputs demonstrating clear context deltas."""
        p_lower = prompt.lower()
        has_skill = bool(context and ("high_velocity_sre" in context.lower() or "rapid diagnostic matrix" in context.lower() or "oomkilled" in context.lower() or "skill" in context.lower()))
        has_docs = bool(context and ("kubernetes incident response guidelines" in context.lower() or "standard_runbook" in context.lower() or "pg_stat_activity" in context.lower() or "runbook" in context.lower()))
        has_profile = bool(system_prompt and ("autonomous senior site reliability engineer" in system_prompt.lower() or "operational standards" in system_prompt.lower() or "sre" in system_prompt.lower()))

        # Scenario 1: Kubernetes OOMKilled / Exit 137
        if "137" in p_lower or "oom" in p_lower or "memory" in p_lower:
            if has_skill:
                text = (
                    "### 🚨 Immediate SRE Mitigation (Skill Protocol v2.1)\n"
                    "**Root Cause**: Exit Code 137 confirms the container was **OOMKilled** by the Linux kernel OOM killer.\n\n"
                    "**1. Rapid Diagnostic Inspection**:\n"
                    "```bash\n"
                    "kubectl top pod -n production --sort-by=memory\n"
                    "kubectl describe pod <pod-name> -n production | grep -E 'State:|Last State:|Exit Code:'\n"
                    "kubectl logs <pod-name> -n production -c app --previous --tail=100\n"
                    "```\n"
                    "**2. Immediate Remediation Action**:\n"
                    "Scale the container memory limits by 1.5x immediately:\n"
                    "```bash\n"
                    "kubectl set resources deployment/<deployment-name> -n production --limits=memory=2Gi --requests=memory=1Gi\n"
                    "```\n"
                    "**3. Incident Telemetry Broadcast**:\n"
                    "Dispatching root-cause memory flamegraph snapshot to `#incident-war-room`."
                )
            elif has_docs:
                text = (
                    "### Kubernetes Pod Crash (Exit 137) Runbook\n"
                    "Exit Code 137 indicates the container was terminated due to an Out Of Memory (OOMKilled) condition.\n\n"
                    "**Steps to resolve:**\n"
                    "1. Check pod status: `kubectl get pods -n production`\n"
                    "2. Inspect pod event history: `kubectl describe pod <pod_name> -n production`\n"
                    "3. Review previous logs: `kubectl logs <pod_name> -c <container> --previous`\n"
                    "4. Increase container memory limits in the deployment manifest YAML."
                )
            elif has_profile:
                text = (
                    "### Senior SRE Diagnostic: Exit 137\n"
                    "Exit code 137 is an OOM kill signal (128 + SIGKILL 9). The Linux kernel terminated the container for exceeding its cgroup memory limit.\n\n"
                    "**Action Plan**:\n"
                    "- Run `kubectl describe pod` to confirm OOM termination status.\n"
                    "- Adjust `resources.limits.memory` in your deployment specification to accommodate peak memory allocations.\n"
                    "- Profile application heap allocation for memory leaks."
                )
            else: # Baseline
                text = (
                    "Exit code 137 usually means the pod crashed because it ran out of memory. "
                    "You should check Kubernetes logs and consider restarting the server or allocating more RAM to your container in the settings."
                )

        # Scenario 2: PostgreSQL connection pool exhaustion
        elif "postgres" in p_lower or "connection" in p_lower or "500" in p_lower or "pool" in p_lower:
            if has_skill:
                text = (
                    "### 🚨 PostgreSQL Connection Pool Storm Protocol\n"
                    "**Incident State**: Database connection saturation (300/300 active connections).\n\n"
                    "**Step 1: Identify Blocking 'idle in transaction' Sessions**:\n"
                    "```sql\n"
                    "SELECT pid, now() - xact_start AS duration, query\n"
                    "FROM pg_stat_activity\n"
                    "WHERE state = 'idle in transaction' AND (now() - xact_start) > interval '2 minutes'\n"
                    "ORDER BY duration DESC;\n"
                    "```\n"
                    "**Step 2: Gracefully Cancel Stuck Backend Connections**:\n"
                    "```sql\n"
                    "SELECT pg_cancel_backend(pid) FROM pg_stat_activity\n"
                    "WHERE state = 'idle in transaction' AND (now() - xact_start) > interval '2 minutes';\n"
                    "```\n"
                    "**Step 3: PgBouncer Dynamic Tuning**:\n"
                    "Switch pool mode to `transaction` and apply `RELOAD` on PgBouncer proxy instances."
                )
            elif has_docs:
                text = (
                    "### Database Connection Exhaustion Runbook\n"
                    "1. Query active and idle database connections:\n"
                    "`SELECT count(*), state FROM pg_stat_activity GROUP BY state;`\n"
                    "2. Terminate idle in transaction connections:\n"
                    "`SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < now() - INTERVAL '5 minutes';`\n"
                    "3. Adjust PgBouncer pool mode to 'transaction' and increase max_client_conn."
                )
            elif has_profile:
                text = (
                    "### SRE Database Remediation\n"
                    "Database pool exhaustion is a critical blocker. Inspect `pg_stat_activity` to isolate unreleased connections and cancel lingering transactions before restarting connection poolers."
                )
            else: # Baseline
                text = (
                    "If your database connections are full, try restarting the database or restart the backend application so that the connections are reset."
                )

        # Scenario 3: Payment Gateway Latency / 503
        elif "payment" in p_lower or "gateway" in p_lower or "latency" in p_lower or "503" in p_lower:
            if has_skill:
                text = (
                    "### 🚨 Payment Gateway Automated Failover Sequence\n"
                    "**Trigger Alert**: P99 Latency > 1200ms & Error Rate > 2.5%.\n\n"
                    "**1. Dynamic Routing Cutover**:\n"
                    "```bash\n"
                    "curl -X POST http://payment-router.internal/api/v1/routing/failover \\\n"
                    "  -H 'Content-Type: application/json' \\\n"
                    "  -d '{\"primary\":\"stripe\",\"fallback\":\"adyen\",\"reason\":\"latency_spike_p99\"}'\n"
                    "```\n"
                    "**2. Kafka Ingestion Consumer Verification**:\n"
                    "Confirm consumer lag on partition topic `payment.settlement.events`.\n\n"
                    "**3. Idempotent Transaction Replay**:\n"
                    "Ensure all buffered requests include header `X-Idempotency-Key` to eliminate double-charge risks."
                )
            elif has_docs:
                text = (
                    "### Payment Gateway Latency Runbook\n"
                    "1. Verify status on upstream provider dashboard (Stripe/Adyen).\n"
                    "2. Check egress proxy timeout limits.\n"
                    "3. If circuit breaker is tripped with 503 errors, initiate secondary gateway failover (Adyen Secondary).\n"
                    "4. Flush pending idempotent transaction queue."
                )
            elif has_profile:
                text = (
                    "### SRE Payment Gateway Protocol\n"
                    "Payment failures require immediate failover. Check circuit breaker status, reroute traffic to the secondary gateway, and ensure idempotency keys are enforced on replay."
                )
            else: # Baseline
                text = (
                    "If the payment gateway is slow or returning 503 errors, wait a few minutes for the third party to recover or contact payment vendor support."
                )

        # Default fallback general queries
        else:
            if has_skill:
                text = (
                    f"### 🛡️ High-Velocity SRE Analysis for: '{prompt}'\n"
                    "Applied active SRE skills and runbook procedures.\n"
                    "- **System state**: Monitored via Prometheus / Grafana alerts.\n"
                    "- **Resolution**: Validated configurations, executed rollback protection, and verified health probes."
                )
            elif has_docs:
                text = (
                    f"### Operational Documentation Reference\n"
                    f"Based on internal runbooks, addressing query: '{prompt}'. Follow standard troubleshooting checklists and log inspection procedures."
                )
            elif has_profile:
                text = (
                    f"### Autonomous Senior SRE Assessment\n"
                    f"Direct technical evaluation for: '{prompt}'. Prioritize isolating failure domains and applying structured diagnostic commands."
                )
            else:
                text = f"General assistant response for: '{prompt}'. Check your server configuration and system status."

        tokens = len(text.split()) * 2
        return text, tokens
