export class FrontendAPIError extends Error {
  constructor(message, response = null) {
    super(message);
    this.name = "FrontendAPIError";
    this.response = response;
    this.code = response?.error?.code ?? "NETWORK_ERROR";
  }
}

export class FrontendClient {
  constructor(baseURL = "") {
    this.baseURL = baseURL.replace(/\/$/, "");
  }

  async getConfig() {
    return this.#request("/api/config");
  }

  async getState({ subjectId, requestId }) {
    const query = new URLSearchParams({
      subject_id: subjectId,
      request_id: requestId,
    });
    return this.#request(`/api/state?${query.toString()}`);
  }

  async sendMessage({
    requestId,
    userId,
    subjectId,
    cycleId,
    message,
    expectedRevision,
  }) {
    return this.#request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: requestId,
        user_id: userId || null,
        subject_id: subjectId,
        cycle_id: cycleId,
        message,
        expected_revision: expectedRevision,
      }),
    });
  }

  subscribeEvents() {
    throw new FrontendAPIError(
      "SSE/WebSocket transport is reserved but not configured in this stage.",
    );
  }

  async #request(path, options = {}) {
    let response;
    try {
      response = await fetch(`${this.baseURL}${path}`, {
        cache: "no-store",
        ...options,
      });
    } catch (error) {
      const wrapped = new FrontendAPIError("无法连接连续性引擎 API。");
      wrapped.cause = error;
      throw wrapped;
    }

    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new FrontendAPIError("API 返回了无法解析的响应。");
    }
    if (!response.ok || payload?.error) {
      const message = payload?.error?.message ?? `请求失败（${response.status}）`;
      throw new FrontendAPIError(message, payload);
    }
    return payload;
  }
}
