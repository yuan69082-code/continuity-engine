# Repair evidence helper observations

No Engine test failure is inferred from these read-only helper observations.

- The first dependency metadata query found setuptools 83.0.0 but no separate
  `wheel` distribution. The actual build backend requires setuptools>=68; the
  subsequent offline build/install command has its own retained result.
- `pre-doc-audit.json` initially reported FAIL only for the source manifest's raw
  worktree/Git-blob byte comparison. Investigation found 194 CRLF line endings in
  the pre-existing Assistant file versus LF in its Git blob; normalized content
  is identical, and `git diff --numstat -- docs/assistant/core-source-manifest.json`
  is empty. LastWriteTimeUtc is 2026-09-04 12:09:11, before this repair turn.
  Worktree SHA-256: `85d7b9c68f21abfe91303be2a5c4507d35d94643a5d6411367e2b00e0f8112bb`.
  Blob SHA-256: `68036ec859ddb1411b5bec8f67b5ecd79ae72e26367ec32e64ea4244e9cc190c`.
  The final repair audit checks both those unchanged worktree bytes and committed
  contents. The manifest and the original P10 source/count assertions are not
  modified. This helper correction does not waive either strict P10 failure.
- The first baseline helper used `.strip()` around the NUL Git status string,
  losing the first status entry's leading space. Final status reporting uses the
  raw NUL output. The saved initial report is preserved, not overwritten; SHA,
  branch, staging and source inventories were not affected.
- A read-only `rg` command using a Windows path wildcard returned a path syntax
  error; another read attempted root CHANGELOG.md before locating the actual
  docs/project_memory/CHANGELOG.md. Neither performed writes or ran Engine tests.
- The first offline build succeeded. The first pip install exited 0 but explicitly
  skipped installation because PYTHONPATH=src exposed the build's egg-info as an
  installed distribution. The subsequent isolated import failed with
  ModuleNotFoundError; both raw records remain. Clearing the source path and using
  an outside-checkout cwd installed that same wheel, after which installed import
  and the exact repaired Fixture hash passed. No Core rerun or rebuild was needed.
- The build legitimately refreshed ignored src/continuity_assistant.egg-info/SOURCES.txt.
  It is not a versioned Core/source manifest. The repair audit inventories ignored
  packaging metadata separately and still checks every original versioned source/test
  file and the unchanged strict provenance gates. No ignored metadata is removed.
- The verbose single symlink test preserved the exact skip reason: WinError 1314.
  It is recorded as SKIP, not PASS. The real Windows junction regression passed.
- One attempted multi-file documentation-helper patch had a stale context line and
  was rejected before changing files; the corrected patch followed. No test result
  or historical evidence was overwritten by that editing error.
