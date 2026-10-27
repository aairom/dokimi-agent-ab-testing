// Dokimi Agent Context A/B Testing Platform Client

let variantsData = [];
let useCasesData = [];
let activeUseCaseId = "sre_incident_response";
let experimentsData = [];
let activeExperiment = null;
let performanceChart = null;
let radarChart = null;
let localModelsCache = [];
let activeTaskEventSource = null;
let activeTaskId = null;

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    loadUseCases();
    loadVariants();
    loadQuestions();
    loadExperiments();
    setupEventListeners();
    initProviderAndModel();
});

// Tab Management
function initTabs() {
    const tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

            tab.classList.add("active");
            const targetId = tab.getAttribute("data-tab");
            document.getElementById(targetId).classList.add("active");

            if (targetId === "dashboard-tab" && activeExperiment) {
                renderCharts(activeExperiment);
            }
        });
    });
}

// Event Listeners
function setupEventListeners() {
    document.getElementById("btn-run-experiment").addEventListener("click", runExperiment);
    document.getElementById("btn-create-variant-modal").addEventListener("click", () => openVariantModal());
    document.getElementById("form-variant").addEventListener("submit", saveVariant);

    const btnCreateUseCase = document.getElementById("btn-create-usecase-modal");
    if (btnCreateUseCase) {
        btnCreateUseCase.addEventListener("click", () => openUseCaseModal());
    }
    const formUseCase = document.getElementById("form-usecase");
    if (formUseCase) {
        formUseCase.addEventListener("submit", saveAdHocUseCase);
    }

    const selectActiveUc = document.getElementById("select-active-usecase");
    if (selectActiveUc) {
        selectActiveUc.addEventListener("change", (e) => {
            selectUseCase(e.target.value);
        });
    }

    document.getElementById("btn-chat-send").addEventListener("click", sendDualChat);
    document.getElementById("chat-prompt-input").addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendDualChat();
        }
    });

    document.getElementById("preset-queries").addEventListener("change", (e) => {
        if (e.target.value) {
            document.getElementById("chat-prompt-input").value = e.target.value;
        }
    });

    // Provider and Model Discovery Event Listeners
    const providerSelect = document.getElementById("select-exp-provider");
    providerSelect.addEventListener("change", (e) => {
        handleProviderChange(e.target.value);
    });

    const localModelSelect = document.getElementById("select-local-models");
    localModelSelect.addEventListener("change", (e) => {
        handleModelSelection(e.target.value);
    });

    const refreshBtn = document.getElementById("btn-refresh-models");
    refreshBtn.addEventListener("click", () => {
        const currentProvider = document.getElementById("select-exp-provider").value;
        refreshLocalModels(currentProvider, true);
    });

    const cancelTaskBtn = document.getElementById("btn-cancel-task");
    if (cancelTaskBtn) {
        cancelTaskBtn.addEventListener("click", () => {
            if (activeTaskId) {
                cancelCurrentTask(activeTaskId);
            }
        });
    }
}

// Initialize Provider & Model state from localStorage
function initProviderAndModel() {
    const savedProvider = localStorage.getItem("dokimi_selected_provider") || "mock";
    const savedModel = localStorage.getItem("dokimi_selected_model");

    const providerSelect = document.getElementById("select-exp-provider");
    if (providerSelect) {
        providerSelect.value = savedProvider;
        handleProviderChange(savedProvider, savedModel);
    }
}

// Handle switching between Cloud/Mock and Local inference providers
async function handleProviderChange(provider, preferredModel = null) {
    localStorage.setItem("dokimi_selected_provider", provider);

    const textInput = document.getElementById("select-exp-model");
    const localSelect = document.getElementById("select-local-models");
    const refreshBtn = document.getElementById("btn-refresh-models");
    const metaBadge = document.getElementById("model-meta-badge");

    if (provider === "local-ollama" || provider === "local-llamacpp") {
        textInput.style.display = "none";
        localSelect.style.display = "inline-block";
        refreshBtn.style.display = "inline-block";
        metaBadge.style.display = "inline-block";

        await refreshLocalModels(provider, false, preferredModel);
    } else {
        // Fallback to text input for Cloud / Mock providers
        textInput.style.display = "inline-block";
        localSelect.style.display = "none";
        refreshBtn.style.display = "none";
        metaBadge.style.display = "none";

        if (provider === "mock") {
            textInput.value = "mock-model";
        } else if (provider === "openai") {
            textInput.value = preferredModel || "gpt-4o";
        } else if (provider === "anthropic") {
            textInput.value = preferredModel || "claude-3-5-sonnet-20241022";
        }

        updateBackendStatus(true, `${provider.toUpperCase()} Mode Active`, false);
        localStorage.setItem("dokimi_selected_model", textInput.value);
    }
}

// Fetch available models from local backend API
async function refreshLocalModels(provider, showSpinner = false, preferredModel = null) {
    const localSelect = document.getElementById("select-local-models");
    const refreshSpinner = document.getElementById("refresh-spinner");
    const metaBadge = document.getElementById("model-meta-badge");

    if (showSpinner && refreshSpinner) {
        refreshSpinner.classList.add("spinning");
    }

    localSelect.innerHTML = `<option value="">🔍 Querying ${provider} models...</option>`;
    localSelect.disabled = true;

    try {
        const res = await fetch(`/api/models/local?provider=${encodeURIComponent(provider)}`);
        const data = await res.json();

        localSelect.innerHTML = "";
        localSelect.disabled = false;

        if (data.is_connected && data.models && data.models.length > 0) {
            localModelsCache = data.models;

            data.models.forEach(m => {
                const opt = document.createElement("option");
                opt.value = m.id;
                const sizeLabel = m.size_human ? ` (${m.size_human})` : "";
                const paramLabel = m.parameter_count ? ` [${m.parameter_count}]` : "";
                opt.textContent = `${m.name}${paramLabel}${sizeLabel}`;
                localSelect.appendChild(opt);
            });

            // Restore previously selected model or default to first
            const savedModel = preferredModel || localStorage.getItem("dokimi_selected_model");
            const modelExists = data.models.some(m => m.id === savedModel);
            if (modelExists) {
                localSelect.value = savedModel;
            } else {
                localSelect.value = data.models[0].id;
            }

            handleModelSelection(localSelect.value);
            updateBackendStatus(true, `${data.models.length} model(s) available on ${provider}`, false);
        } else if (data.is_connected && (!data.models || data.models.length === 0)) {
            localModelsCache = [];
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = `⚠️ No models installed on ${provider}`;
            localSelect.appendChild(opt);
            metaBadge.textContent = "0 Models Found";
            metaBadge.className = "tag tag-nonsig";
            updateBackendStatus(true, `Connected to ${provider} (No models installed)`, true);
        } else {
            // Connection failure / offline
            localModelsCache = [];
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = `🔴 ${data.status_message || 'Backend Offline'}`;
            localSelect.appendChild(opt);
            metaBadge.textContent = "Server Offline";
            metaBadge.className = "tag tag-nonsig";
            updateBackendStatus(false, data.status_message || `${provider} unreachable`, false);
        }
    } catch (err) {
        console.error("Failed to discover models:", err);
        localSelect.innerHTML = `<option value="">🔴 Connection error: ${err.message}</option>`;
        localSelect.disabled = false;
        metaBadge.textContent = "Connection Error";
        metaBadge.className = "tag tag-nonsig";
        updateBackendStatus(false, `Error connecting to ${provider}`, false);
    } finally {
        if (refreshSpinner) {
            refreshSpinner.classList.remove("spinning");
        }
    }
}

// Update model metadata badge and save choice to localStorage
function handleModelSelection(modelId) {
    if (!modelId) return;
    localStorage.setItem("dokimi_selected_model", modelId);

    const modelInfo = localModelsCache.find(m => m.id === modelId);
    const metaBadge = document.getElementById("model-meta-badge");

    if (modelInfo && metaBadge) {
        metaBadge.style.display = "inline-block";
        metaBadge.className = "tag tag-skill";
        const parts = [];
        if (modelInfo.parameter_count && modelInfo.parameter_count !== "Unknown params") parts.push(modelInfo.parameter_count);
        if (modelInfo.size_human) parts.push(modelInfo.size_human);
        if (modelInfo.quantization_format && modelInfo.quantization_format !== "Unknown quant") parts.push(modelInfo.quantization_format);
        metaBadge.textContent = parts.join(" • ") || "Local Model";
    }
}

// Helper to update header status dot and text
function updateBackendStatus(isOnline, message, isWarning = false) {
    const dot = document.getElementById("backend-status-dot");
    const text = document.getElementById("backend-status-text");
    if (!dot || !text) return;

    dot.className = "status-dot";
    if (!isOnline) {
        dot.classList.add("dot-error");
    } else if (isWarning) {
        dot.classList.add("dot-warning");
    }

    text.textContent = message;
}

// Helper to get active model name from either text input or local dropdown
function getActiveModelName() {
    const provider = document.getElementById("select-exp-provider").value;
    if (provider === "local-ollama" || provider === "local-llamacpp") {
        return document.getElementById("select-local-models").value || "default";
    }
    return document.getElementById("select-exp-model").value || "mock-model";
}

// Fetch Use-Cases (Hardcoded & Ad-Hoc)
async function loadUseCases() {
    try {
        const res = await fetch("/api/use-cases");
        useCasesData = await res.json();
        renderUseCasesTable();
        populateUseCaseSelector();
        if (useCasesData.length > 0) {
            const currentSelected = useCasesData.find(u => u.id === activeUseCaseId) || useCasesData[0];
            selectUseCase(currentSelected.id, false);
        }
    } catch (err) {
        console.error("Failed to load use-cases:", err);
    }
}

function populateUseCaseSelector() {
    const select = document.getElementById("select-active-usecase");
    if (!select) return;
    select.innerHTML = "";
    useCasesData.forEach(uc => {
        const opt = document.createElement("option");
        opt.value = uc.id;
        const srcPrefix = uc.source === "hardcoded_fixture" ? "🔒 [Hardcoded]" : "⚡ [Ad-Hoc]";
        opt.textContent = `${srcPrefix} ${uc.name} (${uc.scenarios.length} scenarios)`;
        select.appendChild(opt);
    });
    select.value = activeUseCaseId;
}

function selectUseCase(ucId, updateDropdown = true) {
    activeUseCaseId = ucId;
    const uc = useCasesData.find(u => u.id === ucId);
    if (!uc) return;

    if (updateDropdown) {
        const select = document.getElementById("select-active-usecase");
        if (select) select.value = ucId;
    }

    const titleEl = document.getElementById("dashboard-usecase-title");
    const badgeEl = document.getElementById("dashboard-usecase-badge");
    const descEl = document.getElementById("dashboard-usecase-desc");

    if (titleEl) titleEl.textContent = uc.name;
    if (badgeEl) {
        if (uc.source === "hardcoded_fixture") {
            badgeEl.textContent = "HARDCODED FIXTURE";
            badgeEl.className = "tag tag-baseline";
        } else {
            badgeEl.textContent = "DYNAMIC AD-HOC";
            badgeEl.className = "tag tag-sig";
        }
    }
    if (descEl) descEl.textContent = uc.description || "Ad-hoc use-case evaluation.";

    // Reload questions matching this use-case for playground & questions tab
    loadQuestions();
}

function renderUseCasesTable() {
    const tbody = document.getElementById("usecases-table-body");
    const countBadge = document.getElementById("usecases-count-badge");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (countBadge) {
        const hardcodedCount = useCasesData.filter(u => u.source === "hardcoded_fixture").length;
        const adhocCount = useCasesData.filter(u => u.source === "adhoc_submission").length;
        countBadge.textContent = `${useCasesData.length} Total (${hardcodedCount} Fixtures, ${adhocCount} Ad-Hoc)`;
    }

    useCasesData.forEach(uc => {
        const tr = document.createElement("tr");
        const isHardcoded = uc.source === "hardcoded";
        const sourceBadge = isHardcoded
            ? `<span class="tag tag-baseline">FIXTURE</span>`
            : `<span class="tag tag-sig">AD-HOC</span>`;

        const paramsStr = Object.entries(uc.parameters || {})
            .map(([k, v]) => `<span class="tag tag-skill" style="font-size: 0.7rem; margin-right: 0.2rem;">${escapeHtml(k)}: ${escapeHtml(String(v))}</span>`)
            .join("") || "—";

        const outputsStr = (uc.expected_outputs || [])
            .map(o => `<li style="font-size: 0.75rem;">${escapeHtml(o)}</li>`)
            .join("");

        const deleteBtn = isHardcoded
            ? `<span style="font-size: 0.75rem; color: var(--cds-text-muted);" title="Hardcoded fixtures cannot be removed">Immutable</span>`
            : `<button class="btn btn-danger-sm" style="padding: 0.2rem 0.4rem; font-size: 0.75rem;" onclick="deleteAdHocUseCase('${uc.id}')">Delete</button>`;

        tr.innerHTML = `
            <td>${sourceBadge}</td>
            <td><strong>${escapeHtml(uc.name)}</strong><br><span style="font-size: 0.75rem; color: var(--cds-text-secondary);">${escapeHtml(uc.description || "")}</span></td>
            <td><code>${escapeHtml(uc.id)}</code></td>
            <td>
                <span class="tag tag-baseline" style="font-size: 0.75rem;">${uc.scenarios.length} scenarios</span>
                <button class="btn btn-secondary" style="padding: 0.15rem 0.4rem; font-size: 0.7rem; margin-left: 0.25rem;" onclick="viewUseCaseScenarios('${uc.id}')">View</button>
            </td>
            <td>${paramsStr}</td>
            <td>${outputsStr ? `<ul style="padding-left: 1rem; margin: 0;">${outputsStr}</ul>` : "—"}</td>
            <td>
                <div style="display: flex; gap: 0.35rem; align-items: center;">
                    <button class="btn" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="selectAndRunUseCase('${uc.id}')">Run Eval</button>
                    ${deleteBtn}
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function viewUseCaseScenarios(ucId) {
    const uc = useCasesData.find(u => u.id === ucId);
    if (!uc) return;

    const card = document.getElementById("usecase-scenarios-card");
    const title = document.getElementById("usecase-detail-title");
    const container = document.getElementById("usecase-scenarios-container");

    title.textContent = `🎯 Scenarios for "${uc.name}" (${uc.scenarios.length})`;
    container.innerHTML = "";

    uc.scenarios.forEach((s, idx) => {
        const sDiv = document.createElement("div");
        sDiv.style.backgroundColor = "var(--cds-layer-02)";
        sDiv.style.padding = "0.75rem";
        sDiv.style.borderRadius = "4px";
        sDiv.style.marginBottom = "0.5rem";

        const topics = (s.expected_topics || [])
            .map(a => `<span class="tag tag-baseline" style="font-size: 0.7rem; margin-right: 0.25rem;">${escapeHtml(a)}</span>`)
            .join("") || "None";

        sDiv.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                <strong>Scenario #${idx + 1}: <code>${escapeHtml(s.id)}</code></strong>
                <span class="tag tag-skill">${escapeHtml(s.category || 'General')}</span>
            </div>
            <div style="font-size: 0.85rem; margin-bottom: 0.35rem; color: var(--cds-text-primary);">${escapeHtml(s.prompt)}</div>
            <div style="font-size: 0.75rem; color: var(--cds-text-secondary);">
                <strong>Expected Topics:</strong> ${topics}
            </div>
        `;
        container.appendChild(sDiv);
    });

    card.style.display = "block";
    card.scrollIntoView({ behavior: "smooth" });
}

function closeUseCaseScenarios() {
    const card = document.getElementById("usecase-scenarios-card");
    if (card) card.style.display = "none";
}

function selectAndRunUseCase(ucId) {
    selectUseCase(ucId);
    const dashboardTab = document.querySelector(".nav-tab[data-tab='dashboard-tab']");
    if (dashboardTab) dashboardTab.click();
    runExperiment();
}

async function deleteAdHocUseCase(ucId) {
    if (!confirm(`Are you sure you want to delete ad-hoc use-case "${ucId}"?`)) return;
    try {
        const res = await fetch(`/api/use-cases/${encodeURIComponent(ucId)}`, { method: "DELETE" });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Delete failed");
        }
        await loadUseCases();
    } catch (err) {
        alert("Error deleting use-case: " + err.message);
    }
}

function openUseCaseModal() {
    const modal = document.getElementById("modal-usecase");
    if (!modal) return;
    document.getElementById("form-usecase").reset();
    const scContainer = document.getElementById("modal-scenario-rows-container");
    scContainer.innerHTML = "";
    addScenarioRow(); // default 1 scenario row
    modal.classList.add("active");
}

function closeUseCaseModal() {
    const modal = document.getElementById("modal-usecase");
    if (modal) modal.classList.remove("active");
}

function addScenarioRow() {
    const container = document.getElementById("modal-scenario-rows-container");
    if (!container) return;

    const rowId = `sc_row_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`;
    const row = document.createElement("div");
    row.id = rowId;
    row.style.display = "flex";
    row.style.gap = "0.5rem";
    row.style.alignItems = "center";
    row.style.background = "var(--cds-layer-02)";
    row.style.padding = "0.4rem 0.6rem";
    row.style.borderRadius = "4px";

    row.innerHTML = `
        <input type="text" class="input-text sc-prompt" placeholder="Scenario test prompt / question..." style="flex: 2; padding: 0.3rem 0.5rem; font-size: 0.8rem;" required>
        <input type="text" class="input-text sc-category" placeholder="Category" value="Performance" style="flex: 1; padding: 0.3rem 0.5rem; font-size: 0.8rem;">
        <input type="text" class="input-text sc-assertions" placeholder="Expected keywords (comma-separated)" style="flex: 2; padding: 0.3rem 0.5rem; font-size: 0.8rem;">
        <button type="button" class="btn btn-secondary" onclick="document.getElementById('${rowId}').remove()" style="padding: 0.2rem 0.4rem; font-size: 0.75rem;">✕</button>
    `;
    container.appendChild(row);
}

async function saveAdHocUseCase(e) {
    e.preventDefault();
    const name = document.getElementById("input-uc-name").value.trim();
    const desc = document.getElementById("input-uc-desc").value.trim();
    const paramsRaw = document.getElementById("input-uc-params").value.trim();
    const outputsRaw = document.getElementById("input-uc-outputs").value.trim();

    let parameters = {};
    if (paramsRaw) {
        try {
            parameters = JSON.parse(paramsRaw);
        } catch (err) {
            alert("Invalid JSON in Parameters field: " + err.message);
            return;
        }
    }

    const expected_outputs = outputsRaw ? outputsRaw.split("\n").map(s => s.trim()).filter(Boolean) : [];

    // Collect scenario rows
    const scenarioRows = document.querySelectorAll("#modal-scenario-rows-container > div");
    const scenarios = [];
    scenarioRows.forEach((row, idx) => {
        const prompt = row.querySelector(".sc-prompt")?.value.trim();
        const category = row.querySelector(".sc-category")?.value.trim() || "General";
        const assertionsRaw = row.querySelector(".sc-assertions")?.value.trim() || "";
        const expected_assertions = assertionsRaw ? assertionsRaw.split(",").map(a => a.trim()).filter(Boolean) : [];

        if (prompt) {
            scenarios.push({
                id: `sc_${idx + 1}`,
                category: category,
                prompt: prompt,
                expected_topics: expected_assertions
            });
        }
    });

    if (scenarios.length === 0) {
        alert("Please add at least one scenario.");
        return;
    }

    const payload = {
        name,
        description: desc,
        parameters,
        expected_outputs,
        scenarios
    };

    try {
        const res = await fetch("/api/use-cases/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Submission failed");
        }

        const newUc = await res.json();
        closeUseCaseModal();
        await loadUseCases();
        selectUseCase(newUc.id);
        alert(`Successfully registered ad-hoc use-case "${newUc.name}"!`);
    } catch (err) {
        alert("Failed to submit use-case: " + err.message);
    }
}

// Fetch Variants
async function loadVariants() {
    try {
        const res = await fetch("/api/variants");
        variantsData = await res.json();
        renderVariantsTable();
        populateChatDropdowns();
    } catch (err) {
        console.error("Failed to load variants:", err);
    }
}

// Fetch Evaluation Questions (Dynamic by selected use-case)
async function loadQuestions() {
    try {
        const url = activeUseCaseId ? `/api/questions?use_case_id=${encodeURIComponent(activeUseCaseId)}` : "/api/questions";
        const res = await fetch(url);
        const questions = await res.json();
        renderQuestionsTable(questions);
        populatePresetQuestions(questions);
    } catch (err) {
        console.error("Failed to load questions:", err);
    }
}

// Fetch Experiments
async function loadExperiments() {
    try {
        const res = await fetch("/api/experiments");
        experimentsData = await res.json();
        renderExperimentsList();
        if (experimentsData.length > 0) {
            selectExperiment(experimentsData[experimentsData.length - 1].id);
        } else {
            // Auto trigger initial demo experiment
            runExperiment();
        }
    } catch (err) {
        console.error("Failed to load experiments:", err);
    }
}

// Render Variants Table
function renderVariantsTable() {
    const tbody = document.getElementById("variants-table-body");
    tbody.innerHTML = "";

    variantsData.forEach(v => {
        const tr = document.createElement("tr");
        const armClass = `tag-${v.arm_type}`;
        tr.innerHTML = `
            <td><strong>${escapeHtml(v.name)}</strong></td>
            <td><span class="tag ${armClass}">${v.arm_type.toUpperCase()}</span></td>
            <td><code>${escapeHtml(v.arm_spec)}</code></td>
            <td>${escapeHtml(v.description || "—")}</td>
            <td>
                <button class="btn btn-secondary" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="editVariant('${v.id}')">View</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Render Questions
function renderQuestionsTable(questions) {
    const tbody = document.getElementById("questions-table-body");
    tbody.innerHTML = "";

    questions.forEach(q => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><code>${q.id}</code></td>
            <td><strong>${escapeHtml(q.question)}</strong></td>
            <td><span class="tag tag-baseline">${q.category}</span></td>
            <td>
                <ul style="padding-left: 1.2rem; font-size: 0.8rem; color: var(--cds-text-secondary);">
                    ${q.expected_topics.map(t => `<li>${escapeHtml(t)}</li>`).join("")}
                </ul>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function populatePresetQuestions(questions) {
    const select = document.getElementById("preset-queries");
    select.innerHTML = '<option value="">-- Choose an Incident Scenario or type below --</option>';
    questions.forEach(q => {
        const opt = document.createElement("option");
        opt.value = q.question;
        opt.textContent = `[${q.category.toUpperCase()}] ${q.question.substring(0, 75)}...`;
        select.appendChild(opt);
    });
}

// Populate Chat Dropdowns
function populateChatDropdowns() {
    const selA = document.getElementById("select-arm-a");
    const selB = document.getElementById("select-arm-b");

    selA.innerHTML = "";
    selB.innerHTML = "";

    variantsData.forEach((v, idx) => {
        const optA = document.createElement("option");
        optA.value = v.id;
        optA.textContent = v.name;
        if (v.id === "baseline") optA.selected = true;
        selA.appendChild(optA);

        const optB = document.createElement("option");
        optB.value = v.id;
        optB.textContent = v.name;
        if (v.id === "arm_skill" || idx === 1) optB.selected = true;
        selB.appendChild(optB);
    });
}

// Real-time Progress Tracking Lifecycle Functions
function showProgressBar(taskTitle, initialStep = "Starting...") {
    const banner = document.getElementById("global-progress-banner");
    const label = document.getElementById("progress-task-label");
    const stepDesc = document.getElementById("progress-step-desc");
    const fill = document.getElementById("global-progress-fill");
    const pctBadge = document.getElementById("progress-pct-badge");
    const timer = document.getElementById("progress-timer");

    if (banner) {
        banner.style.display = "block";
        label.textContent = taskTitle;
        stepDesc.textContent = initialStep;
        fill.style.width = "0%";
        pctBadge.textContent = "0%";
        timer.textContent = "0s elapsed | calculating...";
    }
}

function updateProgressDisplay(data) {
    const stepDesc = document.getElementById("progress-step-desc");
    const fill = document.getElementById("global-progress-fill");
    const pctBadge = document.getElementById("progress-pct-badge");
    const timer = document.getElementById("progress-timer");

    if (stepDesc && data.current_step) stepDesc.textContent = data.current_step;
    if (fill && typeof data.percent === "number") fill.style.width = `${data.percent}%`;
    if (pctBadge && typeof data.percent === "number") pctBadge.textContent = `${data.percent}%`;

    if (timer) {
        const elapsed = data.elapsed_seconds ? formatSeconds(data.elapsed_seconds) : "0s";
        let remStr = "";
        if (data.estimated_remaining_seconds !== null && data.estimated_remaining_seconds !== undefined && data.estimated_remaining_seconds > 0) {
            remStr = ` | ~${formatSeconds(data.estimated_remaining_seconds)} remaining`;
        } else if (data.percent >= 100) {
            remStr = ` | Complete`;
        }
        timer.textContent = `${elapsed} elapsed${remStr}`;
    }
}

function hideProgressBar(autoDismissMs = 2500) {
    setTimeout(() => {
        const banner = document.getElementById("global-progress-banner");
        if (banner) banner.style.display = "none";
        if (activeTaskEventSource) {
            activeTaskEventSource.close();
            activeTaskEventSource = null;
        }
        activeTaskId = null;
    }, autoDismissMs);
}

function formatSeconds(sec) {
    const s = Math.round(sec);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}m ${rem}s`;
}

async function cancelCurrentTask(taskId) {
    try {
        await fetch(`/api/tasks/${taskId}/cancel`, { method: "POST" });
        const stepDesc = document.getElementById("progress-step-desc");
        if (stepDesc) stepDesc.textContent = "Cancelling task...";
    } catch (err) {
        console.error("Failed to cancel task:", err);
    }
}

// Run A/B Test Experiment with Real-time SSE Progress Streaming
async function runExperiment() {
    const runBtn = document.getElementById("btn-run-experiment");
    const originalText = runBtn.innerHTML;
    runBtn.innerHTML = `<span>⏳ Evaluating Dokimi A/B Context Arms...</span>`;
    runBtn.disabled = true;

    try {
        const activeProvider = document.getElementById("select-exp-provider").value || "mock";
        const activeModel = getActiveModelName();
        const currentUc = useCasesData.find(u => u.id === activeUseCaseId);
        const numScenarios = currentUc?.scenarios?.length || 4;
        const numArms = variantsData.length || 4;
        const totalSteps = numScenarios * numArms;

        // 1. Register tracked task
        const taskRes = await fetch("/api/tasks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                task_type: "experiment",
                total_steps: totalSteps,
                initial_step: `Initializing Dokimi evaluation for "${currentUc?.name || activeUseCaseId}" on ${activeProvider} / ${activeModel}...`
            })
        });
        const taskData = await taskRes.json();
        activeTaskId = taskData.task_id;

        showProgressBar(`Dokimi A/B Context Eval: ${currentUc?.name || activeUseCaseId}`, taskData.current_step);

        // 2. Open SSE stream for live updates
        activeTaskEventSource = new EventSource(`/api/tasks/${activeTaskId}/events`);
        activeTaskEventSource.onmessage = (event) => {
            try {
                const progressData = JSON.parse(event.data);
                updateProgressDisplay(progressData);
                if (progressData.status === "completed" || progressData.status === "failed" || progressData.status === "cancelled") {
                    activeTaskEventSource.close();
                    activeTaskEventSource = null;
                }
            } catch (e) {
                // Heartbeat comment or non-json message
            }
        };

        // 3. Trigger experiment evaluation execution
        const res = await fetch(`/api/experiments/run?task_id=${encodeURIComponent(activeTaskId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: currentUc ? `${currentUc.name} Context Optimization` : "Context Optimization",
                use_case_id: activeUseCaseId,
                model: activeModel,
                provider: activeProvider
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned HTTP ${res.status}`);
        }

        const newExp = await res.json();
        experimentsData.push(newExp);
        renderExperimentsList();
        selectExperiment(newExp.id);
        hideProgressBar(2000);
    } catch (err) {
        alert("Experiment evaluation error: " + err.message);
        hideProgressBar(1000);
    } finally {
        runBtn.innerHTML = originalText;
        runBtn.disabled = false;
    }
}

// Select and Display Experiment
function selectExperiment(expId) {
    const exp = experimentsData.find(e => e.id === expId);
    if (!exp) return;
    activeExperiment = exp;

    // If experiment has associated use_case_id, update active selection
    if (exp.use_case_id && exp.use_case_id !== activeUseCaseId) {
        selectUseCase(exp.use_case_id, true);
    }

    // Update Summary KPI Cards
    const baseMetric = exp.metrics_by_arm[exp.baseline_arm] || { mean_score: 0.5, latency_ms: 200 };
    const armIds = Object.keys(exp.metrics_by_arm);
    const topArmId = armIds.reduce((a, b) => exp.metrics_by_arm[a].mean_score > exp.metrics_by_arm[b].mean_score ? a : b, armIds[0]);
    const topMetric = exp.metrics_by_arm[topArmId];

    const deltaPct = (((topMetric.mean_score - baseMetric.mean_score) / baseMetric.mean_score) * 100).toFixed(1);

    document.getElementById("kpi-top-arm").textContent = topArmId.replace("arm_", "").toUpperCase();
    document.getElementById("kpi-delta-score").textContent = `+${deltaPct}%`;
    document.getElementById("kpi-delta-score").style.color = "var(--cds-support-success)";
    document.getElementById("kpi-p-value").textContent = topMetric.p_value !== null ? `p = ${topMetric.p_value}` : "p < 0.001";
    document.getElementById("kpi-sig-tag").textContent = topMetric.stat_significant ? "SIGNIFICANT (p < 0.05)" : "NOT SIGNIFICANT";
    document.getElementById("kpi-sig-tag").className = `tag ${topMetric.stat_significant ? 'tag-sig' : 'tag-nonsig'}`;
    document.getElementById("kpi-novel-atoms").textContent = `+${topMetric.novel_atoms_added} atoms`;

    document.getElementById("summary-verdict-text").textContent = exp.summary_verdict || "Experiment completed.";

    renderMetricsTable(exp);
    renderCharts(exp);
    renderDetailedResults(exp);
}

// Render Metrics Comparison Table
function renderMetricsTable(exp) {
    const tbody = document.getElementById("exp-metrics-table-body");
    tbody.innerHTML = "";

    const baseScore = exp.metrics_by_arm[exp.baseline_arm]?.mean_score || 0;

    Object.entries(exp.metrics_by_arm).forEach(([armId, m]) => {
        const delta = m.mean_score - baseScore;
        const deltaClass = delta > 0 ? "style='color: var(--cds-support-success); font-weight: 600;'" : (delta < 0 ? "style='color: var(--cds-support-error);'" : "");
        const deltaStr = delta >= 0 ? `+${delta.toFixed(4)}` : delta.toFixed(4);
        const pvalStr = m.p_value !== null ? m.p_value.toFixed(4) : "— (Base)";
        const sigTag = armId === exp.baseline_arm ? `<span class="tag tag-baseline">Baseline</span>` : (m.stat_significant ? `<span class="tag tag-sig">✅ Sig (p<0.05)</span>` : `<span class="tag tag-nonsig">❌ No</span>`);

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong><code>${armId}</code></strong></td>
            <td><strong>${m.mean_score.toFixed(4)}</strong></td>
            <td ${deltaClass}>${deltaStr}</td>
            <td><code>${pvalStr}</code></td>
            <td>${sigTag}</td>
            <td>${(m.accuracy_score * 100).toFixed(0)}%</td>
            <td>${(m.completeness_score * 100).toFixed(0)}%</td>
            <td>+${m.novel_atoms_added}</td>
            <td>${m.latency_ms} ms</td>
        `;
        tbody.appendChild(tr);
    });
}

// Render ECharts Visualizations
function renderCharts(exp) {
    const barElem = document.getElementById("chart-bar-performance");
    const radarElem = document.getElementById("chart-radar-dimensions");
    if (!barElem || !radarElem || !window.echarts) return;

    if (performanceChart) performanceChart.dispose();
    if (radarChart) radarChart.dispose();

    performanceChart = echarts.init(barElem, "dark");
    radarChart = echarts.init(radarElem, "dark");

    const armLabels = Object.keys(exp.metrics_by_arm);
    const meanScores = armLabels.map(k => (exp.metrics_by_arm[k].mean_score * 100).toFixed(1));
    const accuracyScores = armLabels.map(k => (exp.metrics_by_arm[k].accuracy_score * 100).toFixed(1));
    const completenessScores = armLabels.map(k => (exp.metrics_by_arm[k].completeness_score * 100).toFixed(1));

    // Performance Bar Chart
    performanceChart.setOption({
        backgroundColor: "transparent",
        tooltip: { trigger: "axis" },
        legend: { data: ["Overall Score", "Factual Accuracy", "Grounding Completeness"] },
        grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
        xAxis: { type: "category", data: armLabels },
        yAxis: { type: "value", min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
        series: [
            { name: "Overall Score", type: "bar", data: meanScores, itemStyle: { color: "#0f62fe" } },
            { name: "Factual Accuracy", type: "bar", data: accuracyScores, itemStyle: { color: "#42be65" } },
            { name: "Grounding Completeness", type: "bar", data: completenessScores, itemStyle: { color: "#a56eff" } }
        ]
    });

    // Radar Chart
    const radarSeries = armLabels.map(k => {
        const m = exp.metrics_by_arm[k];
        return {
            name: k,
            value: [
                m.mean_score * 100,
                m.accuracy_score * 100,
                m.completeness_score * 100,
                m.conciseness_score * 100,
                Math.min(100, (m.novel_atoms_added / 12) * 100)
            ]
        };
    });

    radarChart.setOption({
        backgroundColor: "transparent",
        tooltip: {},
        legend: { data: armLabels, bottom: 0 },
        radar: {
            indicator: [
                { name: "Overall Score", max: 100 },
                { name: "Accuracy", max: 100 },
                { name: "Completeness", max: 100 },
                { name: "Conciseness", max: 100 },
                { name: "Novelty Impact", max: 100 }
            ],
            axisName: { color: "#c6c6c6" }
        },
        series: [{ type: "radar", data: radarSeries }]
    });

    window.addEventListener("resize", () => {
        performanceChart && performanceChart.resize();
        radarChart && radarChart.resize();
    });
}

// Render Detailed Question Responses
function renderDetailedResults(exp) {
    const container = document.getElementById("detailed-results-container");
    container.innerHTML = "";

    const questionMap = {};
    exp.detailed_results.forEach(res => {
        if (!questionMap[res.question_id]) {
            questionMap[res.question_id] = { question: res.question, results: [] };
        }
        questionMap[res.question_id].results.push(res);
    });

    Object.entries(questionMap).forEach(([qid, data]) => {
        const card = document.createElement("div");
        card.className = "card";
        card.style.marginBottom = "1.25rem";

        let armsHtml = data.results.map(r => `
            <div style="background-color: var(--cds-layer-02); padding: 0.85rem; border-left: 3px solid ${r.score > 0.85 ? 'var(--cds-support-success)' : (r.score > 0.7 ? 'var(--cds-support-info)' : 'var(--cds-support-error)')};">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.4rem;">
                    <strong><code>${r.arm_name}</code></strong>
                    <span class="tag ${r.score > 0.85 ? 'tag-sig' : 'tag-baseline'}">Score: ${(r.score * 100).toFixed(0)}% | Latency: ${r.latency_ms}ms</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--cds-text-muted); margin-bottom: 0.4rem;"><em>Judge reasoning: ${escapeHtml(r.judge_reasoning)}</em></div>
                <div style="font-size: 0.85rem; white-space: pre-wrap; font-family: var(--font-sans); color: var(--cds-text-secondary); max-height: 160px; overflow-y: auto;">${escapeHtml(r.answer)}</div>
            </div>
        `).join("");

        card.innerHTML = `
            <div class="card-title">
                <span><strong>[${qid}]</strong> ${escapeHtml(data.question)}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-top: 0.75rem;">
                ${armsHtml}
            </div>
        `;
        container.appendChild(card);
    });
}

// Render Experiments History List
function renderExperimentsList() {
    const list = document.getElementById("experiments-history-list");
    if (!list) return;
    list.innerHTML = "";

    experimentsData.slice().reverse().forEach(exp => {
        const item = document.createElement("div");
        item.className = `card ${activeExperiment && activeExperiment.id === exp.id ? 'active-exp' : ''}`;
        item.style.cursor = "pointer";
        item.style.padding = "0.75rem";
        item.style.marginBottom = "0.5rem";
        item.innerHTML = `
            <div style="font-weight: 600; font-size: 0.85rem;">${escapeHtml(exp.name)}</div>
            <div style="font-size: 0.75rem; color: var(--cds-text-muted);">ID: ${exp.id} | ${exp.arms.length} arms</div>
        `;
        item.addEventListener("click", () => selectExperiment(exp.id));
        list.appendChild(item);
    });
}

// Dual Variant Chat Playground
async function sendDualChat() {
    const input = document.getElementById("chat-prompt-input");
    const prompt = input.value.trim();
    if (!prompt) return;

    const armAId = document.getElementById("select-arm-a").value;
    const armBId = document.getElementById("select-arm-b").value;

    const msgsA = document.getElementById("chat-messages-a");
    const msgsB = document.getElementById("chat-messages-b");

    // Append User Message to both panes
    appendMessage(msgsA, prompt, "user");
    appendMessage(msgsB, prompt, "user");

    input.value = "";

    const placeholderA = appendMessage(msgsA, "<em>Generating response with " + armAId + "...</em>", "assistant");
    const placeholderB = appendMessage(msgsB, "<em>Generating response with " + armBId + "...</em>", "assistant");

    try {
        const activeProvider = document.getElementById("select-exp-provider").value || "mock";
        const activeModel = getActiveModelName();

        const [resA, resB] = await Promise.all([
            fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    variant_id: armAId,
                    message: prompt,
                    provider: activeProvider,
                    model: activeModel
                })
            }).then(r => r.json()),
            fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    variant_id: armBId,
                    message: prompt,
                    provider: activeProvider,
                    model: activeModel
                })
            }).then(r => r.json())
        ]);

        placeholderA.innerHTML = formatMarkdown(resA.answer) + `<div style="font-size: 0.75rem; color: var(--cds-text-muted); margin-top: 0.4rem;">⚡ Latency: ${resA.latency_ms}ms | Tokens: ${resA.token_count}</div>`;
        placeholderB.innerHTML = formatMarkdown(resB.answer) + `<div style="font-size: 0.75rem; color: var(--cds-text-muted); margin-top: 0.4rem;">⚡ Latency: ${resB.latency_ms}ms | Tokens: ${resB.token_count}</div>`;
    } catch (err) {
        placeholderA.textContent = "Error: " + err;
        placeholderB.textContent = "Error: " + err;
    }
}

function appendMessage(container, html, role) {
    const div = document.createElement("div");
    div.className = `chat-message ${role}`;
    div.innerHTML = html;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

// Modal handling
function openVariantModal(variant = null) {
    const modal = document.getElementById("modal-variant");
    modal.classList.add("active");

    if (variant) {
        document.getElementById("input-variant-id").value = variant.id;
        document.getElementById("input-variant-name").value = variant.name;
        document.getElementById("input-variant-arm-type").value = variant.arm_type;
        document.getElementById("input-variant-spec").value = variant.arm_spec;
        document.getElementById("input-variant-desc").value = variant.description || "";
        document.getElementById("input-variant-system").value = variant.system_prompt || "";
        document.getElementById("input-variant-context").value = variant.context_content || "";
    } else {
        document.getElementById("form-variant").reset();
        document.getElementById("input-variant-id").value = `arm_custom_${Date.now().toString().slice(-4)}`;
    }
}

function closeVariantModal() {
    document.getElementById("modal-variant").classList.remove("active");
}

function editVariant(id) {
    const v = variantsData.find(item => item.id === id);
    if (v) openVariantModal(v);
}

async function saveVariant(e) {
    e.preventDefault();
    const payload = {
        id: document.getElementById("input-variant-id").value,
        name: document.getElementById("input-variant-name").value,
        arm_type: document.getElementById("input-variant-arm-type").value,
        arm_spec: document.getElementById("input-variant-spec").value,
        description: document.getElementById("input-variant-desc").value,
        system_prompt: document.getElementById("input-variant-system").value,
        context_content: document.getElementById("input-variant-context").value,
        parameters: {}
    };

    try {
        await fetch("/api/variants", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        closeVariantModal();
        loadVariants();
    } catch (err) {
        alert("Failed to save variant: " + err);
    }
}

// Utilities
function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    // Replace markdown bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Replace markdown code blocks
    html = html.replace(/```(.*?)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>");
    // Replace inline code
    html = html.replace(/`(.*?)`/g, "<code>$1</code>");
    // Headers
    html = html.replace(/### (.*?)\n/g, "<h4 style='margin: 0.5rem 0 0.25rem 0; color: var(--cds-link-primary);'>$1</h4>");
    return html;
}
