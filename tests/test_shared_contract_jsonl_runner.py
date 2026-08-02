from __future__ import annotations

import copy
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from continuity_engine.services.integration_contract_hashing import (
    calculate_content_hash,
    calculate_request_hash,
)
from continuity_engine.storage.json_integration_repository import (
    JsonIntegrationResultLedger,
)
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


ROOT = Path(__file__).resolve().parents[1]
MODULE = "tests.shared.continuity_contract_jsonl_runner"


def request(
    content: str = "hello",
    *,
    request_id: str = "request-001",
    expected_revision: int = 0,
) -> dict[str, object]:
    identity = {
        "userId": "user-001",
        "assistantId": "assistant-001",
        "subjectId": "subject-001",
        "bindingId": "binding-001",
        "bindingVersion": 1,
    }
    conversation = {
        "conversationId": "conversation-001",
        "messageId": "message-001",
        "messageVersionId": "message-version-001",
    }
    value: dict[str, object] = {
        "contractVersion": "continuity-integration/v1.1",
        "schemaVersion": "continuity-interaction-request/first-round-v1",
        "requestId": request_id,
        "requestHash": "sha256:" + ("0" * 64),
        "requestType": "user_message",
        "identity": identity,
        "conversation": conversation,
        "expectedEngineRevision": expected_revision,
        "platformFactPackage": {
            "schemaVersion": "vio-platform-fact-package/first-round-v1",
            "facts": [
                {
                    "schemaVersion": "vio-platform-fact/message-version-first-round-v1",
                    "factId": f"fact-{request_id}",
                    "factType": "message_version",
                    "identity": dict(identity),
                    "conversationId": "conversation-001",
                    "messageId": "message-001",
                    "messageVersionId": "message-version-001",
                    "senderType": "user",
                    "content": content,
                    "contentHash": calculate_content_hash(content),
                    "createdAt": "2026-07-30T00:00:00Z",
                }
            ],
            "observationRefs": [f"observation-{request_id}"],
        },
        "observations": [
            {
                "schemaVersion": "vio-platform-observation/message-created-first-round-v1",
                "observationId": f"observation-{request_id}",
                "sourceEventId": f"vio-event-{request_id}",
                "observationType": "message_created",
                "identity": dict(identity),
                "occurredAt": "2026-07-30T00:00:00Z",
                "observedAt": "2026-07-30T00:00:00Z",
                "messageVersionRef": dict(conversation),
            }
        ],
        "constraints": {"purpose": "reply_to_user_message"},
        "createdAt": "2026-07-30T00:00:00Z",
    }
    value["requestHash"] = calculate_request_hash(value)
    return value


def replace_identity(value: dict[str, object], field: str, replacement: object) -> None:
    value["identity"][field] = replacement  # type: ignore[index]
    value["observations"][0]["identity"][field] = replacement  # type: ignore[index]
    value["platformFactPackage"]["facts"][0]["identity"][field] = replacement  # type: ignore[index]
    value["requestHash"] = calculate_request_hash(value)


class RunnerHarness:
    @staticmethod
    def environment(extra_python_path: Path | None = None) -> dict[str, str]:
        env = os.environ.copy()
        paths = [str(ROOT / "src"), str(ROOT)]
        if extra_python_path is not None:
            paths.insert(0, str(extra_python_path))
        if env.get("PYTHONPATH"):
            paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(paths)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    @classmethod
    def run(
        cls,
        data_dir: Path,
        lines: list[object] | None = None,
        *,
        raw: bytes | None = None,
        extra_python_path: Path | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        if raw is None:
            raw = b"".join(
                json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                + b"\n"
                for item in (lines or [])
            )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                MODULE,
                "--data-dir",
                str(data_dir),
            ],
            cwd=ROOT,
            env=cls.environment(extra_python_path),
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )

    @classmethod
    def popen(cls, data_dir: Path) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [sys.executable, "-m", MODULE, "--data-dir", str(data_dir)],
            cwd=ROOT,
            env=cls.environment(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


def decoded_lines(completed: subprocess.CompletedProcess[bytes]) -> list[dict[str, object]]:
    return [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines()]


class SharedContractJsonlRunnerTests(unittest.TestCase):
    def test_one_line_success_is_compact_utf8_jsonl_without_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = RunnerHarness.run(Path(directory), [request()])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stderr, b"")
            self.assertEqual(completed.stdout.count(b"\n"), 1)
            self.assertNotIn(b"\r", completed.stdout)
            result = decoded_lines(completed)[0]
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["requestId"], "request-001")
            self.assertEqual(result["stateProjection"]["changed"], False)  # type: ignore[index]
            self.assertTrue(result["response"]["content"])  # type: ignore[index]

    def test_multiple_lines_preserve_order_and_flush_before_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            process = RunnerHarness.popen(Path(directory))
            assert process.stdin is not None and process.stdout is not None
            first = request(request_id="request-flush-一")
            process.stdin.write(
                json.dumps(first, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                + b"\n"
            )
            process.stdin.flush()
            output: queue.Queue[bytes] = queue.Queue()
            reader = threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True)
            reader.start()
            first_line = output.get(timeout=10)
            self.assertIsNone(process.poll(), "runner exited instead of waiting for another line")
            self.assertEqual(json.loads(first_line)["requestId"], "request-flush-一")
            second = request(request_id="request-flush-二")
            process.stdin.write(
                json.dumps(second, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                + b"\n"
            )
            process.stdin.close()
            second_line = process.stdout.readline()
            process.wait(timeout=20)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(json.loads(second_line)["requestId"], "request-flush-二")
            process.stdout.close()
            assert process.stderr is not None
            process.stderr.close()

    def test_non_ascii_request_id_and_content_round_trip_as_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = RunnerHarness.run(
                Path(directory),
                [request("你好，连续性 🌱", request_id="请求-中文-001")],
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("请求-中文-001".encode("utf-8"), completed.stdout)
            self.assertNotIn(b"\\u8bf7", completed.stdout)
            self.assertEqual(decoded_lines(completed)[0]["requestId"], "请求-中文-001")

    def test_changed_false_and_true_use_real_evolution_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unchanged = RunnerHarness.run(root, [request()])
            self.assertEqual(unchanged.returncode, 0, unchanged.stderr)
            plain = decoded_lines(unchanged)[0]["stateProjection"]
            self.assertEqual(plain["currentRevision"], 0)  # type: ignore[index]
            self.assertFalse(plain["changed"])  # type: ignore[index]
            self.assertIsNone(plain["engineUpdateId"])  # type: ignore[index]

            changed_request = request(
                "remember continuity test focus",
                request_id="request-change-001",
                expected_revision=0,
            )
            changed = RunnerHarness.run(root, [changed_request])
            self.assertEqual(changed.returncode, 0, changed.stderr)
            projection = decoded_lines(changed)[0]["stateProjection"]
            self.assertTrue(projection["changed"])  # type: ignore[index]
            self.assertEqual(projection["previousRevision"], 0)  # type: ignore[index]
            self.assertEqual(projection["currentRevision"], 1)  # type: ignore[index]
            repository = JsonSubjectStateRepository(root / "subject-state")
            updates = repository.list_update_records("subject-001")
            self.assertEqual(len(updates), 1)
            self.assertEqual(projection["engineUpdateId"], updates[0].update_id)  # type: ignore[index]
            self.assertNotEqual(updates[0].event.event_id, "vio-event-request-change-001")

    def test_same_process_replay_is_byte_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            value = request("remember continuity test focus")
            completed = RunnerHarness.run(Path(directory), [value, value])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            lines = completed.stdout.splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0], lines[1])
            state = JsonSubjectStateRepository(Path(directory) / "subject-state").load(
                "subject-001"
            )
            self.assertEqual(state.revision, 1)

    def test_restart_replay_and_new_request_have_unique_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_request = request("remember continuity test focus", request_id="request-A")
            first_run = RunnerHarness.run(root, [first_request])
            self.assertEqual(first_run.returncode, 0, first_run.stderr)
            first = decoded_lines(first_run)[0]
            second_request = request(request_id="request-B", expected_revision=1)
            restarted = RunnerHarness.run(root, [first_request, second_request])
            self.assertEqual(restarted.returncode, 0, restarted.stderr)
            replay, second = decoded_lines(restarted)
            self.assertEqual(replay, first)
            self.assertNotEqual(first["operationId"], second["operationId"])
            self.assertNotEqual(first["response"]["responseId"], second["response"]["responseId"])  # type: ignore[index]
            repository = JsonSubjectStateRepository(root / "subject-state")
            self.assertEqual(repository.load("subject-001").revision, 1)
            self.assertEqual(len(repository.list_update_records("subject-001")), 1)

    def test_four_protocol_errors_are_exact_and_do_not_terminate_stream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = request(request_id="request-valid")
            schema_invalid = copy.deepcopy(request(request_id="request-schema"))
            schema_invalid["unknown"] = True
            binding_invalid = copy.deepcopy(request(request_id="request-binding"))
            replace_identity(binding_invalid, "subjectId", "subject-wrong")
            revision_invalid = request(request_id="request-revision", expected_revision=9)
            first = request(request_id="request-idempotent")
            reused = request("different", request_id="request-idempotent")
            completed = RunnerHarness.run(
                root,
                [schema_invalid, valid, binding_invalid, revision_invalid, first, reused],
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            results = decoded_lines(completed)
            self.assertEqual(
                [item["status"] for item in results],
                ["failed_terminal", "completed", "failed_terminal", "failed_terminal", "completed", "failed_terminal"],
            )
            errors = [results[index]["error"] for index in (0, 2, 3, 5)]
            self.assertEqual(
                [item["code"] for item in errors],  # type: ignore[index]
                ["SCHEMA_INVALID", "SUBJECT_BINDING_MISMATCH", "REVISION_CONFLICT", "IDEMPOTENCY_KEY_REUSED"],
            )
            self.assertEqual(errors[2]["retryClass"], "reassemble")  # type: ignore[index]
            self.assertEqual(errors[3]["retryClass"], "never")  # type: ignore[index]
            self.assertIsNone(errors[1]["currentEngineRevision"])  # type: ignore[index]
            self.assertEqual(errors[2]["currentEngineRevision"], 0)  # type: ignore[index]

    def test_declared_request_hash_is_validated_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            value = request()
            value["requestHash"] = "sha256:" + ("f" * 64)
            completed = RunnerHarness.run(Path(directory), [value])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = decoded_lines(completed)[0]
            self.assertEqual(result["error"]["code"], "SCHEMA_INVALID")  # type: ignore[index]

    def test_local_input_faults_use_stderr_nonzero_and_no_envelope(self) -> None:
        cases = [b"\n", b"{not-json}\n", b"\xff\n", b'{"notRequest":true}\n']
        for raw in cases:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                completed = RunnerHarness.run(Path(directory), raw=raw)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(completed.stdout, b"")
                self.assertTrue(completed.stderr)
                self.assertNotIn(b"Traceback", completed.stderr)

    def test_prior_output_survives_a_later_local_storage_fault(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = RunnerHarness.popen(root)
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(json.dumps(request()).encode("utf-8") + b"\n")
            process.stdin.flush()
            first = process.stdout.readline()
            self.assertEqual(json.loads(first)["status"], "completed")
            ledger = JsonIntegrationResultLedger(root)
            ledger.path.write_text("{corrupt", encoding="utf-8")
            process.stdin.write(
                json.dumps(request(request_id="request-after-corruption")).encode("utf-8")
                + b"\n"
            )
            process.stdin.close()
            process.wait(timeout=20)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(process.stdout.read(), b"")
            self.assertNotIn(b"Traceback", process.stderr.read())  # type: ignore[union-attr]
            process.stdout.close()
            process.stderr.close()  # type: ignore[union-attr]

    def test_complete_fixture_is_loaded_without_reinitialization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialized = RunnerHarness.run(root)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            restarted = RunnerHarness.run(root)
            self.assertEqual(restarted.returncode, 0, restarted.stderr)
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_partial_and_corrupt_directories_fail_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "partial.json"
            marker.write_text("{}", encoding="utf-8")
            completed = RunnerHarness.run(root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(completed.stdout, b"")
            self.assertEqual(list(root.rglob("*")), [marker])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(RunnerHarness.run(root).returncode, 0)
            ledger = JsonIntegrationResultLedger(root)
            ledger.path.parent.mkdir(parents=True, exist_ok=True)
            ledger.path.write_text("not-json", encoding="utf-8")
            completed = RunnerHarness.run(root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(ledger.path.read_text(encoding="utf-8"), "not-json")

    def test_each_missing_fixed_fixture_component_fails_without_repair(self) -> None:
        for component in ("state", "binding", "cycle"):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.assertEqual(RunnerHarness.run(root).returncode, 0)
                if component == "state":
                    target = next((root / "subject-state").glob("*.json"))
                elif component == "binding":
                    target = JsonIntegrationResultLedger(root).path.parent / "subject-binding.first-round-v1.json"
                else:
                    target = next((root / "awakening" / "cycles").glob("*.json"))
                target.unlink()
                completed = RunnerHarness.run(root)
                self.assertNotEqual(completed.returncode, 0)
                self.assertFalse(target.exists())

    def test_state_and_ledger_contradiction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changed = RunnerHarness.run(
                root,
                [request("remember continuity test focus")],
            )
            self.assertEqual(changed.returncode, 0, changed.stderr)
            state_path = next((root / "subject-state").glob("*.json"))
            document = json.loads(state_path.read_text(encoding="utf-8"))
            document["state"]["revision"] = 0
            state_path.write_text(json.dumps(document), encoding="utf-8")
            restarted = RunnerHarness.run(root)
            self.assertNotEqual(restarted.returncode, 0)
            self.assertEqual(restarted.stdout, b"")

    def test_data_dir_is_required_and_production_named_directory_is_rejected(self) -> None:
        missing = subprocess.run(
            [sys.executable, "-m", MODULE],
            cwd=ROOT,
            env=RunnerHarness.environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertEqual(missing.stdout, b"")
        with tempfile.TemporaryDirectory() as directory:
            forbidden = RunnerHarness.run(Path(directory) / ".continuity-data")
            self.assertNotEqual(forbidden.returncode, 0)
            self.assertEqual(forbidden.stdout, b"")

    def test_runner_does_not_use_network_or_legacy_entry_points(self) -> None:
        with tempfile.TemporaryDirectory() as support, tempfile.TemporaryDirectory() as data:
            sitecustomize = Path(support) / "sitecustomize.py"
            sitecustomize.write_text(
                """
import socket
def forbidden(*args, **kwargs):
    raise AssertionError('forbidden old entry point or network access')
socket.create_connection = forbidden
socket.socket.connect = forbidden
from continuity_engine.interfaces.api_service import APIService
from continuity_engine.services.user_interaction_service import UserInteractionService
from continuity_engine.interfaces import http_server
APIService.submit_message = forbidden
UserInteractionService.handle_message = forbidden
http_server.create_frontend_server = forbidden
""".lstrip(),
                encoding="utf-8",
            )
            completed = RunnerHarness.run(
                Path(data),
                [request()],
                extra_python_path=Path(support),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(decoded_lines(completed)[0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
