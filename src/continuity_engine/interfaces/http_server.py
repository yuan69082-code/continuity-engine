from __future__ import annotations

import json
import mimetypes
from datetime import timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from continuity_engine.domain.models import utc_now

from .models import ChatAPIRequest, SubjectStateAPIRequest
from .ports import ContinuityAPI


_STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/client.js": "client.js",
    "/styles.css": "styles.css",
}


class FrontendHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address,
        api: ContinuityAPI,
        *,
        static_root: Path,
        default_subject_id: str,
        default_cycle_id: str,
    ) -> None:
        self.api = api
        self.static_root = static_root
        self.default_subject_id = default_subject_id
        self.default_cycle_id = default_cycle_id
        super().__init__(server_address, FrontendRequestHandler)


class FrontendRequestHandler(BaseHTTPRequestHandler):
    server: FrontendHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in _STATIC_FILES:
            self._serve_static(_STATIC_FILES[parsed.path])
            return
        if parsed.path == "/api/config":
            self._write_json(
                200,
                {
                    "subject_id": self.server.default_subject_id,
                    "cycle_id": self.server.default_cycle_id,
                    "realtime": {
                        "sse": False,
                        "websocket": False,
                    },
                },
            )
            return
        if parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            subject_id = self._first(query, "subject_id") or self.server.default_subject_id
            request_id = self._first(query, "request_id") or str(uuid4())
            try:
                response = self.server.api.get_subject_state(
                    SubjectStateAPIRequest(
                        request_id=request_id,
                        subject_id=subject_id,
                    )
                )
                self._write_json(200 if response.successful else 403, response.to_dict())
            except Exception as exc:
                self._write_transport_error(request_id, subject_id, exc)
            return
        self._write_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self._write_json(404, {"error": "not found"})
            return
        request_id = str(uuid4())
        subject_id = self.server.default_subject_id
        try:
            payload = self._read_json()
            request_id = payload.get("request_id") or request_id
            subject_id = payload.get("subject_id") or subject_id
            response = self.server.api.submit_message(
                ChatAPIRequest(
                    request_id=request_id,
                    subject_id=subject_id,
                    cycle_id=payload.get("cycle_id") or self.server.default_cycle_id,
                    message=payload.get("message"),
                    expected_revision=payload.get("expected_revision"),
                    user_id=payload.get("user_id"),
                    depth=payload.get("depth", "NORMAL"),
                )
            )
            status = 200
            if not response.successful:
                status = {
                    "PERMISSION_DENIED": 403,
                    "CONFIRMATION_REQUIRED": 403,
                    "RESOURCE_DEFERRED": 429,
                }.get(response.error.code, 409)
            self._write_json(status, response.to_dict())
        except Exception as exc:
            self._write_transport_error(request_id, subject_id, exc)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")
        length = int(raw_length)
        if length <= 0 or length > 65_536:
            raise ValueError("request body must be between 1 and 65536 bytes")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _serve_static(self, filename: str) -> None:
        path = self.server.static_root / filename
        if not path.is_file():
            self._write_json(404, {"error": "frontend asset not found"})
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(content)

    def _write_transport_error(
        self,
        request_id: str,
        subject_id: str,
        error: Exception,
    ) -> None:
        self._write_json(
            400,
            {
                "request_id": request_id,
                "subject_id": subject_id,
                "timestamp": utc_now().astimezone(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                ),
                "current_revision": None,
                "result": None,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(error) or type(error).__name__,
                    "details": {},
                },
            },
        )

    def _write_json(self, status: int, payload: Any) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _first(query: dict[str, list[str]], name: str) -> str | None:
        values = query.get(name)
        return values[0] if values else None

    def log_message(self, format: str, *args) -> None:
        return


def create_frontend_server(
    api: ContinuityAPI,
    *,
    subject_id: str,
    cycle_id: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    static_root: Path | str | None = None,
) -> FrontendHTTPServer:
    root = (
        Path(static_root)
        if static_root is not None
        else Path(__file__).resolve().parents[1] / "frontend"
    )
    return FrontendHTTPServer(
        (host, port),
        api,
        static_root=root,
        default_subject_id=subject_id,
        default_cycle_id=cycle_id,
    )
