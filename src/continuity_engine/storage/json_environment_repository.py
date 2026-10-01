"""Durable W04 attachment metadata, not an action/result or SubjectState ledger."""
from __future__ import annotations

import json
import os
import stat
import tempfile
from copy import deepcopy
from pathlib import Path

from continuity_engine.domain.action_planning import digest, identifier
from continuity_engine.domain.environment_access import Attachment, EnvironmentAccessError
from continuity_engine.domain.errors import CapabilityValidationError
from continuity_engine.storage.json_runtime_repository import file_lock, safe_root
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError


if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    _get_attributes = ctypes.WinDLL('kernel32', use_last_error=True).GetFileAttributesW
    _get_attributes.argtypes = [wintypes.LPCWSTR]
    _get_attributes.restype = wintypes.DWORD


def _path_is_link(path):
    """Read CURRENT link attributes without requesting unused file metadata.

    Windows GetFileAttributes reports the link/reparse point itself. Every
    component is still queried on every load; no path or permission is cached.
    Access/other OS failures propagate rather than becoming a missing path.
    """
    if os.name == 'nt':
        attributes = _get_attributes(str(path))
        if attributes == 0xffffffff:
            error = ctypes.get_last_error()
            if error in (2, 3):
                return False
            raise ctypes.WinError(error)
        return bool(attributes & 0x400)
    try:
        return stat.S_ISLNK(path.lstat().st_mode)
    except FileNotFoundError:
        return False


class JsonEnvironmentRepository:
    def __init__(self, root, *, subject_id, environment):
        identifier(subject_id)
        if environment not in {"TEST", "RESEARCH"}:
            raise EnvironmentAccessError("W04_PRODUCTION_NOT_READY")
        self.root = safe_root(root)
        self.subject_id, self.environment = subject_id, environment
        self.path = self.root / "environment-access" / environment.lower() / digest(subject_id)[7:] / "attachments.v1.json"
        self.lock_path = self.path.with_suffix(".lock")
        self._verified = None

    def _empty(self):
        return dict(version="w04-attachments-v1", subject_id=self.subject_id,
                    environment=self.environment, revision=0, active_host=None,
                    generation=0, attachments=[])

    def load(self):
        # The canonical root was established on construction. Recheck EVERY
        # component now, once per component rather than is_symlink + exists +
        # lstat + resolve. This is not a cached path/permission decision.
        for path in (self.path, *self.path.parents):
            if os.path.normcase(path.name) in {os.path.normcase('.continuity-data'), os.path.normcase('.assistant-data')}:
                raise RuntimeBoundaryError('RUNTIME_FORMAL_ROOT_FORBIDDEN')
            if _path_is_link(path):
                raise EnvironmentAccessError('W04_STORE_LINK_FORBIDDEN')
        repository = Path(__file__).absolute().parents[3]
        if (self.root == repository or self.root in repository.parents or repository in self.root.parents
                or (self.root / '.git').exists()):
            raise RuntimeBoundaryError('RUNTIME_REPOSITORY_ROOT_FORBIDDEN')
        if not self.path.exists():
            return self._empty()
        try:
            raw = self.path.read_bytes()
            # Parsing reuse only: reread the current bytes and paths on EVERY
            # access. Permissions, availability and binding gates are outside
            # this cache and still run for each caller. Return isolated copies.
            verified = self._verified
            if verified is not None and raw == verified[0]:
                return deepcopy(verified[1])
            envelope = json.loads(raw)
            if set(envelope) != {"document", "hash"}:
                raise ValueError()
            value = envelope["document"]
            if set(value) - {'entry_bindings', 'contact_pauses'} != set(self._empty()) or envelope["hash"] != digest(value):
                raise ValueError()
            from continuity_engine.domain.cross_entry import EntryBinding
            links = value.get('entry_bindings', [])
            if not isinstance(links, list) or len(links) > 256:
                raise ValueError()
            parsed = [EntryBinding.from_dict(row) for row in links]
            if len({row.entry_id for row in parsed}) != len(parsed) or any(
                    (row.use.subject_id, row.use.environment) != (self.subject_id, self.environment) for row in parsed):
                raise ValueError()
            pauses = value.get('contact_pauses', [])
            if not isinstance(pauses, list) or len(pauses) > 256 or len(pauses) != len(set(pauses)):
                raise ValueError()
            for user in pauses:
                identifier(user)
            if any(value[k] != self._empty()[k] for k in ("version", "subject_id", "environment")):
                raise ValueError()
            if type(value["revision"]) is not int or value["revision"] < 0 or type(value["generation"]) is not int or value["generation"] < 0:
                raise ValueError()
            if value["active_host"] is not None:
                identifier(value["active_host"])
            if not isinstance(value["attachments"], list) or len(value["attachments"]) > 256:
                raise ValueError()
            records = [Attachment.from_dict(row) for row in value["attachments"]]
            if len({row.attachment_id for row in records}) != len(records):
                raise ValueError()
            if any((row.subject_id, row.environment) != (self.subject_id, self.environment)
                   or row.generation > value["generation"] for row in records):
                raise ValueError()
            self._verified = (raw, deepcopy(value))
            return value
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, CapabilityValidationError):
            raise EnvironmentAccessError("W04_STORE_CORRUPT") from None

    def _write(self, value):
        safe_root(self.root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".w04-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump({"document": value, "hash": digest(value)}, stream, ensure_ascii=False, sort_keys=True)
                stream.write("\n")
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def transact(self, expected_revision, change):
        try:
            with file_lock(self.lock_path, wait_seconds=2):
                value = self.load()
                if value["revision"] != expected_revision:
                    raise EnvironmentAccessError("W04_REVISION_CONFLICT")
                updated = change(json.loads(json.dumps(value)))
                if updated == value:
                    return value
                if updated["revision"] != value["revision"] + 1:
                    raise EnvironmentAccessError("W04_REVISION_INVALID")
                self._write(updated)
                return updated
        except EnvironmentAccessError:
            raise
        except Exception:
            raise EnvironmentAccessError("W04_STORE_UNAVAILABLE") from None

    def register(self, attachment, *, expected_revision):
        if not isinstance(attachment, Attachment) or (attachment.subject_id, attachment.environment) != (self.subject_id, self.environment):
            raise EnvironmentAccessError("W04_ATTACHMENT_BINDING")
        def change(value):
            if value["active_host"] is None:
                value["active_host"] = attachment.host_id
                value["generation"] = attachment.generation
            if (attachment.host_id, attachment.generation) != (value["active_host"], value["generation"]):
                raise EnvironmentAccessError("W04_OLD_HOST_FENCED")
            old = next((row for row in value["attachments"] if row["attachment_id"] == attachment.attachment_id), None)
            if old is not None:
                if old == attachment.to_dict():
                    return value
                previous = Attachment.from_dict(old)
                if (not previous.enabled or previous.kind != attachment.kind or previous.host_id != attachment.host_id
                    or previous.subject_id != attachment.subject_id or previous.environment != attachment.environment
                    or previous.generation != attachment.generation
                    or previous.channel_id != attachment.channel_id or previous.device_id != attachment.device_id
                    or previous.account_id != attachment.account_id or previous.session_id != attachment.session_id
                    or previous.software_id != attachment.software_id
                    or (previous.state.value, attachment.state.value) not in {
                        ("HEARD_OF", "DISCOVERED"), ("DISCOVERED", "CONNECTED")}
                    or previous.purposes != attachment.purposes or previous.read_scopes != attachment.read_scopes):
                    raise EnvironmentAccessError("W04_ATTACHMENT_CONFLICT")
                value["attachments"].remove(old)
            if len(value["attachments"]) >= 256:
                raise EnvironmentAccessError("W04_ATTACHMENT_FULL")
            value["attachments"].append(attachment.to_dict())
            value["revision"] += 1
            return value
        return self.transact(expected_revision, change)

    def disable(self, attachment_id, *, expected_revision):
        identifier(attachment_id)
        def change(value):
            old = next((row for row in value["attachments"] if row["attachment_id"] == attachment_id), None)
            if old is None:
                raise EnvironmentAccessError("W04_ATTACHMENT_MISSING")
            if not old["enabled"]:
                return value
            old["enabled"] = False
            value["revision"] += 1
            return value
        return self.transact(expected_revision, change)

    def bind_entry(self, binding, *, expected_revision):
        """Versioned identity/ACL configuration, never messages or execution facts."""
        from continuity_engine.domain.cross_entry import EntryBinding
        if not isinstance(binding, EntryBinding) or (binding.use.subject_id, binding.use.environment) != (self.subject_id, self.environment):
            raise EnvironmentAccessError('ENTRY_CONFIG_BOUNDARY')
        def change(value):
            links = value.setdefault('entry_bindings', [])
            prior = next((row for row in links if row['entry_id'] == binding.entry_id), None)
            if prior == binding.to_dict():
                return value
            if binding.version != (prior['version'] + 1 if prior else 1):
                raise EnvironmentAccessError('ENTRY_CONFIG_VERSION')
            if prior:
                links.remove(prior)
            links.append(binding.to_dict())
            value['revision'] += 1
            return value
        return self.transact(expected_revision, change)

    def contact_pause(self, user_id, paused, *, expected_revision):
        identifier(user_id)
        if type(paused) is not bool:
            raise EnvironmentAccessError('ENTRY_PAUSE_VALUE')
        def change(value):
            users = set(value.get('contact_pauses', []))
            if (user_id in users) == paused:
                return value
            users.add(user_id) if paused else users.discard(user_id)
            value['contact_pauses'] = sorted(users)
            value['revision'] += 1
            return value
        return self.transact(expected_revision, change)

    def handoff_test(self, source_host, target_host, *, expected_revision):
        identifier(source_host); identifier(target_host)
        if source_host == target_host:
            raise EnvironmentAccessError("W04_HANDOFF_SAME_HOST")
        def change(value):
            if value["active_host"] != source_host or value["generation"] < 1:
                raise EnvironmentAccessError("W04_HANDOFF_SOURCE_INVALID")
            value["active_host"] = target_host
            value["generation"] += 1
            value["revision"] += 1
            return value
        return self.transact(expected_revision, change)
