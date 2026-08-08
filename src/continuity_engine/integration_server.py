from __future__ import annotations

import argparse
import sys
from pathlib import Path

from continuity_engine.interfaces.integration_config import (
    DEFAULT_INTEGRATION_PORT,
    IntegrationConfigurationError,
    IntegrationServerConfig,
)
from continuity_engine.interfaces.integration_http_server import LocalIntegrationHTTPServer
from continuity_engine.interfaces.local_integration_app import (
    LocalIntegrationInitializationError,
    build_local_integration_app,
    initialize_local_integration,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m continuity_engine.integration_server")
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="initialize formal local integration data")
    initialize.add_argument("--data-dir", type=Path, required=True)
    initialize.add_argument("--binding-file", type=Path, required=True)
    initialize.add_argument("--binding-fixture-hash", required=True)
    initialize.add_argument("--cycle-id", required=True)
    serve = commands.add_parser("serve", help="serve the loopback-only integration API")
    serve.add_argument("--data-dir", type=Path, required=True)
    serve.add_argument("--port", type=int, default=DEFAULT_INTEGRATION_PORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            initialize_local_integration(
                data_dir=args.data_dir,
                binding_file=args.binding_file,
                binding_fixture_hash=args.binding_fixture_hash,
                cycle_id=args.cycle_id,
            )
            print("Continuity Engine local integration data is initialized.")
            return 0
        config = IntegrationServerConfig.from_environment(
            data_dir=args.data_dir,
            port=args.port,
        )
        app = build_local_integration_app(config.data_dir)
        server = LocalIntegrationHTTPServer(config, app)
        try:
            print(
                f"Continuity Engine local integration listening on {config.host}:{server.server_port}.",
                flush=True,
            )
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except (IntegrationConfigurationError, LocalIntegrationInitializationError) as exc:
        print(f"integration server error: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("integration server error: local initialization failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
