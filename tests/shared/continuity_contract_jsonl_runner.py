from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contract_runtime import SharedContractRuntimeError, build_shared_contract_runtime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test-only JSONL bridge for the first-round continuity contract."
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    return parser


def _safe_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SharedContractRuntimeError("input line must be a JSON object")
    request_id = payload.get("requestId")
    if not isinstance(request_id, str) or not request_id.strip():
        raise SharedContractRuntimeError("input line needs a non-empty requestId")
    return payload


def _stderr(message: str) -> None:
    sys.stderr.write(f"continuity test runner: {message}\n")
    sys.stderr.flush()


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        runtime = build_shared_contract_runtime(args.data_dir)
        for physical_line in sys.stdin:
            if not physical_line.strip():
                raise SharedContractRuntimeError("blank input line")
            try:
                payload = json.loads(physical_line)
            except json.JSONDecodeError as exc:
                raise SharedContractRuntimeError("input line is not valid JSON") from exc
            result = runtime.adapter.submit(_safe_request(payload))
            encoded = json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()
        return 0
    except UnicodeDecodeError:
        _stderr("stdin is not valid UTF-8")
    except SharedContractRuntimeError as exc:
        _stderr(str(exc))
    except Exception:
        _stderr("unexpected local execution failure")
    return 2


if __name__ == "__main__":
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8", errors="strict", newline="\n", write_through=True
        )
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(
            encoding="utf-8", errors="backslashreplace", newline="\n", write_through=True
        )
    raise SystemExit(main())
