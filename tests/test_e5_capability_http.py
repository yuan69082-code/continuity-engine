from __future__ import annotations

import http.client
import io
import json
import socket
import tempfile
import threading
import unittest
from contextlib import contextmanager, redirect_stderr
from pathlib import Path

from continuity_engine.domain.capability import (
    CapabilityRequiredEnvelope,
    IntegrationThinkingMode,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.interfaces.integration_config import (
    MAX_REQUEST_BODY_BYTES,
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
)
from tests.test_contract_test_adapter import first_round_request
from tests.test_e5_capability_flow import capability_result_payload


TOKEN = "formal-local-integration-token-0001"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class E5CapabilityHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "formal-data"
        fixture = SubjectBindingFixture.first_round()
        binding_file = self.root / "binding.json"
        binding_file.write_text(json.dumps(fixture.to_dict()), encoding="utf-8")
        initialize_local_integration(
            data_dir=self.data,
            binding_file=binding_file,
            binding_fixture_hash=calculate_binding_fixture_hash(fixture),
            cycle_id="formal-cycle-001",
        )
        self.app = build_local_integration_app(
            self.data,
            thinking_mode=IntegrationThinkingMode.CAPABILITY,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @contextmanager
    def server(self):
        config = IntegrationServerConfig(
            data_dir=self.data,
            service_token=TOKEN,
            port=free_port(),
            thinking_mode=IntegrationThinkingMode.CAPABILITY,
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
        payload: object | None = None,
        raw_body: bytes | None = None,
        token: str | None = TOKEN,
        content_type: str = "application/json",
    ) -> tuple[int, dict[str, object], str | None]:
        headers: dict[str, str] = {"Content-Type": content_type}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        body = raw_body if raw_body is not None else (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            if payload is not None
            else None
        )
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=5
        )
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        result = json.loads(raw.decode("utf-8")) if raw else {}
        close = response.headers.get("Connection")
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(int(response.headers["Content-Length"]), len(raw))
        status = response.status
        connection.close()
        return status, result, close

    def start_capability(self, server) -> dict[str, object]:
        status, payload, close = self.call(
            server,
            "POST",
            "/internal/v1/continuity/interactions",
            payload=first_round_request(),
        )
        self.assertEqual(status, 200)
        self.assertEqual(close, "close")
        self.assertEqual(payload["status"], "capability_required")
        return payload

    def required_model(self, payload: dict[str, object]) -> CapabilityRequiredEnvelope:
        result = self.app.adapter.query_request(str(payload["requestId"]))
        self.assertIsInstance(result, CapabilityRequiredEnvelope)
        assert isinstance(result, CapabilityRequiredEnvelope)
        return result

    def test_http_interaction_returns_capability_required(self) -> None:
        with self.server() as server:
            payload = self.start_capability(server)
        self.assertEqual(payload["schemaVersion"], "continuity-capability-required/v1")
        self.assertEqual(payload["capabilityRequest"]["capabilityType"], "model.generate")

    def test_http_capability_result_completes_original_interaction(self) -> None:
        with self.server() as server:
            required_payload = self.start_capability(server)
            required = self.required_model(required_payload)
            status, completed, close = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=capability_result_payload(required),
            )
        self.assertEqual(status, 200)
        self.assertEqual(close, "close")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["response"]["content"], "Hello from the bounded capability result.")
        self.assertFalse(completed["stateProjection"]["changed"])

    def test_query_transitions_from_required_to_completed(self) -> None:
        with self.server() as server:
            required_payload = self.start_capability(server)
            status, query, _ = self.call(
                server,
                "GET",
                "/internal/v1/continuity/requests/request-001",
            )
            self.assertEqual((status, query["status"]), (200, "capability_required"))
            required = self.required_model(required_payload)
            self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=capability_result_payload(required),
            )
            status, query, _ = self.call(
                server,
                "GET",
                "/internal/v1/continuity/requests/request-001",
            )
        self.assertEqual((status, query["status"]), (200, "completed"))

    def test_capability_result_requires_bearer_token(self) -> None:
        with self.server() as server:
            required_payload = self.start_capability(server)
            required = self.required_model(required_payload)
            status, payload, close = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=capability_result_payload(required),
                token=None,
            )
        self.assertEqual((status, payload, close), (401, {"error": "unauthorized"}, "close"))

    def test_invalid_result_json_shape_is_400(self) -> None:
        with self.server() as server:
            self.start_capability(server)
            status, payload, close = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload={"requestId": "request-001"},
            )
        self.assertEqual((status, payload, close), (400, {"error": "capability_result_invalid"}, "close"))

    def test_blank_success_is_controlled_400_without_durable_side_effects(
        self,
    ) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.server() as server:
            required_payload = self.start_capability(server)
            required = self.required_model(required_payload)
            operation_before = self.app.ledger.load_operation(required.request_id)
            status, body, close = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=capability_result_payload(required, response="   "),
            )
            self.assertEqual(
                self.app.ledger.load_operation(required.request_id),
                operation_before,
            )
            self.assertEqual(
                self.app.ledger.list_capability_attempts(
                    required.capability_request.capability_request_id
                ),
                [],
            )
            self.assertIsNone(self.app.ledger.load_completed(required.request_id))
            valid_status, completed, _ = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=capability_result_payload(
                    required,
                    result_id="capability-result-after-blank",
                ),
            )

        self.assertEqual(
            (status, body, close),
            (400, {"error": "capability_result_invalid"}, "close"),
        )
        self.assertEqual(valid_status, 200)
        self.assertEqual(completed["status"], "completed")
        attempts = self.app.ledger.list_capability_attempts(
            required.capability_request.capability_request_id
        )
        self.assertEqual(len(attempts), 1)
        self.assertEqual(
            attempts[0].result.capability_result_id,
            "capability-result-after-blank",
        )
        self.assertNotEqual(
            self.app.ledger.load_operation(required.request_id),
            operation_before,
        )
        self.assertEqual(self.app.subject_states.load("subject-001").revision, 0)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_unknown_capability_request_is_404(self) -> None:
        with self.server() as server:
            required_payload = self.start_capability(server)
            required = self.required_model(required_payload)
            payload = capability_result_payload(required)
            payload["requestId"] = "missing-request"
            status, body, _ = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=payload,
            )
        self.assertEqual((status, body), (404, {"error": "capability_request_not_found"}))

    def test_result_id_conflict_is_409(self) -> None:
        with self.server() as server:
            required_payload = self.start_capability(server)
            required = self.required_model(required_payload)
            self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=capability_result_payload(required),
            )
            status, body, _ = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload=capability_result_payload(required, response="different"),
            )
        self.assertEqual((status, body), (409, {"error": "capability_result_conflict"}))

    def test_wrong_method_and_path_use_json_transport_errors(self) -> None:
        with self.server() as server:
            method_status, method_body, method_close = self.call(
                server,
                "GET",
                "/internal/v1/continuity/capability-results",
            )
            path_status, path_body, path_close = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-result",
                payload={"requestId": "request-001"},
            )
        self.assertEqual((method_status, method_body, method_close), (405, {"error": "method_not_allowed"}, "close"))
        self.assertEqual((path_status, path_body, path_close), (404, {"error": "not_found"}, "close"))

    def test_content_type_boundary_is_shared_with_e4(self) -> None:
        with self.server() as server:
            status, body, close = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                payload={"requestId": "request-001"},
                content_type="text/plain",
            )
        self.assertEqual((status, body, close), (415, {"error": "unsupported_media_type"}, "close"))

    def test_invalid_json_is_a_controlled_400(self) -> None:
        with self.server() as server:
            status, body, close = self.call(
                server,
                "POST",
                "/internal/v1/continuity/capability-results",
                raw_body=b"{broken",
            )
        self.assertEqual((status, body, close), (400, {"error": "invalid_json"}, "close"))

    def test_oversized_capability_result_is_rejected_before_parsing(self) -> None:
        stderr = io.StringIO()
        original_submit = self.app.adapter.submit_capability_result
        submit_calls = 0

        def guarded_submit(payload):
            nonlocal submit_calls
            submit_calls += 1
            return original_submit(payload)

        self.app.adapter.submit_capability_result = guarded_submit
        try:
            with redirect_stderr(stderr), self.server() as server:
                oversized = b"x" * (MAX_REQUEST_BODY_BYTES + 1)
                for attempt in range(3):
                    with self.subTest(complete_request=attempt):
                        status, body, close = self.call(
                            server,
                            "POST",
                            "/internal/v1/continuity/capability-results",
                            raw_body=oversized,
                        )
                        self.assertEqual(
                            (status, body, close),
                            (413, {"error": "payload_too_large"}, "close"),
                        )

                with socket.create_connection(
                    ("127.0.0.1", server.server_port), timeout=5
                ) as client:
                    request = (
                        "POST /internal/v1/continuity/capability-results HTTP/1.1\r\n"
                        "Host: 127.0.0.1\r\n"
                        f"Authorization: Bearer {TOKEN}\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {MAX_REQUEST_BODY_BYTES + 1}\r\n"
                        "\r\n"
                    ).encode("ascii")
                    client.sendall(request + b"partial")
                    client.shutdown(socket.SHUT_WR)
                    chunks: list[bytes] = []
                    while True:
                        chunk = client.recv(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    partial_response = b"".join(chunks)

                partial_head, partial_body = partial_response.split(b"\r\n\r\n", 1)
                self.assertEqual(
                    int(partial_head.split(b"\r\n", 1)[0].split()[1]),
                    413,
                )
                self.assertIn(b"Connection: close", partial_head)
                self.assertIn(b"Cache-Control: no-store", partial_head)
                self.assertIn(
                    f"Content-Length: {len(partial_body)}".encode("ascii"),
                    partial_head,
                )
                self.assertEqual(
                    json.loads(partial_body.decode("utf-8")),
                    {"error": "payload_too_large"},
                )

                health_status, health_body, health_close = self.call(
                    server,
                    "GET",
                    "/health/live",
                )
        finally:
            self.app.adapter.submit_capability_result = original_submit

        self.assertEqual(submit_calls, 0)
        self.assertEqual(
            (health_status, health_body, health_close),
            (200, {"status": "live"}, "close"),
        )
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_configuration_rejects_untyped_thinking_mode(self) -> None:
        with self.assertRaises(IntegrationConfigurationError):
            IntegrationServerConfig(
                data_dir=self.data,
                service_token=TOKEN,
                thinking_mode="capability",  # type: ignore[arg-type]
            )

    def test_http_server_rejects_app_mode_mismatch(self) -> None:
        config = IntegrationServerConfig(
            data_dir=self.data,
            service_token=TOKEN,
            port=free_port(),
            thinking_mode=IntegrationThinkingMode.DETERMINISTIC,
        )
        with self.assertRaises(IntegrationConfigurationError):
            LocalIntegrationHTTPServer(config, self.app)


if __name__ == "__main__":
    unittest.main()
