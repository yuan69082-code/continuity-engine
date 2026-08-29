from __future__ import annotations

import hmac
import json
import re
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import unquote, urlsplit

from continuity_engine.domain.errors import (
    CapabilityConflictError,
    CapabilityNotFoundError,
    CapabilityValidationError,
    MachineContractCallError,
)
from continuity_engine.interfaces.integration_config import (
    MAX_REQUEST_BODY_BYTES,
    IntegrationConfigurationError,
    IntegrationServerConfig,
)
from continuity_engine.interfaces.local_integration_app import LocalIntegrationApp


_INTERACTION_PATH = "/internal/v1/continuity/interactions"
_CAPABILITY_RESULT_PATH = "/internal/v1/continuity/capability-results"
_QUERY_PREFIX = "/internal/v1/continuity/requests/"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_JSON_CONTENT_TYPES = {
    "application/json",
    "application/json; charset=utf-8",
}
_DISCARD_BUFFER_BYTES = 64 * 1024
_DISCARD_IDLE_TIMEOUT_SECONDS = 0.1
_DISCARD_TOTAL_TIMEOUT_SECONDS = 1.0
_CONNECTION_ERRORS = (
    socket.timeout,
    BrokenPipeError,
    ConnectionResetError,
    ConnectionAbortedError,
    OSError,
)


class LocalIntegrationHTTPServer(HTTPServer):
    """Serial, loopback-only HTTP boundary for one formal local app."""

    def __init__(
        self,
        config: IntegrationServerConfig,
        app: LocalIntegrationApp,
    ) -> None:
        if config.thinking_mode is not app.thinking_mode:
            raise IntegrationConfigurationError(
                "HTTP configuration thinking mode must match the local app"
            )
        self.integration_config = config
        self.integration_app = app
        super().__init__((config.host, config.port), IntegrationHTTPRequestHandler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Keep connection-level failures inside the local transport boundary."""

        error = sys.exc_info()[1]
        if isinstance(error, _CONNECTION_ERRORS):
            return
        sys.stderr.write("continuity integration connection failed\n")
        sys.stderr.flush()


class IntegrationHTTPRequestHandler(BaseHTTPRequestHandler):
    server: LocalIntegrationHTTPServer
    protocol_version = "HTTP/1.1"
    server_version = "ContinuityEngineLocalIntegration"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(
            self.server.integration_config.read_timeout_seconds
        )

    def handle(self) -> None:
        try:
            super().handle()
        except _CONNECTION_ERRORS:
            self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        path = urlsplit(self.path).path
        if path == "/health/live":
            self._send_json(200, {"status": "live"})
            return
        if path == "/health/ready":
            status = 200 if self.server.integration_app.is_ready() else 503
            self._send_json(status, {"status": "ready" if status == 200 else "not_ready"})
            return
        if path in {_INTERACTION_PATH, _CAPABILITY_RESULT_PATH}:
            self._send_transport_error(405, "method_not_allowed")
            return
        if path.startswith(_QUERY_PREFIX):
            if not self._authorized():
                return
            if not self.server.integration_app.is_ready():
                self._send_transport_error(503, "not_ready")
                return
            request_id = self._query_request_id(path)
            if request_id is None:
                self._send_transport_error(400, "invalid_request_id")
                return
            try:
                result = self.server.integration_app.adapter.query_request(request_id)
                if result is None:
                    self._send_transport_error(404, "not_found")
                else:
                    self._send_json(200, result.to_dict())
            except MachineContractCallError:
                self._send_transport_error(400, "invalid_request_id")
            except Exception:
                self._controlled_fault()
            return
        self._send_transport_error(404, "not_found")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        path = urlsplit(self.path).path
        if path not in {_INTERACTION_PATH, _CAPABILITY_RESULT_PATH}:
            if path.startswith(_QUERY_PREFIX) or path.startswith("/health/"):
                self._reject_post_before_body(405, "method_not_allowed")
            else:
                self._reject_post_before_body(404, "not_found")
            return
        if not self._authorized(before_post_body=True):
            return
        if not self.server.integration_app.is_ready():
            self._reject_post_before_body(503, "not_ready")
            return
        content_type = self.headers.get("Content-Type", "").strip().lower()
        if content_type not in _JSON_CONTENT_TYPES:
            self._reject_post_before_body(415, "unsupported_media_type")
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._reject_post_before_body(400, "transfer_encoding_not_supported")
            return
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._reject_post_before_body(411, "length_required")
            return
        try:
            length = int(content_length, 10)
        except ValueError:
            self._reject_post_before_body(400, "invalid_content_length")
            return
        if length < 0:
            self._reject_post_before_body(400, "invalid_content_length")
            return
        if length > MAX_REQUEST_BODY_BYTES:
            self._reject_post_before_body(413, "payload_too_large")
            return
        try:
            body = self.rfile.read(length)
        except socket.timeout:
            self._send_transport_error(408, "request_timeout")
            return
        except _CONNECTION_ERRORS:
            self.close_connection = True
            return
        if len(body) != length:
            self._send_transport_error(400, "incomplete_body")
            return
        try:
            payload: Any = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_transport_error(400, "invalid_json")
            return
        if not isinstance(payload, dict) or self._safe_body_request_id(payload) is None:
            self._send_transport_error(400, "invalid_request")
            return
        try:
            result = (
                self.server.integration_app.adapter.submit_capability_result(payload)
                if path == _CAPABILITY_RESULT_PATH
                else self.server.integration_app.adapter.submit(payload)
            )
            self._send_json(200, result.to_dict())
        except CapabilityNotFoundError:
            self._send_transport_error(404, "capability_request_not_found")
        except CapabilityConflictError:
            self._send_transport_error(409, "capability_result_conflict")
        except CapabilityValidationError:
            self._send_transport_error(400, "capability_result_invalid")
        except MachineContractCallError:
            self._send_transport_error(400, "invalid_request")
        except Exception:
            self._controlled_fault()

    def do_PUT(self) -> None:  # noqa: N802
        self._send_transport_error(405, "method_not_allowed")

    def do_PATCH(self) -> None:  # noqa: N802
        self._send_transport_error(405, "method_not_allowed")

    def do_DELETE(self) -> None:  # noqa: N802
        self._send_transport_error(405, "method_not_allowed")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_transport_error(405, "method_not_allowed")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_transport_error(405, "method_not_allowed")

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        """Replace BaseHTTPRequestHandler's HTML errors with the JSON boundary."""

        if code == 501:
            self._send_transport_error(405, "method_not_allowed")
            return
        self._send_transport_error(400, "bad_request")

    def _authorized(self, *, before_post_body: bool = False) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.integration_config.service_token}"
        if not hmac.compare_digest(supplied, expected):
            if before_post_body:
                self._reject_post_before_body(401, "unauthorized")
            else:
                self._send_transport_error(401, "unauthorized")
            return False
        return True

    @staticmethod
    def _safe_body_request_id(payload: dict[str, Any]) -> str | None:
        request_id = payload.get("requestId")
        if not isinstance(request_id, str) or _SAFE_REQUEST_ID.fullmatch(request_id) is None:
            return None
        return request_id

    @staticmethod
    def _query_request_id(path: str) -> str | None:
        encoded = path[len(_QUERY_PREFIX) :]
        if not encoded or "/" in encoded:
            return None
        try:
            decoded = unquote(encoded, errors="strict")
        except UnicodeDecodeError:
            return None
        if _SAFE_REQUEST_ID.fullmatch(decoded) is None:
            return None
        return decoded

    def _controlled_fault(self) -> None:
        sys.stderr.write("continuity integration request failed\n")
        sys.stderr.flush()
        self._send_transport_error(500, "internal_error")

    def _reject_post_before_body(self, status: int, code: str) -> None:
        response_sent = self._send_json(status, {"error": code})
        if response_sent:
            self._graceful_close_unread_input()

    def _graceful_close_unread_input(self) -> None:
        """Finish a one-shot rejected POST without parsing or retaining its body."""

        previous_timeout = self.connection.gettimeout()
        total_timeout = min(
            self.server.integration_config.read_timeout_seconds,
            _DISCARD_TOTAL_TIMEOUT_SECONDS,
        )
        deadline = time.monotonic() + total_timeout
        try:
            self.connection.shutdown(socket.SHUT_WR)
            while True:
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    break
                self.connection.settimeout(
                    min(remaining_time, _DISCARD_IDLE_TIMEOUT_SECONDS)
                )
                chunk = self.rfile.read1(_DISCARD_BUFFER_BYTES)
                if not chunk:
                    break
        except socket.timeout:
            pass
        except _CONNECTION_ERRORS:
            pass
        finally:
            self.close_connection = True
            try:
                self.connection.settimeout(previous_timeout)
            except _CONNECTION_ERRORS:
                pass

    def _send_transport_error(self, status: int, code: str) -> None:
        self._send_json(status, {"error": code})

    def _send_json(self, status: int, payload: dict[str, Any]) -> bool:
        self.close_connection = True
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
                self.wfile.flush()
            return True
        except _CONNECTION_ERRORS:
            self.close_connection = True
            return False

    def log_message(self, format: str, *args: Any) -> None:
        # The local formal boundary deliberately emits no request headers or bodies.
        return
