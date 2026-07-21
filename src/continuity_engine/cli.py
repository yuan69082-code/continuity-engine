from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from continuity_engine.domain.errors import ContinuityEngineError, StateValidationError
from continuity_engine.domain.events import (
    ChangeOperation,
    Event,
    JsonValue,
    StateMutation,
    StateSection,
)
from continuity_engine.domain.models import SubjectState, utc_now
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


def _default_data_dir() -> Path:
    configured = os.environ.get("CONTINUITY_ENGINE_DATA_DIR")
    return Path(configured) if configured else Path.cwd() / ".continuity-data"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="continuity-engine",
        description="Create, read, and save SubjectState documents.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_default_data_dir(),
        help="state directory (default: .continuity-data)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a new subject state")
    init.add_argument("subject_id")
    init.add_argument("--self-concept", default="")

    show = commands.add_parser("show", help="print a saved subject state")
    show.add_argument("subject_id")

    update = commands.add_parser("update", help="update a minimal state snapshot")
    update.add_argument("subject_id")
    update.add_argument("--self-concept")
    update.add_argument("--relationship-status")
    update.add_argument("--focus", action="append", default=[])
    update.add_argument("--unfinished", action="append", default=[])
    update.add_argument("--thought", action="append", default=[])
    update.add_argument("--emotion", action="append", default=[])
    update.add_argument("--interaction-state")
    update.add_argument("--source", default="continuity_engine.cli")
    update.add_argument("--content", default="A manual SubjectState update was requested.")
    update.add_argument("--reason", default="Apply an explicit local state update.")

    touch = commands.add_parser("touch", help="record the latest interaction time")
    touch.add_argument("subject_id")

    history = commands.add_parser("history", help="print the event-driven update history")
    history.add_argument("subject_id")
    return parser


def _print_state(state: SubjectState) -> None:
    print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    service = SubjectStateService(JsonSubjectStateRepository(args.data_dir))

    try:
        if args.command == "init":
            state = service.create(args.subject_id)
            if args.self_concept:
                event = Event.create(
                    occurred_at=utc_now(),
                    source="continuity_engine.cli",
                    event_type="initialization",
                    content="An initial self-concept was supplied for the new subject.",
                    impact_scope=[StateSection.IDENTITY],
                    mutations=[
                        StateMutation(
                            field_path="identity.self_concept",
                            operation=ChangeOperation.SET,
                            value=args.self_concept,
                            reason="Initialize the subject's self-concept.",
                        )
                    ],
                    reason="Complete initialization with the supplied identity state.",
                )
                state = service.apply_event(args.subject_id, event).state
            _print_state(state)
            return 0

        if args.command == "show":
            _print_state(service.load(args.subject_id))
            return 0

        if args.command == "update":
            mutations: list[StateMutation] = []
            scope: list[StateSection] = []

            def add_mutation(
                section: StateSection,
                field_path: str,
                operation: ChangeOperation,
                value: JsonValue,
                reason: str,
            ) -> None:
                scope.append(section)
                mutations.append(
                    StateMutation(
                        field_path=field_path,
                        operation=operation,
                        value=value,
                        reason=reason,
                    )
                )

            if args.self_concept is not None:
                add_mutation(
                    StateSection.IDENTITY,
                    "identity.self_concept",
                    ChangeOperation.SET,
                    args.self_concept,
                    "The event explicitly revised the subject's self-concept.",
                )
            if args.relationship_status is not None:
                add_mutation(
                    StateSection.RELATIONSHIP,
                    "relationship.current_status",
                    ChangeOperation.SET,
                    args.relationship_status,
                    "The event explicitly changed the current relationship status.",
                )
            for focus in args.focus:
                add_mutation(
                    StateSection.CONTINUITY,
                    "continuity.current_focus",
                    ChangeOperation.APPEND,
                    focus,
                    "The event introduced a current focus.",
                )
            for unfinished in args.unfinished:
                add_mutation(
                    StateSection.CONTINUITY,
                    "continuity.unfinished_items",
                    ChangeOperation.APPEND,
                    unfinished,
                    "The event left an item unfinished.",
                )
            for thought in args.thought:
                add_mutation(
                    StateSection.INTENTIONS,
                    "intentions.emerging_thoughts",
                    ChangeOperation.APPEND,
                    thought,
                    "The event caused an emerging thought.",
                )
            for emotion in args.emotion:
                add_mutation(
                    StateSection.EMOTION_STATE,
                    "emotion_state.emotions",
                    ChangeOperation.APPEND,
                    emotion,
                    "The event affected the current emotional state.",
                )
            if args.interaction_state is not None:
                add_mutation(
                    StateSection.EMOTION_STATE,
                    "emotion_state.interaction_state",
                    ChangeOperation.SET,
                    args.interaction_state,
                    "The event changed the current interaction state.",
                )
            if not mutations:
                raise StateValidationError("update requires at least one state change option")
            event = Event.create(
                occurred_at=utc_now(),
                source=args.source,
                event_type="state_update",
                content=args.content,
                impact_scope=scope,
                mutations=mutations,
                reason=args.reason,
            )
            _print_state(service.apply_event(args.subject_id, event).state)
            return 0

        if args.command == "touch":
            _print_state(service.record_interaction(args.subject_id))
            return 0

        if args.command == "history":
            history = [record.to_dict() for record in service.get_update_history(args.subject_id)]
            print(json.dumps(history, ensure_ascii=False, indent=2))
            return 0
    except ContinuityEngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
