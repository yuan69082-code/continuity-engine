"""Bounded Windows permission probes confined to one newly-created TEST root.

No Engine runtime/source edits. Native replace and native access checks are used;
all changed attributes/DACLs are restored before this script removes its own root.
"""
from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
LABEL = "acl-access-02"
DELETE = 0x10000
DELETE_CHILD = 0x40
DACL = 4
PROTECTED_DACL = 0x80000000
UNPROTECTED_DACL = 0x20000000


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def sources():
    return {p.relative_to(ROOT).as_posix(): sha(p)
            for folder in ("src", "tests") for p in sorted((ROOT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def exception_record(exc, source=None, target=None):
    return {"type": type(exc).__name__, "errno": getattr(exc, "errno", None),
            "winerror": getattr(exc, "winerror", None),
            "sourceFilenameMatches": source is not None and getattr(exc, "filename", None) == str(source),
            "targetFilenameMatches": target is not None and getattr(exc, "filename2", None) == str(target)}


class Trustee(ctypes.Structure):
    _fields_ = [("multiple", ctypes.c_void_p), ("operation", wintypes.DWORD),
                ("form", wintypes.DWORD), ("kind", wintypes.DWORD), ("name", ctypes.c_void_p)]


class ExplicitAccess(ctypes.Structure):
    _fields_ = [("permissions", wintypes.DWORD), ("mode", wintypes.DWORD),
                ("inheritance", wintypes.DWORD), ("trustee", Trustee)]


class Windows:
    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        self.kernel.GetFileAttributesW.restype = wintypes.DWORD
        self.kernel.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        self.kernel.SetFileAttributesW.restype = wintypes.BOOL
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel.LocalFree.restype = ctypes.c_void_p
        self.advapi.GetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p)]
        self.advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
        self.advapi.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        self.advapi.SetNamedSecurityInfoW.restype = wintypes.DWORD
        self.advapi.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p,
            ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
        self.advapi.GetSecurityDescriptorControl.restype = wintypes.BOOL
        self.advapi.GetSecurityDescriptorLength.argtypes = [ctypes.c_void_p]
        self.advapi.GetSecurityDescriptorLength.restype = wintypes.DWORD
        self.advapi.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
        self.advapi.ConvertStringSidToSidW.restype = wintypes.BOOL
        self.advapi.SetEntriesInAclW.argtypes = [wintypes.ULONG, ctypes.POINTER(ExplicitAccess),
                                                ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.advapi.SetEntriesInAclW.restype = wintypes.DWORD

    def access(self, path, mask=DELETE):
        handle = self.kernel.CreateFileW(str(path), mask, 7, None, 3,
                                        0x02000000 if path.is_dir() else 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            return {"allowed": False, "winerror": ctypes.get_last_error(), "requestedAccess": mask}
        if not self.kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"allowed": True, "winerror": 0, "requestedAccess": mask}

    def attributes(self, path):
        result = self.kernel.GetFileAttributesW(str(path))
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def set_attributes(self, path, attributes):
        if not self.kernel.SetFileAttributesW(str(path), attributes):
            raise ctypes.WinError(ctypes.get_last_error())

    def security(self, path):
        dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p()
        code = self.advapi.GetNamedSecurityInfoW(str(path), 1, DACL, None, None,
                                               ctypes.byref(dacl), None, ctypes.byref(descriptor))
        if code:
            raise ctypes.WinError(code)
        control, revision = wintypes.WORD(), wintypes.DWORD()
        if not self.advapi.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision)):
            self.kernel.LocalFree(descriptor)
            raise ctypes.WinError(ctypes.get_last_error())
        return dacl, descriptor, control.value

    def security_hash(self, path):
        dacl, descriptor, control = self.security(path)
        try:
            size = self.advapi.GetSecurityDescriptorLength(descriptor)
            return hashlib.sha256(ctypes.string_at(descriptor, size)).hexdigest()
        finally:
            self.kernel.LocalFree(descriptor)

    def security_structure(self, path):
        dacl, descriptor, control = self.security(path)
        try:
            size = ctypes.c_ushort.from_address(dacl.value + 2).value
            count = ctypes.c_ushort.from_address(dacl.value + 4).value
            return {"control": control, "daclProtected": bool(control & 0x1000),
                    "daclAutoInherited": bool(control & 0x400), "aceCount": count,
                    "daclHash": hashlib.sha256(ctypes.string_at(dacl, size)).hexdigest()}
        finally:
            self.kernel.LocalFree(descriptor)

    @contextlib.contextmanager
    def deny(self, path, mask, events, relative):
        old_dacl, descriptor, control = self.security(path)
        sid, new_acl = ctypes.c_void_p(), ctypes.c_void_p()
        applied = False
        old_hash = self.security_hash(path)
        old_structure = self.security_structure(path)
        event = {"path": relative, "deniedAccess": mask, "principal": "well-known Everyone",
                 "beforeSecurityHash": old_hash, "beforeSecurity": old_structure,
                 "applied": False, "restored": False}
        events.append(event)
        try:
            if not self.advapi.ConvertStringSidToSidW("S-1-1-0", ctypes.byref(sid)):
                raise ctypes.WinError(ctypes.get_last_error())
            entry = ExplicitAccess(mask, 3, 0, Trustee(None, 0, 0, 5, sid))
            code = self.advapi.SetEntriesInAclW(1, ctypes.byref(entry), old_dacl, ctypes.byref(new_acl))
            if code:
                raise ctypes.WinError(code)
            code = self.advapi.SetNamedSecurityInfoW(str(path), 1, DACL | PROTECTED_DACL,
                                                   None, None, new_acl, None)
            if code:
                raise ctypes.WinError(code)
            applied = True
            event["applied"] = True
            event["duringSecurityHash"] = self.security_hash(path)
            yield
        finally:
            if applied:
                flags = DACL | (PROTECTED_DACL if control & 0x1000 else UNPROTECTED_DACL)
                code = self.advapi.SetNamedSecurityInfoW(str(path), 1, flags, None, None, old_dacl, None)
                event["restoreSystemCode"] = code
                if not code:
                    event["afterSecurityHash"] = self.security_hash(path)
                    event["afterSecurity"] = self.security_structure(path)
                    event["securityDescriptorBytesIdentical"] = event["afterSecurityHash"] == old_hash
                    event["restored"] = (event["afterSecurity"]["daclHash"] == old_structure["daclHash"]
                        and event["afterSecurity"]["daclProtected"] == old_structure["daclProtected"])
                if code or not event["restored"]:
                    raise RuntimeError("TEST_DACL_RESTORE_FAILED")
            for value in (new_acl, sid, descriptor):
                if value:
                    self.kernel.LocalFree(value)


def replace_observation(api, temporary, target):
    before = {"target": sha(target), "temporary": sha(temporary)}
    observation = {"beforeHashes": before,
                   "targetAttributes": api.attributes(target),
                   "temporaryAttributes": api.attributes(temporary),
                   "targetDeleteAccess": api.access(target),
                   "temporaryDeleteAccess": api.access(temporary),
                   "parentDeleteChildAccess": api.access(target.parent, DELETE_CHILD)}
    try:
        os.replace(temporary, target)
        observation["replace"] = {"succeeded": True}
    except OSError as exc:
        observation["replace"] = {"succeeded": False, **exception_record(exc, temporary, target)}
    observation["afterHashes"] = {"target": sha(target), "temporary": sha(temporary)}
    observation["unchangedOnRefusal"] = (not observation["replace"]["succeeded"] and
                                         before == observation["afterHashes"])
    return observation


def main():
    paths = {"json": OUT / (LABEL + ".json"), "stdout": OUT / (LABEL + ".stdout.log"),
             "stderr": OUT / (LABEL + ".stderr.log")}
    if any(p.exists() for p in paths.values()):
        raise RuntimeError("TEST_EVIDENCE_LABEL_ALREADY_EXISTS")
    record = {"command": [sys.executable, str(Path(__file__).resolve())], "startedAt": now(),
              "status": "STARTED", "cases": [], "sourceBefore": sources(), "cleanup": {}}
    baseline = json.loads((OUT.parent / "before.json").read_text(encoding="utf8"))
    assert len(record["sourceBefore"]) == 267
    assert record["sourceBefore"] == baseline["sourceTest"]
    paths["json"].write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    started = time.monotonic()
    code, owned = 1, None
    with paths["stdout"].open("x", encoding="utf8") as stdout, paths["stderr"].open("x", encoding="utf8") as stderr:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                if os.name != "nt":
                    raise RuntimeError("TEST_WINDOWS_REQUIRED")
                api = Windows()
                owned = Path(tempfile.mkdtemp(prefix="p18-acl-access-")).resolve()
                record["ownedTestRoot"] = str(owned)
                for name in ("normal", "target-readonly", "temporary-readonly", "target-delete-denied", "temporary-delete-denied"):
                    directory = owned / name
                    directory.mkdir()
                    target, temporary = directory / "target.json", directory / ".candidate.tmp"
                    target.write_bytes(b'{"testRevision":1}\n')
                    temporary.write_bytes(b'{"testRevision":2}\n')
                    item = {"name": name, "setup": [], "status": "STARTED"}
                    record["cases"].append(item)
                    try:
                        if name.endswith("readonly"):
                            changed = target if name == "target-readonly" else temporary
                            original = api.attributes(changed)
                            item["setup"].append({"path": changed.name, "beforeAttributes": original})
                            try:
                                api.set_attributes(changed, original | 1)
                                item["observation"] = replace_observation(api, temporary, target)
                            finally:
                                # A successfully renamed source now exists at target.
                                restored_path = changed if changed.exists() else target
                                api.set_attributes(restored_path, original)
                                item["setup"][0].update(restored=api.attributes(restored_path) == original,
                                                        afterAttributes=api.attributes(restored_path))
                        elif name.endswith("denied"):
                            changed = target if name == "target-delete-denied" else temporary
                            with api.deny(directory, DELETE_CHILD, item["setup"], name), \
                                    api.deny(changed, DELETE, item["setup"], name + "/" + changed.name):
                                item["observation"] = replace_observation(api, temporary, target)
                        else:
                            item["observation"] = replace_observation(api, temporary, target)
                        item["status"] = "OBSERVED"
                    except Exception as exc:
                        item.update(status="PROBE_ERROR", error=exception_record(exc))
                        print(json.dumps({"case": name, "error": item["error"]}), file=stderr, flush=True)
                        if any(e.get("applied") and not e.get("restored") for e in item["setup"]):
                            raise RuntimeError("TEST_CLEANUP_REQUIRES_ATTENTION") from None
                    print(json.dumps(item), flush=True)
                code = 0 if all(c["status"] == "OBSERVED" for c in record["cases"]) else 1
            except Exception as exc:
                record["error"] = exception_record(exc)
                print(json.dumps({"error": record["error"]}), file=stderr, flush=True)
            finally:
                if owned is not None:
                    safe = owned.parent == Path(tempfile.gettempdir()).resolve() and owned.name.startswith("p18-acl-access-")
                    record["cleanup"]["resolvedOwnedRootVerified"] = safe
                    restored = all(e.get("restored", True) for c in record["cases"] for e in c["setup"])
                    record["cleanup"]["allChangedPermissionsRestored"] = restored
                    if safe and restored:
                        try:
                            shutil.rmtree(owned)
                            record["cleanup"]["ownedRootRemoved"] = not owned.exists()
                        except Exception as exc:
                            record["cleanup"].update(ownedRootRemoved=False, error=exception_record(exc))
                            code = 1
                    else:
                        record["cleanup"]["ownedRootRemoved"] = False
                        code = 1
                record["sourceAfter"] = sources()
                record["sourceUnchanged"] = record["sourceBefore"] == record["sourceAfter"]
                if not record["sourceUnchanged"]:
                    code = 1
                record.update(status="COMPLETED", exitCode=code, finishedAt=now(), seconds=round(time.monotonic()-started, 3))
                record["stdoutSha256"], record["stderrSha256"] = sha(paths["stdout"]), sha(paths["stderr"])
                record["probeScriptSha256"] = sha(Path(__file__))
                paths["json"].write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    return code


def cleanup_first_run():
    label = "acl-access-01-cleanup"
    paths = {key: OUT / (label + suffix) for key, suffix in
             (("json", ".json"), ("stdout", ".stdout.log"), ("stderr", ".stderr.log"))}
    if any(p.exists() for p in paths.values()):
        raise RuntimeError("TEST_EVIDENCE_LABEL_ALREADY_EXISTS")
    original_path = OUT / "acl-access-01.json"
    original = json.loads(original_path.read_text(encoding="utf8"))
    record = {"startedAt": now(), "originalEvidenceSha256": sha(original_path),
              "sourceBefore": sources(), "status": "STARTED"}
    paths["json"].write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    code, started = 1, time.monotonic()
    with paths["stdout"].open("x", encoding="utf8") as stdout, paths["stderr"].open("x", encoding="utf8") as stderr:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                api = Windows()
                owned = Path(original["ownedTestRoot"]).resolve(strict=True)
                expected = Path("C:/Users/Administrator/AppData/Local/Temp/p18-acl-access-arj1_sv6").resolve()
                assert owned == expected and owned.parent == Path(tempfile.gettempdir()).resolve()
                assert not owned.is_symlink()
                record["ownedRoot"] = str(owned)
                records = []
                for changed, control in (("target-delete-denied", "normal"),
                        ("target-delete-denied/target.json", "target-readonly/target.json")):
                    after, untouched = api.security_structure(owned / changed), api.security_structure(owned / control)
                    item = {"restoredRelativePath": changed, "untouchedSibling": control,
                            "restoredStructure": after, "untouchedStructure": untouched,
                            "access": api.access(owned / changed, DELETE_CHILD if (owned / changed).is_dir() else DELETE)}
                    item["permissionEntriesIdentical"] = after["daclHash"] == untouched["daclHash"]
                    item["onlyAutoInheritedControlBitDiffers"] = (after["control"] ^ untouched["control"]) in (0, 0x400)
                    records.append(item)
                    assert item["permissionEntriesIdentical"] and item["onlyAutoInheritedControlBitDiffers"]
                    assert item["access"]["allowed"]
                record["permissionVerification"] = records
                record["conclusion"] = "DACL entries and effective delete access restored; descriptor inheritance metadata differs, not original byte identity."
                shutil.rmtree(owned)
                record["ownedRootRemoved"] = not owned.exists()
                assert record["ownedRootRemoved"]
                code = 0
                print(json.dumps({k: v for k, v in record.items() if not k.startswith("source")}), flush=True)
            except Exception as exc:
                record["error"] = exception_record(exc)
                print(json.dumps(record["error"]), file=stderr, flush=True)
            finally:
                record["sourceAfter"] = sources()
                record["sourceUnchanged"] = record["sourceBefore"] == record["sourceAfter"] == original["sourceBefore"]
                if not record["sourceUnchanged"]:
                    code = 1
                record.update(status="COMPLETED", exitCode=code, finishedAt=now(), seconds=round(time.monotonic()-started, 3))
                record["stdoutSha256"], record["stderrSha256"] = sha(paths["stdout"]), sha(paths["stderr"])
                record["probeScriptSha256"] = sha(Path(__file__))
                paths["json"].write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    return code


if __name__ == "__main__":
    raise SystemExit(cleanup_first_run() if sys.argv[1:] == ["--cleanup-01"] else main())
