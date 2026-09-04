# P10 acceptance archive first staging helper failure

- Date: 2026-09-05
- Stage: explicit Engine acceptance-archive staging
- Result: helper ERROR; staging remained empty
- Cause 1: the sandbox identity could not create `.git/index.lock` (`Permission denied`).
- Cause 2: the Python helper decoded Git's Windows console path output with the wrong code page, so its diagnostic argument list displayed Chinese filenames as mojibake.
- Effect: no file entered the index; no worktree content, history, remote or Git configuration changed.
- Resolution: use Git's native pathspecs under the existing Git-write authorization, positively naming `README.md` and `docs/project_memory`, and explicitly exclude every `p10_evidence/**/*.py` local execution helper. Then verify the complete staged list and scope before commit.

The original stderr and argument list remain in the active task tool record. This classification does not replace that raw output.
