const state = {
  sessionId: null,
  sessions: [],
  messages: [],
  memories: [],
  toolEvents: [],
  busy: false,
  pendingMessage: null,
};

const els = {
  sessionList: document.getElementById("sessionList"),
  sessionCount: document.getElementById("sessionCount"),
  sessionTitle: document.getElementById("sessionTitle"),
  messages: document.getElementById("messages"),
  previewPanel: document.getElementById("previewPanel"),
  toolLog: document.getElementById("toolLog"),
  chatForm: document.getElementById("chatForm"),
  promptInput: document.getElementById("promptInput"),
  sendButton: document.getElementById("sendButton"),
  statusText: document.getElementById("statusText"),
  newSessionButton: document.getElementById("newSessionButton"),
  modelSelect: document.getElementById("modelSelect"),
  workspaceInput: document.getElementById("workspaceInput"),
  memoryForm: document.getElementById("memoryForm"),
  memoryInput: document.getElementById("memoryInput"),
  memoryList: document.getElementById("memoryList"),
  setupBanner: document.getElementById("setupBanner"),
  messageTemplate: document.getElementById("messageTemplate"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}

function renderSessions() {
  els.sessionCount.textContent = String(state.sessions.length);
  els.sessionList.innerHTML = "";

  if (!state.sessions.length) {
    els.sessionList.innerHTML = `<div class="empty-state">No sessions yet.</div>`;
    return;
  }

  state.sessions.forEach((session) => {
    const item = document.createElement("article");
    item.className = `session-item${session.id === state.sessionId ? " active" : ""}`;
    item.innerHTML = `
      <button class="session-main" type="button">
        <strong>${escapeHtml(session.title)}</strong>
        <div class="session-meta">${formatDate(session.updated_at)}</div>
      </button>
      <button class="session-delete" type="button" aria-label="Delete session">Delete</button>
    `;
    item.querySelector(".session-main").addEventListener("click", () => loadSession(session.id));
    item.querySelector(".session-delete").addEventListener("click", async (event) => {
      event.stopPropagation();
      await deleteSession(session.id);
    });
    els.sessionList.appendChild(item);
  });
}

function renderMessages() {
  els.messages.innerHTML = "";
  const visibleMessages = state.pendingMessage ? [...state.messages, state.pendingMessage] : state.messages;
  if (!visibleMessages.length) {
    els.messages.innerHTML = `<div class="empty-state">Start a session and ask Atlas to build, explain, or inspect something.</div>`;
    return;
  }

  visibleMessages.forEach((message) => {
    const node = els.messageTemplate.content.firstElementChild.cloneNode(true);
    node.classList.add(message.role);
    if (message.pending) {
      node.classList.add("thinking");
    }
    node.querySelector(".message-role").textContent = message.role;
    renderMessageBody(node.querySelector(".message-body"), message);
    els.messages.appendChild(node);
  });
  els.messages.scrollTop = els.messages.scrollHeight;
  renderPreview();
}

function renderPreview() {
  const latestCode = findLatestCodeBlock();
  if (!latestCode) {
    els.previewPanel.className = "preview-panel empty-state";
    els.previewPanel.textContent = "No code preview yet.";
    return;
  }

  els.previewPanel.className = "preview-panel";
  els.previewPanel.innerHTML = `
    <div class="preview-head">${escapeHtml(latestCode.language || "code")}</div>
    <pre><code>${escapeHtml(latestCode.code)}</code></pre>
  `;
}

function findLatestCodeBlock() {
  for (let index = state.messages.length - 1; index >= 0; index -= 1) {
    const message = state.messages[index];
    if (message.role !== "assistant") {
      continue;
    }
    const match = String(message.content || "").match(/```([\w+-]*)\n([\s\S]*?)```/);
    if (match) {
      return {
        language: match[1],
        code: match[2].trim(),
      };
    }
  }
  return null;
}

function renderMessageBody(container, message) {
  if (message.pending) {
    container.innerHTML = `
      <div class="thinking-wrap">
        <span>Thinking</span>
        <div class="thinking-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = renderRichText(message.content || "");
}

function renderRichText(text) {
  const blocks = String(text).split("```");
  return blocks
    .map((block, index) => {
      if (index % 2 === 1) {
        const lines = block.split("\n");
        const language = lines[0].trim();
        const code = lines.slice(1).join("\n");
        return `
          <div class="code-block">
            <div class="code-head">${escapeHtml(language || "code")}</div>
            <pre><code>${escapeHtml(code)}</code></pre>
          </div>
        `;
      }
      return block
        .split("\n")
        .map((line) => `<p>${renderInlineCode(line)}</p>`)
        .join("");
    })
    .join("");
}

function renderInlineCode(line) {
  const parts = String(line).split("`");
  return parts
    .map((part, index) => (index % 2 === 1 ? `<code>${escapeHtml(part)}</code>` : escapeHtml(part)))
    .join("");
}

function renderToolEvents() {
  if (!state.toolEvents.length) {
    els.toolLog.className = "tool-log empty-state";
    els.toolLog.textContent = "No tool calls yet.";
    return;
  }

  els.toolLog.className = "tool-log";
  els.toolLog.innerHTML = "";
  [...state.toolEvents].reverse().forEach((event) => {
    const card = document.createElement("article");
    card.className = "tool-card";
    card.innerHTML = `
      <div class="tool-card-header">
        <div class="tool-name">${escapeHtml(event.name)}</div>
        <div class="session-meta">${formatDate(event.at)}</div>
      </div>
      <div class="tool-args">${escapeHtml(JSON.stringify(event.arguments, null, 2))}</div>
      <div class="tool-result">${escapeHtml(event.result)}</div>
    `;
    els.toolLog.appendChild(card);
  });
}

function renderMemories() {
  els.memoryList.innerHTML = "";
  if (!state.memories.length) {
    els.memoryList.innerHTML = `<div class="empty-state">No saved memory yet.</div>`;
    return;
  }

  state.memories.forEach((item) => {
    const card = document.createElement("article");
    card.className = "memory-item";
    card.innerHTML = `
      <div>${escapeHtml(item.text)}</div>
      <div class="memory-date">${formatDate(item.created_at)}</div>
    `;
    els.memoryList.appendChild(card);
  });
}

function setBusy(busy, label = "Ready") {
  state.busy = busy;
  els.sendButton.disabled = busy;
  els.promptInput.disabled = busy;
  els.statusText.textContent = label;
}

async function refreshSessions() {
  state.sessions = await api("/api/sessions");
  renderSessions();
}

async function refreshMemories() {
  state.memories = await api("/api/memory");
  renderMemories();
}

async function createSession(title = "New Session") {
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  await refreshSessions();
  await loadSession(session.id);
}

async function deleteSession(sessionId) {
  await api(`/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (state.sessionId === sessionId) {
    state.sessionId = null;
    state.messages = [];
    els.sessionTitle.textContent = "New Session";
  }
  await refreshSessions();
  if (state.sessions.length) {
    await loadSession(state.sessions[0].id);
  } else {
    renderMessages();
    renderToolEvents();
  }
}

async function loadSession(sessionId) {
  const data = await api(`/api/sessions/${sessionId}`);
  state.sessionId = sessionId;
  state.messages = data.messages;
  els.sessionTitle.textContent = data.session.title;
  renderSessions();
  renderMessages();
}

async function sendMessage(message) {
  setBusy(true, "Thinking and using tools");
  const optimisticUser = {
    role: "user",
    content: message,
  };
  state.messages = [...state.messages, optimisticUser];
  state.pendingMessage = {
    role: "assistant",
    content: "",
    pending: true,
  };
  renderMessages();
  try {
    const payload = {
      session_id: state.sessionId,
      message,
      model: els.modelSelect.value,
      workspace: els.workspaceInput.value.trim() || ".",
    };
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.sessionId = data.session.id;
    state.messages = data.messages;
    state.pendingMessage = null;
    els.sessionTitle.textContent = data.session.title;
    const stamped = data.tool_events.map((event) => ({ ...event, at: new Date().toISOString() }));
    state.toolEvents.push(...stamped);
    await refreshSessions();
    renderMessages();
    renderToolEvents();
  } catch (error) {
    state.pendingMessage = null;
    state.messages = [
      ...state.messages,
      {
        role: "assistant",
        content: `Request error: ${error.message}`,
      },
    ];
    renderMessages();
    throw error;
  } finally {
    setBusy(false, "Ready");
  }
}

function formatDate(value) {
  return new Date(value).toLocaleString();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

els.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = els.promptInput.value.trim();
  if (!message || state.busy) {
    return;
  }
  els.promptInput.value = "";
  try {
    await sendMessage(message);
  } catch (_) {
    setBusy(false, "Error");
  }
});

els.newSessionButton.addEventListener("click", async () => {
  await createSession();
});

els.memoryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = els.memoryInput.value.trim();
  if (!text) {
    return;
  }
  await api("/api/memory", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  els.memoryInput.value = "";
  await refreshMemories();
});

async function boot() {
  const health = await api("/api/health");
  els.modelSelect.value = health.default_model;
  els.workspaceInput.placeholder = health.workspace_root;
  if (!health.api_key_configured) {
    els.setupBanner.classList.remove("hidden");
    els.setupBanner.textContent = health.local_fallback_enabled
      ? `No provider key is configured. Atlas will still work in local fallback mode. Add ${health.api_key_name} later if you want stronger hosted-model answers.`
      : `${health.api_key_name} is not configured yet. Create a .env file in the project root, add ${health.api_key_name}=your_real_key, then restart the server.`;
  } else {
    els.setupBanner.classList.add("hidden");
    els.setupBanner.textContent = "";
  }
  await refreshSessions();
  await refreshMemories();
  if (state.sessions.length) {
    await loadSession(state.sessions[0].id);
  } else {
    renderMessages();
    renderToolEvents();
  }
}

boot().catch((error) => {
  els.messages.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  setBusy(false, "Error");
});
