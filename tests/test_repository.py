import json
import tempfile
import unittest
from pathlib import Path

from continuity_engine.domain.errors import StateNotFoundError, StateValidationError
from continuity_engine.domain.models import SubjectState
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


class JsonSubjectStateRepositoryTests(unittest.TestCase):
    def test_save_then_load_restores_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectStateRepository(directory)
            state = SubjectState.create("主体/一号")
            state.identity.self_concept = "continuous assistant"

            repository.save(state)
            restored = repository.load("主体/一号")

            self.assertEqual(restored.to_dict(), state.to_dict())
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)

    def test_load_missing_state_raises_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectStateRepository(directory)

            with self.assertRaises(StateNotFoundError):
                repository.load("missing")

    def test_load_rejects_mismatched_subject_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonSubjectStateRepository(directory)
            state = SubjectState.create("requested")
            repository.save(state)
            path = next(Path(directory).glob("*.json"))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["subject_id"] = "tampered"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(StateValidationError):
                repository.load("requested")


if __name__ == "__main__":
    unittest.main()

