"""Continuous Engine entry. No implicit process deadline or UI dependency.

This milestone exposes only an explicitly initialized isolated TEST profile;
production authentication, contact policy and adapters remain NOT_READY.
"""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('init-test','start','query','pause','resume','stop'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--test-mode',choices=('silence','contact','reflect'),default='silence')
    parser.add_argument('--test-clock-rate',type=float,default=1.0)
    parser.add_argument('--command-id')
    parser.add_argument('--expected-revision',type=int)
    args=parser.parse_args(argv)
    from continuity_engine.testing.p18_runtime_fixture import P18Fixture
    from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
    try:
        f=P18Fixture(args.root,initialize=args.command=='init-test',mode=args.test_mode,test_clock_rate=args.test_clock_rate)
        if args.command=='start':
            # Product lifetime is explicitly continuous. Test controllers own
            # their timeouts, send STOP, and reap only their child process.
            f.host.serve()
        elif args.command in {'pause','resume','stop'}:
            f.host.control(args.command.upper(),command_id=args.command_id or 'control:'+uuid4().hex,
                expected_revision=args.expected_revision,handle='p18-test-owner')
        print(json.dumps(f.host.query(),ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        # An OS/user process interrupt is not a persisted Owner STOP.
        print('RUNTIME_PROCESS_INTERRUPTED',file=sys.stderr);return 130
    except Exception as exc:
        code=str(exc) if isinstance(exc,RuntimeBoundaryError) else 'RUNTIME_ENTRY_UNAVAILABLE'
        if not code.startswith('RUNTIME_') or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code):
            code='RUNTIME_ENTRY_UNAVAILABLE'
        print(code,file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
