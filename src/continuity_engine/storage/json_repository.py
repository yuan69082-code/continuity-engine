from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import Event as ThreadEvent, RLock
from typing import Any

from continuity_engine.domain.errors import (
    EventIdentityConflictError,
    StateEvolutionError,
    StateNotFoundError,
    StateValidationError,
)
from continuity_engine.domain.events import StateUpdateRecord
from continuity_engine.domain.models import SubjectState


PERSISTENCE_FORMAT_VERSION = 1

# Shared by repository instances: protect the complete local read/validate/write
# transaction, including direct-save compatibility. No multi-process guarantee.
_STATE_WRITE_LOCK = RLock()
_RETRY_GUARD = ContextVar('state_write_retry_guard', default=None)
_INHERIT_RETRY_GUARD = object()


def _retain_cleanup_error(primary: BaseException, cleanup: BaseException) -> None:
    """Keep the pending refusal and both error histories without re-raising it.

    Raising primary inside the cleanup handler would replace its implicit
    context. Instead append cleanup to the visible chain and let the original
    exception continue unwinding. No exception text leaves this internal chain.
    """
    def graph(root):
        pending, found = [root], {}
        while pending:
            error = pending.pop()
            if error is None or id(error) in found:
                continue
            found[id(error)] = error
            pending.extend((error.__cause__, error.__context__))
        return found

    original = graph(primary)
    for error in graph(cleanup).values():
        if id(error) in original:
            continue
        # Handling cleanup during the pending refusal creates reverse context
        # edges. Their reasons remain in original; retaining the edges would
        # create a cycle when cleanup is attached below that refusal.
        if id(error.__context__) in original:
            error.__context__ = None
        if error.__cause__ is primary:
            error.__cause__ = None  # primary remains the root, never its child
    if id(cleanup) in original:
        return
    secondary = graph(cleanup)
    current, seen = primary, set()
    while id(current) not in seen:
        seen.add(id(current))
        attribute = '__cause__' if current.__cause__ is not None or current.__suppress_context__ else '__context__'
        following = getattr(current, attribute)
        if following is None:
            current.__cause__ = cleanup
            return
        if id(following) in secondary:
            # Shared reason: insert cleanup above it, not beneath it. The
            # existing reason is still reachable through cleanup's own chain.
            setattr(current, attribute, cleanup)
            return
        current = following


@contextmanager
def state_write_retry_guard(check):
    """Explicit caller authorization for bounded retries of this state write."""
    token = _RETRY_GUARD.set(check)
    try:
        yield
    finally:
        _RETRY_GUARD.reset(token)


def _replace_contended(error: OSError, path: Path) -> bool:
    """Access denied alone does not prove a retryable sharing violation."""
    if os.name != 'nt' or getattr(error, 'winerror', None) not in {5, 32, 33}:
        return False
    return _delete_access_error(path) in {32, 33}


def _delete_access_error(path: Path) -> int:
    """Observe current DELETE access without changing attributes or permissions."""
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL

    # Open DELETE access only to classify the OS refusal; no deletion is done.
    handle = create(str(path), 0x10000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        return ctypes.get_last_error()
    close(handle)
    return 0


def _file_image(path: Path):
    """Identity and content, not just a revision or a path-shaped string."""
    before = path.lstat()
    content = path.read_bytes()
    after = path.lstat()
    def identity(s):
        return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns,
                getattr(s, 'st_file_attributes', 0))
    if identity(before) != identity(after):
        raise StateEvolutionError('file changed during atomic replacement check')
    return identity(after), content


def _path_chain(path: Path):
    result = []
    for parent in (path.parent, *path.parent.parents):
        s = parent.lstat()
        if not stat.S_ISDIR(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400:
            raise StateEvolutionError('atomic replacement path is not a plain directory')
        result.append((s.st_dev, s.st_ino))
    return tuple(result)


def _replace_payload(temporary: Path, path: Path, previous: bytes | None, *,
                     retry_guard=_INHERIT_RETRY_GUARD, exhausted=None,
                     prepared_bytes=None, prepared_identity=None) -> None:
    """Retry one prepared commit under explicit current authorization only.

    Current access permits bounded attempts; it does not establish the cause of
    an earlier denial. Native replace remains the final OS permission check.
    """
    guard = _RETRY_GUARD.get() if retry_guard is _INHERIT_RETRY_GUARD else retry_guard
    if guard is None:
        os.replace(temporary, path)
        return
    temporary, path = Path(temporary).absolute(), Path(path).absolute()
    if temporary.parent != path.parent or temporary == path:
        raise StateEvolutionError('atomic replacement temporary binding is invalid')
    chain = _path_chain(path)
    prepared = _file_image(temporary)
    if ((prepared_bytes is not None and prepared[1] != prepared_bytes)
            or (prepared_identity is not None and prepared[0][:2] != prepared_identity)):
        raise StateEvolutionError('prepared temporary does not match original write')
    target = _file_image(path) if path.exists() else None
    if (target[1] if target else None) != previous:
        raise StateEvolutionError('state changed before atomic replacement')

    def current_conditions():
        if _path_chain(path) != chain or _file_image(temporary) != prepared:
            raise StateEvolutionError('temporary or path changed during atomic replacement wait')
        current = _file_image(path) if path.exists() else None
        if current != target:
            raise StateEvolutionError('state changed during atomic replacement wait')
        # Do not remove readonly attributes or bypass an actual access denial.
        for item, image in ((temporary, prepared), (path, target)):
            if image is None:
                return False
            mode, attributes = image[0][2], image[0][-1]
            if not stat.S_ISREG(mode) or attributes & (0x1 | 0x400):
                return False
            if _delete_access_error(item) not in {0, 32, 33}:
                return False
        return True

    def bound(value, expected):
        return isinstance(value, (str, bytes)) and os.path.normcase(os.path.abspath(value)) == os.path.normcase(str(expected))

    deadline = time.monotonic() + 0.25
    while True:
        try:
            os.replace(temporary, path)
            return
        except OSError as error:
            if (os.name != 'nt' or getattr(error, 'winerror', None) not in {5, 32, 33}
                    or not bound(error.filename, temporary)
                    or not bound(getattr(error, 'filename2', None), path)):
                raise
            # Retain the current contention observation; a reader may release
            # before this check. Its absence no longer forbids a bounded attempt.
            _replace_contended(error, path)
            if not current_conditions():
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if exhausted is not None:
                    exhausted(error)
                raise
            ThreadEvent().wait(min(0.025, remaining))
            guard()
            if not current_conditions():
                raise
            if time.monotonic() >= deadline:
                if exhausted is not None:
                    exhausted(error)
                raise


class JsonSubjectStateRepository:
    """Persist each SubjectState as one UTF-8 JSON document.

    Subject identifiers are hashed for filenames so identifiers can safely contain
    spaces, Unicode, or path-like characters. The original identifier remains in
    the JSON document and is verified when loading.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @staticmethod
    def _validate_subject_id(subject_id: str) -> None:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise StateValidationError("subject_id must be a non-empty string")

    def _path_for(self, subject_id: str) -> Path:
        self._validate_subject_id(subject_id)
        digest = hashlib.sha256(subject_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def exists(self, subject_id: str) -> bool:
        return self._path_for(subject_id).is_file()

    def load(self, subject_id: str) -> SubjectState:
        path = self._path_for(subject_id)
        if not path.is_file():
            raise StateNotFoundError(f"subject state not found: {subject_id}")
        state, _ = self._decode_document(self._read_payload(path, subject_id))
        if state.subject_id != subject_id:
            raise StateValidationError("persisted subject_id does not match requested subject_id")
        return state

    def save(self, state: SubjectState) -> None:
        with _STATE_WRITE_LOCK:
            path = self._path_for(state.subject_id)
            updates: list[StateUpdateRecord] | None = None
            if path.is_file():
                raw = self._read_payload(path, state.subject_id)
                if self._is_envelope(raw):
                    current, updates = self._decode_document(raw)
                    if state.to_dict() != current.to_dict():
                        raise StateEvolutionError(
                            "event-backed state cannot be changed with direct save; use save_transition"
                        )
            payload: dict[str, Any] = state.to_dict()
            self._validate_history(state, updates or [])
            if updates is not None:
                payload = self._envelope(state, updates)
            self._write_payload(path, payload)

    def save_transition(self, state: SubjectState, update: StateUpdateRecord) -> None:
        with _STATE_WRITE_LOCK:
            path = self._path_for(state.subject_id)
            if not path.is_file():
                raise StateNotFoundError(f"subject state not found: {state.subject_id}")

            current, updates = self._decode_document(self._read_payload(path, state.subject_id))
            if current.subject_id != state.subject_id or update.subject_id != state.subject_id:
                raise StateEvolutionError("transition subject identifiers do not match")
            existing = next(
                (record for record in updates if record.event.event_id == update.event.event_id),
                None,
            )
            if existing is not None:
                if existing.event.canonical_dict() != update.event.canonical_dict():
                    raise EventIdentityConflictError(
                        f"event identity conflicts with immutable history: {update.event.event_id}"
                    )
                if current.to_dict() != state.to_dict():
                    raise StateEvolutionError(
                        "idempotent event replay cannot change the persisted subject state"
                    )
                return
            if current.revision != update.before_revision:
                raise StateEvolutionError(
                    f"stale state revision: stored {current.revision}, event expected "
                    f"{update.before_revision}"
                )
            if state.revision != update.after_revision:
                raise StateEvolutionError("updated state revision does not match its update record")
            if any(record.update_id == update.update_id for record in updates):
                raise StateEvolutionError(f"duplicate update record: {update.update_id}")
            self._write_payload(path, self._envelope(state, [*updates, update]))

    def save_initial_transition(self, state: SubjectState, update: StateUpdateRecord) -> None:
        """Create once with its original Evolution record; no ACTIVE crash window."""
        with _STATE_WRITE_LOCK:
            path = self._path_for(state.subject_id)
            if path.exists():
                raise StateEvolutionError("subject identity already exists")
            self._validate_history(state, [update])
            state.to_dict()  # Validate typed internal subject bindings before any write.
            self._write_payload(path, self._envelope(state, [update]))

    def list_update_records(self, subject_id: str) -> list[StateUpdateRecord]:
        path = self._path_for(subject_id)
        if not path.is_file():
            raise StateNotFoundError(f"subject state not found: {subject_id}")
        state, updates = self._decode_document(self._read_payload(path, subject_id))
        if state.subject_id != subject_id:
            raise StateValidationError("persisted subject_id does not match requested subject_id")
        return updates

    @staticmethod
    def _is_envelope(data: Any) -> bool:
        return isinstance(data, dict) and "state" in data and "updates" in data

    @staticmethod
    def _envelope(
        state: SubjectState,
        updates: list[StateUpdateRecord],
    ) -> dict[str, Any]:
        JsonSubjectStateRepository._validate_history(state, updates)
        return {
            "persistence_format_version": PERSISTENCE_FORMAT_VERSION,
            "state": state.to_dict(),
            "updates": [record.to_dict() for record in updates],
        }

    @staticmethod
    def _decode_document(data: Any) -> tuple[SubjectState, list[StateUpdateRecord]]:
        if JsonSubjectStateRepository._is_envelope(data):
            format_version = data.get("persistence_format_version")
            if format_version != PERSISTENCE_FORMAT_VERSION:
                raise StateValidationError(
                    f"unsupported persistence format version: {format_version}"
                )
            raw_updates = data.get("updates")
            if not isinstance(raw_updates, list):
                raise StateValidationError("updates must be a list")
            state = SubjectState.from_dict(data.get("state"))
            updates = [StateUpdateRecord.from_dict(item) for item in raw_updates]
            JsonSubjectStateRepository._validate_history(state, updates)
            return (
                state,
                updates,
            )
        state = SubjectState.from_dict(data)
        JsonSubjectStateRepository._validate_history(state, [])
        return state, []

    @staticmethod
    def _validate_history(
        state: SubjectState,
        updates: list[StateUpdateRecord],
    ) -> None:
        update_ids: set[str] = set()
        event_ids: set[str] = set()
        revision = 0
        lifecycle = None
        for update in updates:
            if update.subject_id != state.subject_id:
                raise StateValidationError("update history crosses subject boundaries")
            if update.update_id in update_ids:
                raise StateValidationError("update history contains a duplicate update_id")
            if update.event.event_id in event_ids:
                raise StateValidationError("update history contains a duplicate event_id")
            if update.before_revision != revision:
                raise StateValidationError("update history revision chain is invalid")
            if update.after_revision not in (revision, revision + 1):
                raise StateValidationError("update history revision step is invalid")
            for reference in update.event.references:
                if reference.target_subject_id != state.subject_id:
                    raise StateValidationError(
                        "event history reference crosses subject boundaries"
                    )
                if reference.target_event_id not in event_ids:
                    raise StateValidationError(
                        "event history reference must target an earlier event"
                    )
            update_ids.add(update.update_id)
            event_ids.add(update.event.event_id)
            revision = update.after_revision
            lifecycle = JsonSubjectStateRepository._advance_lifecycle(state.subject_id, lifecycle, update)
        if updates and revision != state.revision:
            raise StateValidationError("update history does not reach the current state revision")
        if state.temporal.subject_lifecycle != lifecycle:
            raise StateValidationError("current lifecycle disagrees with original Evolution history")

    @staticmethod
    def _advance_lifecycle(subject_id, previous, update):
        """Validate existing lifecycle facts, without repairing or creating state."""
        from continuity_engine.domain.subject_lifecycle import LifecycleCommand, SubjectLifecycle, transition
        from continuity_engine.domain.action_planning import digest
        from continuity_engine.domain.events import ChangeOperation, EventClassification
        event=update.event
        mutations=[m for m in event.mutations if m.field_path=='temporal.subject_lifecycle']
        changes=[c for c in update.changes if c.field_path=='temporal.subject_lifecycle']
        managed=(event.event_type=='subject_lifecycle' and event.source=='subject_lifecycle_service') or event.event_id.startswith('p15-lifecycle:')
        if not mutations and not changes and not managed:
            return previous
        try:
            metadata=event.metadata
            command=LifecycleCommand.from_dict(metadata['command'])
            principal=metadata['principal_id']
            if (event.event_type!='subject_lifecycle' or event.source!='subject_lifecycle_service'
                    or command.subject_id!=subject_id or command.expected_revision!=update.before_revision
                    or metadata['environment']!=command.environment or event.reason!=command.reason
                    or event.occurred_at!=command.requested_at
                    or event.event_id!='p15-lifecycle:'+digest([subject_id,command.command_id])[7:]):
                raise ValueError('lifecycle command identity mismatch')
            if command.initiator=='SUBJECT':
                if (principal!=subject_id or mutations or changes or update.before_revision!=update.after_revision
                        or event.classification is not EventClassification.INTENTION
                        or previous is not None and previous['status']!='ACTIVE'):
                    raise ValueError('subject intent cannot change lifecycle')
                return previous
            if (len(mutations)!=1 or len(changes)!=1 or len(event.mutations)!=1
                    or mutations[0].operation is not ChangeOperation.SET
                    or changes[0].operation is not ChangeOperation.SET
                    or changes[0].before!=previous or changes[0].after!=mutations[0].value
                    or changes[0].reason!=command.reason or mutations[0].reason!=command.reason
                    or event.classification is not EventClassification.STATE_CHANGE
                    or update.after_revision!=update.before_revision+1):
                raise ValueError('lifecycle mutation/change mismatch')
            value=SubjectLifecycle.from_dict(mutations[0].value)
            if (value.subject_id!=subject_id or value.environment!=command.environment
                    or value.owner_principal_id!=principal or value.reason!=command.reason
                    or value.changed_at<command.requested_at):
                raise ValueError('lifecycle value binding mismatch')
            if previous is not None and (previous['environment']!=value.environment
                    or previous['owner_principal_id']!=principal
                    or value.changed_at<SubjectLifecycle.from_dict(previous).changed_at):
                raise ValueError('lifecycle historical binding changed')
            if command.operation=='CREATE':
                if previous is not None or update.before_revision!=0:raise ValueError('duplicate lifecycle creation')
                target='CREATE'
            else:target=transition(previous['status'] if previous else 'ACTIVE',command.operation)
            if value.status!=target:raise ValueError('lifecycle transition disagrees with command')
            return value.to_dict()
        except (ValueError,KeyError,TypeError) as exc:
            raise StateValidationError('invalid lifecycle history: '+str(exc)) from exc

    @staticmethod
    def _read_payload(path: Path, subject_id: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateValidationError(f"unable to read valid state data for: {subject_id}") from exc

    def _write_payload(self, path: Path, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        previous = path.read_bytes() if path.exists() else None

        temporary_path: Path | None = None
        primary: BaseException | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.stem}.",
                suffix=".tmp",
                dir=self.root,
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                created = os.fstat(temporary.fileno())
            _replace_payload(temporary_path, path, previous, prepared_bytes=payload.encode('utf-8'),
                             prepared_identity=(created.st_dev, created.st_ino))
        except BaseException as error:
            primary = error
            raise
        finally:
            if temporary_path is not None:
                try:
                    if temporary_path.exists():
                        temporary_path.unlink()
                except OSError as cleanup:
                    if primary is not None:
                        _retain_cleanup_error(primary, cleanup)
                    else:
                        raise
