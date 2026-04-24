// --- Session Storage Management ---
const STORAGE_KEY = "ppt_sessions";

function loadAllSessions() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (data) {
      return JSON.parse(data);
    }
  } catch (e) {
    console.error("Failed to load sessions:", e);
  }
  return { activeSessionId: null, sessions: {} };
}

function saveAllSessions(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.error("Failed to save sessions:", e);
  }
}

function generateSessionId() {
  return Math.random().toString(36).substring(2, 15);
}

function createNewSession() {
  const id = generateSessionId();
  const newSession = {
    id: id,
    title: "新会话",
    createdAt: Date.now(),
    state: "INIT",
    messages: [],
    traces: [],
  };

  const data = loadAllSessions();
  data.sessions[id] = newSession;
  data.activeSessionId = id;
  saveAllSessions(data);

  return id;
}

// Initialize session state
let sessionData = loadAllSessions();
let sessionId = sessionData.activeSessionId;

// If no active session exists or the active session data is missing, create a new one.
// Also migrate old 'ppt_session_id' if it exists but no structured data is found.
if (!sessionId || !sessionData.sessions[sessionId]) {
  const oldId = localStorage.getItem("ppt_session_id");
  if (oldId && Object.keys(sessionData.sessions).length === 0) {
    sessionId = oldId;
    sessionData.sessions[sessionId] = {
      id: sessionId,
      title: "历史会话",
      createdAt: Date.now(),
      state: "INIT",
      messages: [],
      traces: [],
    };
    sessionData.activeSessionId = sessionId;
    saveAllSessions(sessionData);
    localStorage.removeItem("ppt_session_id");
  } else {
    sessionId = createNewSession();
    sessionData = loadAllSessions();
  }
}

function getCurrentSession() {
  return sessionData.sessions[sessionId];
}

function saveCurrentSession() {
  sessionData.sessions[sessionId].state = agentState.textContent;
  saveAllSessions(sessionData);
  renderHistorySidebar();
}

function updateSessionTitleIfEmpty(text) {
  const session = getCurrentSession();
  if (session.title === "新会话" || session.title === "历史会话") {
    session.title = text.length > 15 ? text.substring(0, 15) + "..." : text;
    saveCurrentSession();
  }
}

// --- DOM Elements ---
const chatContainer = document.getElementById("chat-container");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const sendIcon = document.getElementById("send-icon");
const stopIcon = document.getElementById("stop-icon");
const traceContainer = document.getElementById("trace-container");
const tokenUsage = document.getElementById("token-usage");
const agentState = document.getElementById("agent-state");
const statusPing = document.getElementById("status-ping");
const statusDot = document.getElementById("status-dot");
const resetBtn = document.getElementById("reset-btn");
const clearTraceBtn = document.getElementById("clear-trace-btn");
const scrollToBottomBtn = document.getElementById("scroll-to-bottom-btn");
const sessionList = document.getElementById("session-list");
const newChatBtn = document.getElementById("new-chat-btn");

document.getElementById("session-id-display").textContent = sessionId;

let currentAssistantMessageDiv = null;
let currentAssistantMarkdown = "";
let currentAiResponse = null;
let isGenerating = false;
let abortController = null;
let planCardElement = null;
let summaryCardElement = null;
const stepCardMap = new Map();
const stepContentMap = new Map();

const STEP_STATUS_ORDER = ["开始", "思考", "计划", "执行", "完成"];
const STEP_STATUS_ICON = {
  start: "🟢",
  thinking: "🤔",
  planning: "🗺️",
  executing: "⚙️",
  completed: "✅",
};
const STEP_STATUS_ICON_FALLBACK = {
  开始: "🟢",
  思考: "🤔",
  计划: "🗺️",
  执行: "⚙️",
  完成: "✅",
};

// Auto-resize textarea
userInput.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = this.scrollHeight + "px";
});

// Submit on Enter (Shift+Enter for new line)
userInput.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!isGenerating && this.value.trim() !== "") {
      chatForm.dispatchEvent(new Event("submit"));
    }
  }
});

function renderHistorySidebar() {
  sessionList.innerHTML = "";
  const sessions = Object.values(sessionData.sessions).sort(
    (a, b) => b.createdAt - a.createdAt,
  );

  sessions.forEach((session) => {
    const li = document.createElement("li");
    const isActive = session.id === sessionId;

    // Ensure li is focusable for keyboard navigation
    li.tabIndex = 0;
    li.className = `group flex justify-between items-center px-3 py-2 rounded-lg cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus-within:bg-gray-100 ${isActive ? "bg-blue-100 text-blue-800" : "hover:bg-gray-100 text-gray-700"}`;

    const titleSpan = document.createElement("span");
    titleSpan.className = "truncate text-sm font-medium";
    titleSpan.textContent = session.title || "新会话";
    titleSpan.title = session.title;

    const deleteBtn = document.createElement("button");
    deleteBtn.className = `text-gray-400 hover:text-red-500 p-1 rounded opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-red-500 transition-opacity ${isGenerating ? "hidden" : ""}`;
    deleteBtn.innerHTML =
      '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>';

    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      if (isGenerating) return;
      deleteSession(session.id);
    };

    li.onclick = () => {
      if (isGenerating || isActive) return;
      switchSession(session.id);
    };

    // Add keyboard support for selection
    li.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        li.click();
      }
    };

    li.appendChild(titleSpan);
    li.appendChild(deleteBtn);
    sessionList.appendChild(li);
  });
}

function deleteSession(id) {
  if (Object.keys(sessionData.sessions).length <= 1) {
    // Don't delete the last session, just clear it
    sessionData.sessions[id].messages = [];
    sessionData.sessions[id].traces = [];
    sessionData.sessions[id].title = "新会话";
    sessionData.sessions[id].state = "INIT";
    saveAllSessions(sessionData);
    switchSession(id);
    return;
  }

  delete sessionData.sessions[id];

  if (id === sessionId) {
    // Switch to the most recent available session
    const remainingSessions = Object.values(sessionData.sessions).sort(
      (a, b) => b.createdAt - a.createdAt,
    );
    // Persist deletion before switchSession() reloads data from localStorage.
    saveAllSessions(sessionData);
    switchSession(remainingSessions[0].id);
  } else {
    saveAllSessions(sessionData);
    renderHistorySidebar();
  }
}

function switchSession(id) {
  // Keep in-memory session cache aligned with localStorage before switching.
  sessionData = loadAllSessions();
  if (!sessionData.sessions[id]) {
    console.warn(
      "Target session not found, creating a replacement session:",
      id,
    );
    id = createNewSession();
    sessionData = loadAllSessions();
  }

  sessionId = id;
  sessionData.activeSessionId = id;
  saveAllSessions(sessionData);
  document.getElementById("session-id-display").textContent = sessionId;

  // Clear current DOM
  chatContainer.innerHTML = "";
  traceContainer.innerHTML = "";
  tokenUsage.textContent = "0";
  resetFlowCards();

  const session = getCurrentSession();

  // Restore state
  updateState(session.state || "INIT");

  // Restore Messages
  if (session.messages && session.messages.length > 0) {
    session.messages.forEach((msg) => {
      if (msg.role === "user") {
        appendUserMessage(msg.content, false);
      } else if (msg.role === "ai") {
        if (msg.plan || (msg.steps && msg.steps.length > 0) || msg.summary) {
          restoreAssistantMessage(msg);
        } else {
          // Fallback to old simple text rendering
          appendAssistantMessageHistory(msg.fallbackContent || msg.content);
        }
      }
    });
    setTimeout(scrollToBottom, 50);
  } else {
    // Show welcome message if empty
    chatContainer.innerHTML = `
            <div class="flex gap-4 max-w-3xl mx-auto w-full">
                <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0 shadow-sm mt-1">
                    <span class="text-blue-600 font-bold text-sm">AI</span>
                </div>
                <div class="bg-gray-50 rounded-2xl rounded-tl-none px-5 py-3 text-gray-800 shadow-sm border border-gray-100 markdown-body w-full">
                    <p>你好！我是 PPT Agent。请告诉我你想生成什么主题的演示文稿，或者直接粘贴内容大纲给我。</p>
                </div>
            </div>
        `;
  }

  // Restore Traces
  if (session.traces && session.traces.length > 0) {
    session.traces.forEach((trace) => {
      appendTrace(trace.content, false, trace.time);
    });
  } else {
    traceContainer.innerHTML =
      '<div class="text-gray-600 italic text-center py-4">暂无执行追踪...</div>';
  }

  renderHistorySidebar();
}

newChatBtn.addEventListener("click", () => {
  if (isGenerating) {
    alert("正在生成中，请先停止当前会话。");
    return;
  }
  const newId = createNewSession();
  sessionData = loadAllSessions();
  switchSession(newId);
});

// Initial render
renderHistorySidebar();
switchSession(sessionId);

// --- Original Logic Adjustments ---
resetBtn.addEventListener("click", () => {
  if (isGenerating) {
    alert("正在生成中，请先停止当前会话。");
    return;
  }
  const newId = createNewSession();
  sessionData = loadAllSessions();
  switchSession(newId);
});

clearTraceBtn.addEventListener("click", () => {
  traceContainer.innerHTML =
    '<div class="text-gray-600 italic text-center py-4">暂无执行追踪...</div>';
  const session = getCurrentSession();
  session.traces = [];
  saveCurrentSession();
});

function isScrolledToBottom() {
  // Return true if the user is within 50px of the bottom
  return (
    chatContainer.scrollHeight -
      chatContainer.scrollTop -
      chatContainer.clientHeight <
    50
  );
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function resetFlowCards() {
  planCardElement = null;
  summaryCardElement = null;
  stepCardMap.clear();
  stepContentMap.clear();
}

/**
 * 辅助函数：创建一个通用的流程卡片容器并追加到聊天区。
 * 用于统一计划、步骤和总结卡片的外层样式。
 */
function appendFlowCardContainer(extraClass = "") {
  const wrapper = document.createElement("div");
  wrapper.className =
    `max-w-3xl mx-auto w-full flow-card-wrapper ${extraClass}`.trim();
  chatContainer.appendChild(wrapper);
  return wrapper;
}

function getStatusIcon(status, statusIconKey) {
  if (statusIconKey && STEP_STATUS_ICON[statusIconKey]) {
    return STEP_STATUS_ICON[statusIconKey];
  }
  return STEP_STATUS_ICON_FALLBACK[status] || "🔹";
}

function shouldAdvanceStatus(oldStatus, newStatus) {
  const oldIndex = STEP_STATUS_ORDER.indexOf(oldStatus);
  const newIndex = STEP_STATUS_ORDER.indexOf(newStatus);
  if (newIndex < 0) return false;
  if (oldIndex < 0) return true;
  return newIndex >= oldIndex;
}

/**
 * 更新或插入“执行计划”卡片（对应 session_plan 事件）。
 * 如果卡片不存在则创建，如果已存在则更新其内容。
 */
function upsertPlanCard(data) {
  const totalSteps = Number(data.total_steps || 0);
  const steps = Array.isArray(data.steps) ? data.steps : [];
  if (!planCardElement) {
    planCardElement = appendFlowCardContainer();
    planCardElement.dataset.cardType = "plan";
    planCardElement.innerHTML = `
            <div class="rounded-2xl border border-blue-200 bg-blue-50 p-4 shadow-sm">
                <div class="text-xs font-semibold uppercase tracking-wider text-blue-700">整体执行计划</div>
                <div class="mt-1 text-sm text-blue-900" id="plan-total-steps"></div>
                <ol class="mt-3 space-y-1 text-sm text-blue-800 list-decimal list-inside" id="plan-steps-list"></ol>
            </div>
        `;
  }
  const totalEl = planCardElement.querySelector("#plan-total-steps");
  const listEl = planCardElement.querySelector("#plan-steps-list");
  totalEl.textContent = `${data.plan_title || "本轮任务"}：共 ${totalSteps || steps.length} 个步骤`;
  listEl.innerHTML = steps
    .map(
      (step) =>
        `<li>${escapeHtml(step.step_title || `步骤 ${step.step_no || "-"}`)}</li>`,
    )
    .join("");
  scrollToBottom();
}

/**
 * 更新或插入“步骤状态”卡片（对应 step_status 事件）。
 * 通过 step_id 跟踪特定的步骤，如果步骤卡片已存在，则只更新状态以避免重复创建。
 * 状态只会单向推进（如：开始 -> 执行 -> 完成）。
 */
function upsertStepCard(data) {
  const stepId = data.step_id || `step_${data.step_no || "unknown"}`;
  const status = data.status || "开始";
  let card = stepCardMap.get(stepId);
  if (!card) {
    card = appendFlowCardContainer();
    card.dataset.cardType = "step";
    card.dataset.stepId = stepId;
    card.dataset.status = "";
    card.innerHTML = `
            <div class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
                <div class="flex items-center justify-between gap-2">
                    <div class="text-sm font-semibold text-gray-800" id="step-title"></div>
                    <div class="text-xs text-gray-500" id="step-no"></div>
                </div>
                <div class="mt-2 inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-sm text-gray-700">
                    <span id="step-icon" aria-hidden="true">🟢</span>
                    <span id="step-status">开始</span>
                </div>
                <div class="step-content-wrapper mt-3 hidden">
                    <div class="markdown-body text-sm text-gray-800 overflow-x-auto" id="step-content-${stepId}"></div>
                </div>
            </div>
        `;
    stepCardMap.set(stepId, card);
  }

  const oldStatus = card.dataset.status || "";
  if (!shouldAdvanceStatus(oldStatus, status)) {
    return;
  }
  card.dataset.status = status;
  card.querySelector("#step-title").textContent =
    data.step_title || "未命名步骤";
  card.querySelector("#step-no").textContent = `第 ${data.step_no || "-"} 步`;
  card.querySelector("#step-icon").textContent = getStatusIcon(
    status,
    data.status_icon_key,
  );
  card.querySelector("#step-status").textContent = status;
  scrollToBottom();
}

/**
 * 更新或插入“完成总结”卡片（对应 session_summary 事件）。
 * 展示任务的最终状态及生成的文件路径等产物。
 */
function upsertSummaryCard(data) {
  if (!summaryCardElement) {
    summaryCardElement = appendFlowCardContainer();
    summaryCardElement.dataset.cardType = "summary";
    summaryCardElement.innerHTML = `
            <div class="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-sm">
                <div class="text-xs font-semibold uppercase tracking-wider text-emerald-700">完成总结</div>
                <div class="mt-1 text-sm text-emerald-900" id="summary-content"></div>
                <ul class="mt-3 space-y-1 text-sm text-emerald-800" id="summary-artifacts"></ul>
            </div>
        `;
  }
  summaryCardElement.querySelector("#summary-content").textContent =
    data.summary || data.content || "任务已完成。";
  const listEl = summaryCardElement.querySelector("#summary-artifacts");
  const artifacts = Array.isArray(data.artifacts) ? data.artifacts : [];
  listEl.innerHTML = artifacts
    .map(
      (item) =>
        `<li>${escapeHtml(item.label || "产物")}: ${escapeHtml(item.path || "-")}</li>`,
    )
    .join("");
  scrollToBottom();
}

chatContainer.addEventListener("scroll", () => {
  if (isScrolledToBottom()) {
    scrollToBottomBtn.classList.add("hidden");
  } else {
    scrollToBottomBtn.classList.remove("hidden");
  }
});

scrollToBottomBtn.addEventListener("click", () => {
  scrollToBottom();
});

function appendUserMessage(text, save = true) {
  const div = document.createElement("div");
  div.className = "flex gap-4 max-w-3xl mx-auto w-full flex-row-reverse";
  div.innerHTML = `
        <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0 shadow-sm mt-1">
            <span class="text-white font-bold text-sm">U</span>
        </div>
        <div class="bg-blue-600 text-white rounded-2xl rounded-tr-none px-5 py-3 whitespace-pre-wrap shadow-sm max-w-[85%]">
            ${escapeHtml(text)}
        </div>
    `;
  chatContainer.appendChild(div);
  scrollToBottom();

  if (save) {
    const session = getCurrentSession();
    session.messages.push({ role: "user", content: text });
    saveCurrentSession();
    updateSessionTitleIfEmpty(text);
  }
}

function createAssistantMessage() {
  const div = document.createElement("div");
  div.className = "flex gap-4 max-w-3xl mx-auto w-full";

  const avatar = document.createElement("div");
  avatar.className =
    "w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0 shadow-sm mt-1";
  avatar.innerHTML = '<span class="text-blue-600 font-bold text-sm">AI</span>';

  const contentWrapper = document.createElement("div");
  contentWrapper.className =
    "bg-gray-50 rounded-2xl rounded-tl-none px-5 py-3 text-gray-800 shadow-sm border border-gray-100 markdown-body w-full overflow-x-auto";

  div.appendChild(avatar);
  div.appendChild(contentWrapper);

  chatContainer.appendChild(div);
  const wasAtBottom = isScrolledToBottom();
  currentAssistantMessageDiv = contentWrapper;
  currentAssistantMarkdown = "";
  if (wasAtBottom) {
    scrollToBottom();
  }
}

function appendAssistantMessageHistory(markdown) {
  const div = document.createElement("div");
  div.className = "flex gap-4 max-w-3xl mx-auto w-full";

  const avatar = document.createElement("div");
  avatar.className =
    "w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0 shadow-sm mt-1";
  avatar.innerHTML = '<span class="text-blue-600 font-bold text-sm">AI</span>';

  const contentWrapper = document.createElement("div");
  contentWrapper.className =
    "bg-gray-50 rounded-2xl rounded-tl-none px-5 py-3 text-gray-800 shadow-sm border border-gray-100 markdown-body w-full overflow-x-auto";
  contentWrapper.innerHTML = renderMarkdownWithSVG(markdown);

  div.appendChild(avatar);
  div.appendChild(contentWrapper);
  chatContainer.appendChild(div);
}

function appendTrace(text, save = true, timeStr = null) {
  // Remove placeholder if exists
  const placeholder = traceContainer.querySelector(".italic");
  if (placeholder) {
    placeholder.remove();
  }

  const div = document.createElement("div");
  div.className =
    "font-mono py-0.5 border-l-2 border-transparent hover:border-gray-600 hover:bg-gray-800/50 px-2 transition-colors";

  const time =
    timeStr || new Date().toLocaleTimeString("zh-CN", { hour12: false });
  div.innerHTML = `<span class="text-green-500 select-none mr-2">[${time}]</span><span class="text-gray-300 break-words leading-relaxed">${escapeHtml(text)}</span>`;

  traceContainer.appendChild(div);
  traceContainer.scrollTop = traceContainer.scrollHeight;

  if (save) {
    const session = getCurrentSession();
    session.traces.push({ time: time, content: text });
    saveCurrentSession();
  }
}

function updateState(state) {
  agentState.textContent = state;
  if (
    state !== "INIT" &&
    state !== "DONE" &&
    state !== "ERROR" &&
    state !== "WAITING_CONFIRMATION"
  ) {
    statusPing.classList.remove("hidden");
    statusDot.classList.replace("bg-gray-400", "bg-green-500");
  } else {
    statusPing.classList.add("hidden");
    statusDot.classList.replace(
      "bg-green-500",
      state === "ERROR" ? "bg-red-500" : "bg-gray-400",
    );
  }
}

function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  // If currently generating, abort the request
  if (isGenerating) {
    if (abortController) {
      abortController.abort();
      appendTrace("用户手动终止了生成请求。");
      updateState("DONE"); // Set state to DONE or abort state
      resetInputState();
    }
    return;
  }

  const text = userInput.value.trim();
  if (!text) return;

  userInput.value = "";
  userInput.style.height = "auto";
  appendUserMessage(text);

  isGenerating = true;
  abortController = new AbortController();

  // Initialize structured response cache for this generation
  currentAiResponse = {
    role: "ai",
    plan: null,
    steps: [],
    summary: null,
    fallbackContent: ""
  };

  // Update UI for generating state
  sendIcon.classList.add("hidden");
  stopIcon.classList.remove("hidden");
  sendBtn.classList.replace("bg-blue-600", "bg-red-500");
  sendBtn.classList.replace("hover:bg-blue-700", "hover:bg-red-600");
  userInput.disabled = true;

  resetFlowCards();
  createAssistantMessage();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
      signal: abortController.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();

      for (const part of parts) {
        if (part.startsWith("data: ")) {
          const dataStr = part.slice(6);
          try {
            const data = JSON.parse(dataStr);
            handleServerEvent(data);
          } catch (err) {
            console.error("Failed to parse SSE JSON:", dataStr, err);
          }
        }
      }
    }

    // Handle any remaining buffer
    if (buffer) {
      const parts = buffer.split("\n\n");
      for (const part of parts) {
        if (part.startsWith("data: ")) {
          const dataStr = part.slice(6);
          try {
            const data = JSON.parse(dataStr);
            handleServerEvent(data);
          } catch (err) {
            console.error("Failed to parse SSE JSON:", dataStr, err);
          }
        }
      }
    }
  } catch (error) {
    if (error.name === "AbortError") {
      console.log("Fetch aborted by user");
      currentAssistantMarkdown += `\n\n*[生成已中止]*`;
      currentAssistantMessageDiv.innerHTML = renderMarkdownWithSVG(
        currentAssistantMarkdown,
      );
      const wasAtBottom = isScrolledToBottom();
      if (wasAtBottom) scrollToBottom();
    } else {
      console.error("Chat error:", error);
      currentAssistantMarkdown += `\n\n**Error**: ${error.message}`;
      currentAssistantMessageDiv.innerHTML = renderMarkdownWithSVG(
        currentAssistantMarkdown,
      );
      updateState("ERROR");
    }
  } finally {
    if (currentAiResponse && (currentAiResponse.plan || currentAiResponse.steps.length > 0 || currentAiResponse.summary || currentAiResponse.fallbackContent)) {
      const session = getCurrentSession();
      session.messages.push(currentAiResponse);
      saveCurrentSession();
    } else if (currentAssistantMarkdown) {
      // Fallback if structured data is entirely missing but markdown exists
      const session = getCurrentSession();
      session.messages.push({ role: "ai", content: currentAssistantMarkdown });
      saveCurrentSession();
    }
    resetInputState();
  }
});

function resetInputState() {
  isGenerating = false;
  abortController = null;

  // Restore send button UI
  sendIcon.classList.remove("hidden");
  stopIcon.classList.add("hidden");
  sendBtn.classList.replace("bg-red-500", "bg-blue-600");
  sendBtn.classList.replace("hover:bg-red-600", "hover:bg-blue-700");

  userInput.disabled = false;
  userInput.focus();
}

function renderMarkdownWithSVG(markdown) {
  let html = marked.parse(markdown);

  // In some cases marked.js converts the opening ```svg block but handles the first one differently
  // or adds extra classes. Let's make the regex more robust to catch any <pre><code class="language-svg"> block.
  // Also, sometimes LLMs use xml instead of svg.
  const svgBlockRegex =
    /<pre><code class="language-(?:svg|xml)">([\s\S]*?)<\/code><\/pre>/gi;

  html = html.replace(svgBlockRegex, (match, svgCodeEscaped) => {
    // Unescape HTML entities that marked.js escaped
    const svgCode = svgCodeEscaped
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'");

    // Check if it's actually an SVG by looking for <svg tag
    if (!svgCode.toLowerCase().includes("<svg")) {
      return match; // return original if it doesn't look like SVG
    }

    return `
            <div class="svg-preview-container my-4 p-4 bg-white border border-gray-200 rounded-lg shadow-sm">
                <div class="flex justify-between items-center mb-2 border-b pb-2">
                    <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">PPT Page Preview</span>
                </div>
                <div class="svg-content overflow-hidden w-full" style="max-height: 600px; display: flex; justify-content: center; align-items: center; background: #f9f9f9;">
                    ${svgCode}
                </div>
            </div>
        `;
  });

  return html;
}

function handleServerEvent(data) {
  let wasAtBottom = false;

  switch (data.type) {
    case "session_plan":
      if (currentAiResponse) {
        currentAiResponse.plan = data;
      }
      upsertPlanCard(data);
      break;
    case "step_status":
      if (currentAiResponse) {
        let step = currentAiResponse.steps.find(s => s.step_id === data.step_id);
        if (!step) {
          currentAiResponse.steps.push({ ...data, content: "" });
        } else {
          step.status = data.status;
          if (data.step_title) step.step_title = data.step_title;
          if (data.status_icon_key) step.status_icon_key = data.status_icon_key;
        }
      }
      upsertStepCard(data);
      break;
    case "session_summary":
      if (currentAiResponse) {
        currentAiResponse.summary = data;
      }
      upsertSummaryCard(data);
      break;
    case "state":
      updateState(data.content);
      break;
    case "trace":
      appendTrace(data.content);
      break;
    case "chunk":
    case "message":
      wasAtBottom = isScrolledToBottom();
      
      if (data.step_id && stepCardMap.has(data.step_id)) {
        // Append to step content
        let content = stepContentMap.get(data.step_id) || "";
        content += data.content;
        stepContentMap.set(data.step_id, content);
        
        if (currentAiResponse) {
          let step = currentAiResponse.steps.find(s => s.step_id === data.step_id);
          if (step) step.content = content;
        }
        
        const card = stepCardMap.get(data.step_id);
        const wrapper = card.querySelector(".step-content-wrapper");
        const contentEl = card.querySelector(`#step-content-${data.step_id}`);
        
        wrapper.classList.remove("hidden");
        contentEl.innerHTML = renderMarkdownWithSVG(content);
      } else {
        // Fallback to global message div
        currentAssistantMarkdown += data.content;
        if (currentAiResponse) {
          currentAiResponse.fallbackContent = currentAssistantMarkdown;
        }
        if (currentAssistantMessageDiv) {
          currentAssistantMessageDiv.innerHTML = renderMarkdownWithSVG(
            currentAssistantMarkdown,
          );
        }
      }
      
      if (wasAtBottom) scrollToBottom();
      break;
    case "usage":
      tokenUsage.textContent = data.content;
      break;
    default:
      console.warn("Unknown event type:", data);
  }
}

/**
 * 根据保存的会话数据结构恢复 UI。
 */
function restoreAssistantMessage(msg) {
  resetFlowCards();

  const fallbackContent = msg.fallbackContent || msg.content || "";
  if (fallbackContent) {
    createAssistantMessage();
    currentAssistantMarkdown = fallbackContent;
    currentAssistantMessageDiv.innerHTML = renderMarkdownWithSVG(fallbackContent);
  }

  if (msg.plan) {
    upsertPlanCard(msg.plan);
  }

  if (msg.steps && msg.steps.length > 0) {
    msg.steps.forEach(step => {
      upsertStepCard(step);
      if (step.content) {
        stepContentMap.set(step.step_id, step.content);
        const card = stepCardMap.get(step.step_id);
        const wrapper = card.querySelector(".step-content-wrapper");
        const contentEl = card.querySelector(`#step-content-${step.step_id}`);
        wrapper.classList.remove("hidden");
        contentEl.innerHTML = renderMarkdownWithSVG(step.content);
      }
    });
  }

  if (msg.summary) {
    upsertSummaryCard(msg.summary);
  }
}
