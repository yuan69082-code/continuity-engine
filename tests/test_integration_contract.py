from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import (
    MachineContractSchemaError,
    MachineContractValidationError,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.interfaces.integration_contract_schema import (
    FACT_SCHEMA_ID,
    OBSERVATION_SCHEMA_ID,
    REQUEST_SCHEMA_ID,
    SCHEMA_IDS,
    LocalSchemaRegistry,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_content_hash,
    calculate_request_hash,
    canonicalize_json,
)
from continuity_engine.services.integration_contract_validation import (
    MachineContractValidator,
)


CONTENT_HASH = (
    "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
)
REQUEST_HASH = (
    "sha256:ec07ad9ba66d1ffcdfa9177cd61bec1b880ad6ee99a6ec6449e732c1b86002d0"
)
BINDING_FIXTURE_HASH = (
    "sha256:c75b72194c0158a549f3fb30f04a5147ea11a4e777cb1a9cc1a54da6b93359f6"
)


def conformance_request() -> dict[str, object]:
    return {
        "contractVersion": "continuity-integration/v1.1",
        "schemaVersion": "continuity-interaction-request/first-round-v1",
        "requestId": "request-001",
        "requestHash": REQUEST_HASH,
        "requestType": "user_message",
        "identity": {
            "userId": "user-001",
            "assistantId": "assistant-001",
            "subjectId": "subject-001",
            "bindingId": "binding-001",
            "bindingVersion": 1,
        },
        "conversation": {
            "conversationId": "conversation-001",
            "messageId": "message-001",
            "messageVersionId": "message-version-001",
        },
        "expectedEngineRevision": 0,
        "platformFactPackage": {
            "schemaVersion": "vio-platform-fact-package/first-round-v1",
            "facts": [
                {
                    "schemaVersion": (
                        "vio-platform-fact/message-version-first-round-v1"
                    ),
                    "factId": "fact-001",
                    "factType": "message_version",
                    "identity": {
                        "userId": "user-001",
                        "assistantId": "assistant-001",
                        "subjectId": "subject-001",
                        "bindingId": "binding-001",
                        "bindingVersion": 1,
                    },
                    "conversationId": "conversation-001",
                    "messageId": "message-001",
                    "messageVersionId": "message-version-001",
                    "senderType": "user",
                    "content": "hello",
                    "contentHash": CONTENT_HASH,
                    "createdAt": "2026-07-30T00:00:00Z",
                }
            ],
            "observationRefs": ["observation-001"],
        },
        "observations": [
            {
                "schemaVersion": (
                    "vio-platform-observation/message-created-first-round-v1"
                ),
                "observationId": "observation-001",
                "sourceEventId": "event-001",
                "observationType": "message_created",
                "identity": {
                    "userId": "user-001",
                    "assistantId": "assistant-001",
                    "subjectId": "subject-001",
                    "bindingId": "binding-001",
                    "bindingVersion": 1,
                },
                "occurredAt": "2026-07-30T00:00:00Z",
                "observedAt": "2026-07-30T00:00:00Z",
                "messageVersionRef": {
                    "conversationId": "conversation-001",
                    "messageId": "message-001",
                    "messageVersionId": "message-version-001",
                },
            }
        ],
        "constraints": {"purpose": "reply_to_user_message"},
        "createdAt": "2026-07-30T00:00:00Z",
    }


def binding_fixture() -> dict[str, object]:
    return {
        "schemaVersion": "subject-binding/first-round-v1",
        "bindingId": "binding-001",
        "userId": "user-001",
        "assistantId": "assistant-001",
        "subjectId": "subject-001",
        "bindingVersion": 1,
        "status": "active",
        "createdAt": "2026-07-30T00:00:00Z",
        "effectiveAt": "2026-07-30T00:00:00Z",
        "replacedBindingId": None,
    }


class MachineContractPositiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LocalSchemaRegistry()
        self.validator = MachineContractValidator(self.registry)

    def test_three_schemas_are_registered_with_unique_absolute_ids(self) -> None:
        self.assertEqual(self.registry.schema_ids, SCHEMA_IDS)
        self.assertEqual(len(set(self.registry.schema_ids)), 3)
        self.assertTrue(all(item.startswith("urn:") for item in SCHEMA_IDS))

    def test_request_schema_has_the_two_exact_local_references(self) -> None:
        schema = self.registry.get_schema(REQUEST_SCHEMA_ID)
        references = {
            schema["properties"]["platformFactPackage"]["properties"]["facts"][
                "items"
            ]["$ref"],
            schema["properties"]["observations"]["items"]["$ref"],
        }
        self.assertEqual(references, {FACT_SCHEMA_ID, OBSERVATION_SCHEMA_ID})

    def test_conformance_vector_passes_the_request_schema(self) -> None:
        self.registry.validate(REQUEST_SCHEMA_ID, conformance_request())

    def test_conformance_vector_passes_all_validation(self) -> None:
        result = self.validator.validate_request(conformance_request())
        self.assertEqual(result.request_id, "request-001")
        self.assertEqual(result.observations[0].observation_type, "message_created")
        self.assertEqual(
            result.platform_fact_package.facts[0].fact_type,
            "message_version",
        )

    def test_all_three_fixed_hashes_are_independently_recalculated(self) -> None:
        request = conformance_request()
        fact = request["platformFactPackage"]["facts"][0]  # type: ignore[index]
        self.assertEqual(calculate_content_hash(fact["content"]), CONTENT_HASH)
        self.assertEqual(calculate_request_hash(request), REQUEST_HASH)
        self.assertEqual(
            calculate_binding_fixture_hash(binding_fixture()),
            BINDING_FIXTURE_HASH,
        )

    def test_typed_model_round_trips_the_conformance_vector_losslessly(self) -> None:
        request = conformance_request()
        result = self.validator.validate_request(request)
        self.assertEqual(result.to_dict(), request)

    def test_fixed_binding_fixture_validates_and_round_trips(self) -> None:
        fixture = binding_fixture()
        result = self.validator.validate_fixed_subject_binding(
            fixture,
            binding_fixture_hash=BINDING_FIXTURE_HASH,
        )
        self.assertEqual(result, SubjectBindingFixture.first_round())
        self.assertEqual(result.to_dict(), fixture)

    def test_unicode_content_produces_stable_content_and_request_hashes(self) -> None:
        request = conformance_request()
        fact = request["platformFactPackage"]["facts"][0]  # type: ignore[index]
        fact["content"] = "你好，连续性 🌱"
        fact["contentHash"] = calculate_content_hash(fact["content"])
        request["requestHash"] = calculate_request_hash(request)

        result = self.validator.validate_request(request)
        self.assertEqual(result.to_dict(), request)
        self.assertEqual(
            calculate_content_hash("你好，连续性 🌱"),
            fact["contentHash"],
        )

    def test_object_field_order_does_not_change_rfc8785_or_request_hash(self) -> None:
        request = conformance_request()
        reordered = dict(reversed(list(request.items())))
        reordered["identity"] = dict(
            reversed(list(request["identity"].items()))  # type: ignore[union-attr]
        )
        self.assertEqual(canonicalize_json(request), canonicalize_json(reordered))
        self.assertEqual(
            calculate_request_hash(request),
            calculate_request_hash(reordered),
        )

    def test_request_hash_excludes_only_the_top_level_request_hash(self) -> None:
        request = conformance_request()
        request["requestHash"] = "sha256:" + ("0" * 64)
        self.assertEqual(calculate_request_hash(request), REQUEST_HASH)


class MachineContractNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LocalSchemaRegistry()
        self.validator = MachineContractValidator(self.registry)

    def assert_request_rejected(self, request: dict[str, object]) -> None:
        with self.assertRaises(MachineContractValidationError):
            self.validator.validate_request(request)

    def test_top_level_unknown_field_is_rejected(self) -> None:
        request = conformance_request()
        request["unexpected"] = True
        self.assert_request_rejected(request)

    def test_nested_unknown_field_is_rejected(self) -> None:
        request = conformance_request()
        request["identity"]["unexpected"] = True  # type: ignore[index]
        self.assert_request_rejected(request)

    def test_empty_facts_are_rejected(self) -> None:
        request = conformance_request()
        request["platformFactPackage"]["facts"] = []  # type: ignore[index]
        self.assert_request_rejected(request)

    def test_more_than_one_fact_is_rejected(self) -> None:
        request = conformance_request()
        facts = request["platformFactPackage"]["facts"]  # type: ignore[index]
        facts.append(copy.deepcopy(facts[0]))
        self.assert_request_rejected(request)

    def test_empty_observations_are_rejected(self) -> None:
        request = conformance_request()
        request["observations"] = []
        self.assert_request_rejected(request)

    def test_more_than_one_observation_is_rejected(self) -> None:
        request = conformance_request()
        observations = request["observations"]
        observations.append(copy.deepcopy(observations[0]))  # type: ignore[union-attr]
        self.assert_request_rejected(request)

    def test_identity_mismatch_is_rejected(self) -> None:
        request = conformance_request()
        request["observations"][0]["identity"]["subjectId"] = "subject-002"  # type: ignore[index]
        self.assert_request_rejected(request)

    def test_conversation_reference_mismatch_is_rejected(self) -> None:
        request = conformance_request()
        request["observations"][0]["messageVersionRef"]["messageId"] = (  # type: ignore[index]
            "message-002"
        )
        self.assert_request_rejected(request)

    def test_fact_conversation_reference_mismatch_is_rejected(self) -> None:
        request = conformance_request()
        request["platformFactPackage"]["facts"][0]["messageVersionId"] = (  # type: ignore[index]
            "message-version-002"
        )
        self.assert_request_rejected(request)

    def test_observation_refs_mismatch_is_rejected(self) -> None:
        request = conformance_request()
        request["platformFactPackage"]["observationRefs"] = [  # type: ignore[index]
            "observation-002"
        ]
        self.assert_request_rejected(request)

    def test_message_body_in_observation_is_rejected(self) -> None:
        request = conformance_request()
        request["observations"][0]["content"] = "hello"  # type: ignore[index]
        self.assert_request_rejected(request)

    def test_incorrect_content_hash_is_rejected(self) -> None:
        request = conformance_request()
        request["platformFactPackage"]["facts"][0]["contentHash"] = (  # type: ignore[index]
            "sha256:" + ("0" * 64)
        )
        self.assert_request_rejected(request)

    def test_incorrect_request_hash_is_rejected(self) -> None:
        request = conformance_request()
        request["requestHash"] = "sha256:" + ("0" * 64)
        self.assert_request_rejected(request)

    def test_uppercase_hash_is_rejected(self) -> None:
        request = conformance_request()
        request["requestHash"] = REQUEST_HASH.upper()
        self.assert_request_rejected(request)

    def test_non_utc_or_invalid_times_are_rejected(self) -> None:
        invalid_times = (
            "2026-07-30T00:00:00",
            "2026-07-30T08:00:00+08:00",
            "2026-02-30T00:00:00Z",
            "2026-07-30T00:00:00z",
        )
        for invalid_time in invalid_times:
            with self.subTest(invalid_time=invalid_time):
                request = conformance_request()
                request["createdAt"] = invalid_time
                self.assert_request_rejected(request)

    def test_negative_expected_revision_is_rejected(self) -> None:
        request = conformance_request()
        request["expectedEngineRevision"] = -1
        self.assert_request_rejected(request)

    def test_state_write_fields_are_rejected_before_domain_conversion(self) -> None:
        forbidden_fields = (
            "mutation",
            "StateMutation",
            "stateMutation",
            "impact_scope",
            "field_path",
            "operation",
            "state_patch",
            "state_snapshot",
            "SubjectStatePatch",
            "subject_state_override",
        )
        for field in forbidden_fields:
            with self.subTest(field=field):
                request = conformance_request()
                request["constraints"][field] = {}  # type: ignore[index]
                with self.assertRaisesRegex(
                    MachineContractValidationError,
                    "state-write field is forbidden",
                ):
                    self.validator.validate_request(request)

    def test_unresolvable_reference_fails_locally_without_network_access(self) -> None:
        schema = self.registry.get_schema(REQUEST_SCHEMA_ID)
        schema["properties"]["observations"]["items"]["$ref"] = (  # type: ignore[index]
            "https://schemas.invalid.example/observation.json"
        )
        with patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(MachineContractSchemaError):
                self.registry.validate_inline(schema, conformance_request())
            urlopen.assert_not_called()

    def test_changing_any_binding_fixture_field_changes_its_hash(self) -> None:
        original = binding_fixture()
        original_hash = calculate_binding_fixture_hash(original)
        changes = {
            "schemaVersion": "subject-binding/first-round-v2",
            "bindingId": "binding-002",
            "userId": "user-002",
            "assistantId": "assistant-002",
            "subjectId": "subject-002",
            "bindingVersion": 2,
            "status": "replaced",
            "createdAt": "2026-07-30T00:00:01Z",
            "effectiveAt": "2026-07-30T00:00:01Z",
            "replacedBindingId": "binding-000",
        }
        for field, changed_value in changes.items():
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed[field] = changed_value
                self.assertNotEqual(
                    calculate_binding_fixture_hash(changed),
                    original_hash,
                )

    def test_changed_or_unknown_fixed_binding_fixture_is_rejected(self) -> None:
        changed = binding_fixture()
        changed["subjectId"] = "subject-002"
        with self.assertRaises(MachineContractValidationError):
            self.validator.validate_fixed_subject_binding(
                changed,
                binding_fixture_hash=calculate_binding_fixture_hash(changed),
            )


if __name__ == "__main__":
    unittest.main()
