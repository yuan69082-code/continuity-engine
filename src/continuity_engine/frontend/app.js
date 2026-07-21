import { FrontendAPIError, FrontendClient } from "./client.js";

const client = new FrontendClient();
const session = {
  subjectId: "",
  userId: "",
  cycleId: "",
  revision: 0,
};

const elements = {
  form: document.querySelector("#message-form"),
  input: document.querySelector("#message-input"),
  send: document.querySelector("#send-button"),
  messages: document.querySelector("#messages"),
  subject: document.querySelector("#subject-id"),
  user: document.querySelector("#user-id"),
  revision: document.querySelector("#revision-value"),
  connection: document.querySelector("#connection-status"),
  stateSummary: document.querySelector("#state-summary"),
  eventList: document.querySelector("#recent-events"),
  debugPanel: document.querySelector("#debug-panel"),
  debugToggle: document.querySelector("#debug-toggle"),
  refresh: document.querySelector("#refresh-state"),
};

function requestId(prefix) {
  const value = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  return `${prefix}-${value}`;
}

function setConnection(label, tone = "ready") {
  elements.connection.textContent = label;
  elements.connection.dataset.tone = tone;
}

function addMessage(role, content, { pending = false } = {}) {
  const item = document.createElement("article");
  item.className = `message message--${role}`;
  item.dataset.pending = String(pending);

  const label = document.createElement("span");
  label.className = "message__label";
  label.textContent = role === "user" ? "你" : role === "system" ? "系统" : "连续性引擎";

  const body = document.createElement("p");
  body.className = "message__body";
  body.textContent = content;
  item.append(label, body);
  elements.messages.append(item);
  elements.messages.scrollTop = elements.messages.scrollHeight;
  return item;
}

function renderState(response) {
  const { summary, recent_events: recentEvents = [] } = response.result;
  session.revision = response.current_revision;
  elements.revision.textContent = String(session.revision);
  elements.stateSummary.replaceChildren();

  const rows = [
    ["当前关注", summary.current_focus?.join("、") || "暂无"],
    ["未完成事项", summary.unfinished_items?.join("、") || "暂无"],
    ["关系状态", summary.relationship_status || "未设置"],
    ["最后互动", summary.last_interaction_at || "暂无"],
  ];
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "state-row";
    const term = document.createElement("span");
    term.textContent = label;
    const detail = document.createElement("strong");
    detail.textContent = value;
    row.append(term, detail);
    elements.stateSummary.append(row);
  }

  elements.eventList.replaceChildren();
  if (!recentEvents.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "暂无事件";
    elements.eventList.append(empty);
  } else {
    for (const event of recentEvents) {
      const item = document.createElement("li");
      const type = document.createElement("strong");
      type.textContent = event.event_type;
      const content = document.createElement("span");
      content.textContent = event.content;
      item.append(type, content);
      elements.eventList.append(item);
    }
  }
}

async function refreshState() {
  session.subjectId = elements.subject.value.trim();
  if (!session.subjectId) return;
  setConnection("同步状态…", "working");
  try {
    const response = await client.getState({
      subjectId: session.subjectId,
      requestId: requestId("state"),
    });
    renderState(response);
    setConnection("API 已连接", "ready");
  } catch (error) {
    const message = error instanceof FrontendAPIError ? error.message : "状态同步失败。";
    setConnection(message, "error");
  }
}

async function submitMessage(event) {
  event.preventDefault();
  const message = elements.input.value.trim();
  if (!message || elements.send.disabled) return;

  session.subjectId = elements.subject.value.trim();
  session.userId = elements.user.value.trim();
  addMessage("user", message);
  elements.input.value = "";
  elements.send.disabled = true;
  const pending = addMessage("assistant", "正在经过感知、思考与行动决策…", {
    pending: true,
  });
  setConnection("连续性流程运行中", "working");

  try {
    const response = await client.sendMessage({
      requestId: requestId("chat"),
      userId: session.userId,
      subjectId: session.subjectId,
      cycleId: session.cycleId,
      message,
      expectedRevision: session.revision,
    });
    pending.remove();
    addMessage("assistant", response.result.reply.content);
    session.revision = response.current_revision;
    await refreshState();
  } catch (error) {
    pending.remove();
    const messageText = error instanceof FrontendAPIError ? error.message : "请求处理失败。";
    addMessage("system", messageText);
    setConnection("请求失败", "error");
    await refreshState();
  } finally {
    elements.send.disabled = false;
    elements.input.focus();
  }
}

async function boot() {
  setConnection("连接 API…", "working");
  try {
    const config = await client.getConfig();
    session.subjectId = config.subject_id;
    session.cycleId = config.cycle_id;
    elements.subject.value = session.subjectId;
    await refreshState();
  } catch (error) {
    setConnection(error.message || "启动失败", "error");
  }
}

elements.form.addEventListener("submit", submitMessage);
elements.refresh.addEventListener("click", refreshState);
elements.subject.addEventListener("change", refreshState);
elements.debugToggle.addEventListener("click", () => {
  const open = elements.debugPanel.toggleAttribute("data-open");
  elements.debugToggle.setAttribute("aria-expanded", String(open));
});
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

boot();
