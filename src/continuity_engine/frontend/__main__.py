from __future__ import annotations

import argparse
import os
from pathlib import Path

from continuity_engine.interfaces.http_server import create_frontend_server
from continuity_engine.interfaces.local_frontend_app import (
    create_local_frontend_application,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="continuity-frontend",
        description="Run the minimal local Continuity Engine frontend.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(
            os.environ.get("CONTINUITY_ENGINE_DATA_DIR", ".continuity-data")
        ),
    )
    parser.add_argument("--subject-id", default="demo-subject")
    parser.add_argument(
        "--initialize",
        action="store_true",
        help="explicitly create the local subject, permission, resources, and wake cycle",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    application = create_local_frontend_application(
        args.data_dir,
        subject_id=args.subject_id,
        initialize=args.initialize,
    )
    server = create_frontend_server(
        application.api,
        subject_id=application.subject_id,
        cycle_id=application.cycle_id,
        host=args.host,
        port=args.port,
    )
    actual_host, actual_port = server.server_address[:2]
    print(f"Continuity frontend: http://{actual_host}:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
