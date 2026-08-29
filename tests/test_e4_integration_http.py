from __future__ import annotations

import copy
import http.client
import io
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import (
    IntegrationOperationRecord,
    IntegrationOperationStage,
)
from continuity_engine.interfaces.integration_config import (
    DEFAULT_INTEGRATION_HOST,
    DEFAULT_INTEGRATION_PORT,
    DEFAULT_READ_TIMEOUT_SECONDS,
    IntegrationConfigurationError,
    IntegrationServerConfig,
)
from continuity_engine.interfaces.integration_http_server import LocalIntegrationHTTPServer
from continuity_engine.interfaces.local_integration_app import (
    build_local_integration_app,
    initialize_local_integration,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_request_hash,
)
from tests.test_contract_test_adapter import first_round_request, replace_identity


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "formal-local-integration-token-0001"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class E4IntegrationHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.binding_file = self.root / "binding.json"
        fixture = SubjectBindingFixture.first_round()
        self.binding_hash = calculate_binding_fixture_hash(fixture)
        self.binding_file.write_text(json.dumps(fixture.to_dict()), encoding="utf-8")
        initialize_local_integration(
            data_dir=self.data,
            binding_file=self.binding_file,
            binding_fixture_hash=self.binding_hash,
            cycle_id="formal-cycle-001",
        )
        self.app = build_local_integration_app(self.data)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @contextmanager
    def server(self, *, read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS):
        config = IntegrationServerConfig(
            data_dir=self.data,
            service_token=TOKEN,
            port=free_port(),
            read_timeout_seconds=read_timeout_seconds,
        )
        server = LocalIntegrationHTTPServer(config, self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def call(
        self,
        server: LocalIntegrationHTTPServer,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        token: str | None = TOKEN,
        content_type: str | None = "application/json",
    ) -> tuple[int, dict[str, object], http.client.HTTPResponse]:
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if content_type is not None:
            headers["Content-Type"] = content_type
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        self.assertEqual(response.headers.get("Connection"), "close")
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(int(response.headers["Content-Length"]), len(raw))
        connection.close()
        return response.status, payload, response

    def post_request(self, server, payload=None, **kwargs):
        value = payload if payload is not None else first_round_request()
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self.call(
            server,
            "POST",
            "/internal/v1/continuity/interactions",
            body=body,
            **kwargs,
        )

    def raw_exchange(
        self,
        server: LocalIntegrationHTTPServer,
        raw: bytes,
        *,
        timeout: float = 5,
    ) -> bytes:
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=5) as client:
            client.settimeout(timeout)
            client.sendall(raw)
            chunks: list[bytes] = []
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
        return b"".join(chunks)

    def assert_raw_json_response(
        self,
        response: bytes,
        status: int,
        payload: dict[str, object],
    ) -> None:
        head, body = response.split(b"\r\n\r\n", 1)
        self.assertEqual(int(head.split(b"\r\n", 1)[0].split()[1]), status)
        self.assertIn(b"Connection: close", head)
        self.assertIn(b"Cache-Control: no-store", head)
        self.assertIn(f"Content-Length: {len(body)}".encode("ascii"), head)
        self.assertEqual(json.loads(body.decode("utf-8")), payload)
        self.assertEqual(response.count(b"HTTP/1.1"), 1)
        self.assertNotIn(b"<!DOCTYPE", response)

    def test_config_defaults_are_loopback_and_8766(self) -> None:
        config = IntegrationServerConfig(self.data, TOKEN)
        self.assertEqual(config.host, DEFAULT_INTEGRATION_HOST)
        self.assertEqual(config.port, DEFAULT_INTEGRATION_PORT)
        self.assertEqual(config.read_timeout_seconds, DEFAULT_READ_TIMEOUT_SECONDS)

    def test_read_timeout_must_be_positive_and_finite(self) -> None:
        for value in (0, -1, True, float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(IntegrationConfigurationError):
                    IntegrationServerConfig(
                        self.data,
                        TOKEN,
                        read_timeout_seconds=value,
                    )

    def test_non_loopback_hosts_are_rejected(self) -> None:
        for host in ("0.0.0.0", "::", "::1", "192.168.1.5", "localhost"):
            with self.subTest(host=host):
                with self.assertRaises(IntegrationConfigurationError):
                    IntegrationServerConfig(self.data, TOKEN, host=host)

    def test_short_or_missing_token_is_rejected_at_configuration(self) -> None:
        for token in ("", "short"):
            with self.subTest(token=token):
                with self.assertRaises(IntegrationConfigurationError):
                    IntegrationServerConfig(self.data, token)

    def test_server_socket_is_ipv4_loopback_only(self) -> None:
        with self.server() as server:
            self.assertEqual(server.server_address[0], "127.0.0.1")

    def test_authorized_post_returns_raw_success_envelope(self) -> None:
        with self.server() as server:
            status, payload, response = self.post_request(server)
        self.assertEqual(status, 200)
        self.assertEqual(payload["contractVersion"], "continuity-integration/v1.1")
        self.assertEqual(payload["status"], "completed")
        self.assertNotIn("result", payload)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_missing_or_wrong_token_returns_401(self) -> None:
        operations_before = self.app.ledger.list_operations()
        with self.server() as server:
            for attempt in range(3):
                for token in (None, "x" * 32):
                    with self.subTest(attempt=attempt, token=token):
                        status, payload, _ = self.post_request(server, token=token)
                        self.assertEqual(status, 401)
                        self.assertEqual(payload, {"error": "unauthorized"})

            headers_only = (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 1048576\r\n\r\n"
            )
            started = time.monotonic()
            response = self.raw_exchange(server, headers_only, timeout=2)
            elapsed = time.monotonic() - started
            health_status, health_payload, _ = self.call(
                server, "GET", "/health/live", token=None, content_type=None
            )

        self.assert_raw_json_response(response, 401, {"error": "unauthorized"})
        self.assertLess(elapsed, 1.5)
        self.assertEqual((health_status, health_payload), (200, {"status": "live"}))
        self.assertEqual(self.app.ledger.list_operations(), operations_before)

    def test_token_is_not_persisted_or_echoed(self) -> None:
        with self.server() as server:
            status, payload, _ = self.post_request(server, token="z" * 32)
        self.assertEqual(status, 401)
        self.assertNotIn("z" * 32, json.dumps(payload))
        for path in self.data.rglob("*"):
            if path.is_file():
                self.assertNotIn(TOKEN.encode(), path.read_bytes())

    def test_content_type_accepts_only_two_json_forms(self) -> None:
        with self.server() as server:
            status, _, _ = self.post_request(
                server,
                first_round_request(request_id="request-a"),
                content_type="application/json; charset=utf-8",
            )
            self.assertEqual(status, 200)
            for content_type in ("text/json", "application/json; charset=utf-16", None):
                with self.subTest(content_type=content_type):
                    status, _, _ = self.post_request(
                        server,
                        first_round_request(request_id="request-b"),
                        content_type=content_type,
                    )
                    self.assertEqual(status, 415)

    def test_body_over_one_mebibyte_returns_413(self) -> None:
        with self.server() as server:
            status, payload, _ = self.call(
                server,
                "POST",
                "/internal/v1/continuity/interactions",
                body=b"x" * 1_048_577,
            )
        self.assertEqual(status, 413)
        self.assertEqual(payload, {"error": "payload_too_large"})

    def test_missing_content_length_returns_411(self) -> None:
        with self.server() as server:
            raw = (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + f"Authorization: Bearer {TOKEN}\r\n".encode()
                + b"Content-Type: application/json\r\n\r\n"
            )
            response = self.raw_exchange(server, raw)
        self.assert_raw_json_response(
            response,
            411,
            {"error": "length_required"},
        )

    def test_chunked_transfer_is_rejected(self) -> None:
        with self.server() as server:
            raw = (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + f"Authorization: Bearer {TOKEN}\r\n".encode()
                + b"Content-Type: application/json\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n"
            )
            response = self.raw_exchange(server, raw)
        self.assert_raw_json_response(
            response,
            400,
            {"error": "transfer_encoding_not_supported"},
        )

    def test_rejected_unread_bodies_close_connection_without_pipelining(self) -> None:
        suffix = b"GET /health/live HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
        authorized = f"Authorization: Bearer {TOKEN}\r\n".encode()
        cases = (
            (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\nContent-Type: application/json\r\n"
                b"Content-Length: 2\r\n\r\n{}" + suffix,
                401,
                {"error": "unauthorized"},
            ),
            (
                b"POST /missing HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                b"Content-Length: 2\r\n\r\n{}" + suffix,
                404,
                {"error": "not_found"},
            ),
            (
                b"POST /health/live HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                b"Content-Length: 2\r\n\r\n{}" + suffix,
                405,
                {"error": "method_not_allowed"},
            ),
            (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + authorized
                + b"Content-Type: application/json\r\n"
                b"Content-Length: 1048577\r\n\r\n{}" + suffix,
                413,
                {"error": "payload_too_large"},
            ),
            (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + authorized
                + b"Content-Type: text/plain\r\nContent-Length: 2\r\n\r\n{}"
                + suffix,
                415,
                {"error": "unsupported_media_type"},
            ),
            (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + authorized
                + b"Content-Type: application/json\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n"
                + suffix,
                400,
                {"error": "transfer_encoding_not_supported"},
            ),
            (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + authorized
                + b"Content-Type: application/json\r\n\r\n{}"
                + suffix,
                411,
                {"error": "length_required"},
            ),
            (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + authorized
                + b"Content-Type: application/json\r\n"
                b"Content-Length: invalid\r\n\r\n{}"
                + suffix,
                400,
                {"error": "invalid_content_length"},
            ),
            (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + authorized
                + b"Content-Type: application/json\r\n"
                b"Content-Length: -1\r\n\r\n{}"
                + suffix,
                400,
                {"error": "invalid_content_length"},
            ),
        )
        operations_before = self.app.ledger.list_operations()
        with self.server() as server:
            for raw, status, payload in cases:
                with self.subTest(status=status, payload=payload):
                    self.assert_raw_json_response(
                        self.raw_exchange(server, raw),
                        status,
                        payload,
                    )

            not_ready = (
                b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                + authorized
                + b"Content-Type: application/json\r\n"
                b"Content-Length: 2\r\n\r\n{}"
                + suffix
            )
            with patch.object(type(self.app), "is_ready", return_value=False):
                self.assert_raw_json_response(
                    self.raw_exchange(server, not_ready),
                    503,
                    {"error": "not_ready"},
                )
            health_status, health_payload, _ = self.call(
                server, "GET", "/health/live", token=None, content_type=None
            )

        self.assertEqual((health_status, health_payload), (200, {"status": "live"}))
        self.assertEqual(self.app.ledger.list_operations(), operations_before)

    def test_unknown_http_method_is_json_405_and_closes_connection(self) -> None:
        unknown = (
            b"BREW /health/live HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n\r\n"
        )
        head = (
            b"HEAD /health/live HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n\r\n"
        )
        with self.server() as server:
            response = self.raw_exchange(server, unknown)
            head_response = self.raw_exchange(server, head)
        self.assert_raw_json_response(
            response,
            405,
            {"error": "method_not_allowed"},
        )
        head_headers, head_body = head_response.split(b"\r\n\r\n", 1)
        self.assertEqual(int(head_headers.split(b"\r\n", 1)[0].split()[1]), 405)
        self.assertIn(b"Connection: close", head_headers)
        self.assertEqual(head_body, b"")

    def test_parseable_header_error_uses_json_boundary(self) -> None:
        headers = b"".join(
            f"X-Test-{index}: value\r\n".encode("ascii") for index in range(101)
        )
        raw = (
            b"GET /health/live HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            + headers
            + b"\r\n"
        )
        with self.server() as server:
            response = self.raw_exchange(server, raw)
        self.assert_raw_json_response(
            response,
            400,
            {"error": "bad_request"},
        )

    def test_partial_body_times_out_then_health_recovers(self) -> None:
        raw = (
            b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            + f"Authorization: Bearer {TOKEN}\r\n".encode()
            + b"Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{"
        )
        with self.server(read_timeout_seconds=0.2) as server:
            response = self.raw_exchange(server, raw, timeout=3)
            self.assert_raw_json_response(
                response,
                408,
                {"error": "request_timeout"},
            )
            status, payload, _ = self.call(
                server,
                "GET",
                "/health/live",
                token=None,
                content_type=None,
            )
        self.assertEqual((status, payload), (200, {"status": "live"}))

    def test_client_disconnect_does_not_traceback_or_stop_server(self) -> None:
        captured = io.StringIO()
        started = threading.Event()
        original_submit = self.app.adapter.submit

        def delayed_submit(payload):
            started.set()
            time.sleep(0.2)
            return original_submit(payload)

        body = json.dumps(first_round_request()).encode("utf-8")
        raw = (
            b"POST /internal/v1/continuity/interactions HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            + f"Authorization: Bearer {TOKEN}\r\n".encode()
            + b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
            + body
        )
        with self.server() as server, patch.object(
            self.app.adapter,
            "submit",
            side_effect=delayed_submit,
        ), patch("sys.stderr", captured):
            client = socket.create_connection(
                ("127.0.0.1", server.server_port), timeout=5
            )
            client.sendall(raw)
            self.assertTrue(started.wait(timeout=2))
            client.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_LINGER,
                struct.pack("hh", 1, 0),
            )
            client.close()
            time.sleep(0.3)
            status, payload, _ = self.call(
                server,
                "GET",
                "/health/live",
                token=None,
                content_type=None,
            )
        self.assertEqual((status, payload), (200, {"status": "live"}))
        self.assertNotIn("Traceback", captured.getvalue())
        self.assertNotIn(TOKEN, captured.getvalue())

    def test_invalid_utf8_json_nonobject_and_missing_request_id_return_400(self) -> None:
        candidates = (
            b"\xff",
            b"{broken",
            b"[]",
            b"{}",
            json.dumps({"requestId": "bad id"}).encode(),
        )
        with self.server() as server:
            for body in candidates:
                with self.subTest(body=body):
                    status, _, _ = self.call(
                        server,
                        "POST",
                        "/internal/v1/continuity/interactions",
                        body=body,
                    )
                    self.assertEqual(status, 400)

    def test_schema_error_is_http_200_machine_envelope(self) -> None:
        payload = first_round_request()
        payload["unknown"] = True
        with self.server() as server:
            status, result, _ = self.post_request(server, payload)
        self.assertEqual(status, 200)
        self.assertEqual(result["error"]["code"], "SCHEMA_INVALID")

    def test_binding_error_is_http_200_machine_envelope(self) -> None:
        payload = first_round_request()
        replace_identity(payload, "subjectId", "wrong-subject")
        with self.server() as server:
            status, result, _ = self.post_request(server, payload)
        self.assertEqual(status, 200)
        self.assertEqual(result["error"]["code"], "SUBJECT_BINDING_MISMATCH")

    def test_revision_error_is_http_200_machine_envelope(self) -> None:
        payload = first_round_request(expected_revision=9)
        with self.server() as server:
            status, result, _ = self.post_request(server, payload)
        self.assertEqual(status, 200)
        self.assertEqual(result["error"]["code"], "REVISION_CONFLICT")

    def test_idempotency_error_is_http_200_machine_envelope(self) -> None:
        with self.server() as server:
            self.post_request(server)
            changed = first_round_request("different")
            status, result, _ = self.post_request(server, changed)
        self.assertEqual(status, 200)
        self.assertEqual(result["error"]["code"], "IDEMPOTENCY_KEY_REUSED")

    def test_live_is_minimal_and_does_not_require_token(self) -> None:
        with self.server() as server:
            status, payload, _ = self.call(
                server, "GET", "/health/live", token=None, content_type=None
            )
        self.assertEqual((status, payload), (200, {"status": "live"}))

    def test_ready_is_minimal_and_does_not_require_token(self) -> None:
        with self.server() as server:
            status, payload, _ = self.call(
                server, "GET", "/health/ready", token=None, content_type=None
            )
        self.assertEqual((status, payload), (200, {"status": "ready"}))

    def test_corruption_makes_readiness_503_without_details(self) -> None:
        with self.server() as server:
            binding_path = next(self.data.rglob("subject-binding.runtime-v1.json"))
            binding_path.write_text("{}", encoding="utf-8")
            status, payload, _ = self.call(
                server, "GET", "/health/ready", token=None, content_type=None
            )
        self.assertEqual(status, 503)
        self.assertEqual(payload, {"status": "not_ready"})

    def test_completed_query_returns_nested_first_result(self) -> None:
        with self.server() as server:
            _, completed, _ = self.post_request(server)
            status, query, _ = self.call(
                server,
                "GET",
                "/internal/v1/continuity/requests/request-001",
                content_type=None,
            )
        self.assertEqual(status, 200)
        self.assertEqual(query["status"], "completed")
        self.assertEqual(query["requestHash"], completed["requestHash"])
        self.assertEqual(query["operationId"], completed["operationId"])
        self.assertEqual(query["result"], completed)

    def test_unknown_query_is_transport_404(self) -> None:
        with self.server() as server:
            status, payload, _ = self.call(
                server,
                "GET",
                "/internal/v1/continuity/requests/missing",
                content_type=None,
            )
        self.assertEqual(status, 404)
        self.assertEqual(payload, {"error": "not_found"})

    def test_recovery_required_query_is_http_200_with_null_result(self) -> None:
        now = "2026-07-30T00:00:00Z"
        request = first_round_request(request_id="request-recovery")
        self.app.ledger.save_operation(
            IntegrationOperationRecord(
                request_id="request-recovery",
                request_hash=request["requestHash"],
                operation_id="operation-recovery",
                subject_id="subject-001",
                binding_id="binding-001",
                binding_version=1,
                input_revision=0,
                consumed_observation_ids=("observation-001",),
                stage=IntegrationOperationStage.RESERVED,
                reserved_at=now,
                updated_at=now,
            )
        )
        with self.server() as server:
            status, query, _ = self.call(
                server,
                "GET",
                "/internal/v1/continuity/requests/request-recovery",
                content_type=None,
            )
        self.assertEqual(status, 200)
        self.assertEqual(query["status"], "recovery_required")
        self.assertEqual(query["operationId"], "operation-recovery")
        self.assertIsNone(query["result"])

    def test_invalid_encoded_query_id_is_400(self) -> None:
        with self.server() as server:
            status, _, _ = self.call(
                server,
                "GET",
                "/internal/v1/continuity/requests/bad%20id",
                content_type=None,
            )
        self.assertEqual(status, 400)

    def test_query_does_not_execute_domain(self) -> None:
        with self.server() as server:
            before = list(self.app.adapter.service.last_call_log)
            status, _, _ = self.call(
                server,
                "GET",
                "/internal/v1/continuity/requests/missing",
                content_type=None,
            )
        self.assertEqual(status, 404)
        self.assertEqual(self.app.adapter.service.last_call_log, before)

    def test_unknown_path_and_wrong_methods_are_distinct(self) -> None:
        with self.server() as server:
            unknown, _, _ = self.call(
                server, "GET", "/missing", token=None, content_type=None
            )
            wrong, _, _ = self.call(
                server, "GET", "/internal/v1/continuity/interactions", content_type=None
            )
            put, _, _ = self.call(server, "PUT", "/missing", body=b"")
        self.assertEqual(unknown, 404)
        self.assertEqual(wrong, 405)
        self.assertEqual(put, 405)

    def test_controlled_500_has_no_traceback_or_token(self) -> None:
        captured = io.StringIO()
        with self.server() as server, patch.object(
            self.app.adapter, "submit", side_effect=RuntimeError("private detail")
        ), patch("sys.stderr", captured):
            status, payload, _ = self.post_request(server)
        self.assertEqual(status, 500)
        self.assertEqual(payload, {"error": "internal_error"})
        self.assertNotIn("Traceback", captured.getvalue())
        self.assertNotIn("private detail", captured.getvalue())
        self.assertNotIn(TOKEN, captured.getvalue())

    def test_real_serve_process_accepts_one_http_request(self) -> None:
        port = free_port()
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["CONTINUITY_ENGINE_INTEGRATION_TOKEN"] = TOKEN
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "continuity_engine.integration_server",
                "serve",
                "--data-dir",
                str(self.data),
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                    connection.request("GET", "/health/live")
                    response = connection.getresponse()
                    response.read()
                    connection.close()
                    if response.status == 200:
                        break
                except OSError:
                    pass
                if process.poll() is not None or time.monotonic() >= deadline:
                    self.fail("formal serve process did not become live")
                time.sleep(0.05)
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            body = json.dumps(first_round_request()).encode("utf-8")
            connection.request(
                "POST",
                "/internal/v1/continuity/interactions",
                body=body,
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            payload = json.loads(response.read())
            connection.close()
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["status"], "completed")
        finally:
            process.terminate()
            stdout_bytes, stderr_bytes = process.communicate(timeout=10)
        stdout = stdout_bytes.decode("utf-8")
        stderr = stderr_bytes.decode("utf-8")
        self.assertNotIn(TOKEN, stdout + stderr)

    def test_serve_command_without_token_fails_without_initializing(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        environment.pop("CONTINUITY_ENGINE_INTEGRATION_TOKEN", None)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "continuity_engine.integration_server",
                "serve",
                "--data-dir",
                str(self.data),
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn(TOKEN.encode(), completed.stderr)


if __name__ == "__main__":
    unittest.main()
