# P10 acceptance audit first-attempt helper failure

- Date: 2026-09-05
- Stage: documentation-only acceptance audit
- Result: helper ERROR before the audit report was written
- Exit code: 1
- Cause: the sandbox identity could read the Assistant files but Git rejected `rev-parse` with `detected dubious ownership` because the repository belongs to the desktop user.
- Effect: no repository content, Git config, staging area, commit or remote was changed by this attempt. This is not a Core, source, test, CI or acceptance failure.
- Resolution for the next audit: pass `-c safe.directory=C:/Users/Administrator/Documents/continuity-assistant` to the two read-only Git invocations only. Do not change global or repository configuration.

The original command output remains in the active task tool record. This note preserves the classification and does not replace that output.
