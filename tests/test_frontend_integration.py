import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from continuity_engine.domain.errors import StateNotFoundError
from continuity_engine.interfaces import (
    create_frontend_server,
    create_local_frontend_application,
)


class FrontendIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 27, 9, 0, tzinfo=timezone.utc)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = temporary.name
        self.application = create_local_frontend_application(
            self.directory,
            subject_id="frontend-subject",
            initialize=True,
            clock=lambda: self.now,
        )
        self.server = create_frontend_server(
            self.application.api,
            subject_id=self.application.subject_id,
            cycle_id=self.application.cycle_id,
            port=0,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.addCleanup(self._stop_server)

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def get_text(self, path: str) -> str:
        with urlopen(f"{self.base_url}{path}", timeout=5) as response:
            self.assertEqual(response.status, 200)
            return response.read().decode("utf-8")

    def get_json(self, path: str):
        return json.loads(self.get_text(path))

    def post_json(self, path: str, payload: dict):
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                return error.code, json.loads(error.read().decode("utf-8"))
            finally:
                error.close()

    def test_frontend_client_can_send_requests_and_render_responses(self) -> None:
        html = self.get_text("/")
        client = self.get_text("/client.js")
        application = self.get_text("/app.js")

        self.assertIn('id="message-form"', html)
        self.assertIn('id="messages"', html)
        self.assertIn("class FrontendClient", client)
        self.assertIn('this.#request("/api/chat"', client)
        self.assertIn("response.result.reply.content", application)
        self.assertIn('addMessage("assistant"', application)

    def test_http_chat_runs_event_to_action_flow_and_returns_reply(self) -> None:
        before = self.get_json(
            "/api/state?subject_id=frontend-subject&request_id=state-before"
        )
        status, response = self.post_json(
            "/api/chat",
            {
                "request_id": "frontend-chat-1",
                "user_id": "future-user-1",
                "subject_id": self.application.subject_id,
                "cycle_id": self.application.cycle_id,
                "message": "请继续当前连续性开发。",
                "expected_revision": before["current_revision"],
            },
        )

        self.assertEqual(status, 200)
        self.assertIsNone(response["error"])
        self.assertEqual(response["result"]["user_event"]["event_type"], "interaction")
        self.assertEqual(response["result"]["user_event"]["source"], "frontend")
        self.assertEqual(response["result"]["user_id"], "future-user-1")
        self.assertIsNotNone(response["result"]["wake"])
        self.assertIsNotNone(response["result"]["perception"])
        self.assertIsNotNone(response["result"]["thinking"])
        self.assertIsNotNone(response["result"]["action"])
        self.assertEqual(response["result"]["reply"]["role"], "assistant")
        self.assertTrue(response["result"]["reply"]["content"])
        self.assertEqual(response["current_revision"], 1)

        after = self.get_json(
            "/api/state?subject_id=frontend-subject&request_id=state-after"
        )
        self.assertEqual(after["current_revision"], 1)
        self.assertEqual(after["result"]["recent_events"][0]["event_id"], "frontend-interaction:frontend-chat-1")
        self.assertEqual(
            after["result"]["summary"]["last_interaction_at"],
            "2026-07-27T09:00:00Z",
        )

    def test_stale_frontend_revision_is_reported_without_new_event(self) -> None:
        status, response = self.post_json(
            "/api/chat",
            {
                "request_id": "frontend-chat-stale",
                "subject_id": self.application.subject_id,
                "cycle_id": self.application.cycle_id,
                "message": "This request is stale.",
                "expected_revision": 9,
            },
        )

        self.assertEqual(status, 409)
        self.assertEqual(response["error"]["code"], "REVISION_CONFLICT")
        self.assertEqual(response["current_revision"], 0)
        state = self.get_json(
            "/api/state?subject_id=frontend-subject&request_id=state-stale"
        )
        self.assertEqual(state["current_revision"], 0)
        self.assertEqual(state["result"]["recent_events"], [])

    def test_frontend_contains_no_subject_memory_or_personality_storage(self) -> None:
        frontend_root = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "continuity_engine"
            / "frontend"
        )
        javascript = "\n".join(
            path.read_text(encoding="utf-8")
            for path in frontend_root.glob("*.js")
        )

        for storage_api in ("localStorage", "sessionStorage", "indexedDB"):
            self.assertNotIn(storage_api, javascript)
        self.assertNotIn("apply_event", javascript)
        self.assertNotIn("StateMutation", javascript)
        self.assertNotIn("MemoryManager", javascript)
        self.assertIn("expected_revision", javascript)
        self.assertIn("subject_id", javascript)
        self.assertIn("user_id", javascript)

    def test_config_reserves_identity_and_realtime_extension_points(self) -> None:
        config = self.get_json("/api/config")
        client = self.get_text("/client.js")

        self.assertEqual(config["subject_id"], "frontend-subject")
        self.assertEqual(config["cycle_id"], "frontend-cycle:frontend-subject")
        self.assertEqual(config["realtime"], {"sse": False, "websocket": False})
        self.assertIn("subscribeEvents", client)

    def test_local_frontend_bootstrap_requires_explicit_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StateNotFoundError):
                create_local_frontend_application(
                    directory,
                    subject_id="new-subject",
                    clock=lambda: self.now,
                )
            initialized = create_local_frontend_application(
                directory,
                subject_id="new-subject",
                initialize=True,
                clock=lambda: self.now,
            )
            restored = create_local_frontend_application(
                directory,
                subject_id="new-subject",
                clock=lambda: self.now,
            )

            self.assertEqual(initialized.subject_id, restored.subject_id)
            self.assertEqual(initialized.cycle_id, restored.cycle_id)


if __name__ == "__main__":
    unittest.main()
