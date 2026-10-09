#!/usr/bin/env bash
# PreToolUse hook (Edit|Write|MultiEdit|NotebookEdit): blocks edits to protected paths.
# Protected: results/, observations/, CLAUDE.md, .claude/ and tools/arch/.
# Everything under results/ is written only by the harness scripts; CLAUDE.md, .claude/
# and tools/arch/ belong to the author. Exit 2 denies the edit and shows the reason.
set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
[ -z "$file" ] && exit 0

rel=$(PROJECT_DIR="$PROJECT_DIR" FILE="$file" python3 - <<'EOF'
import os, sys
project = os.path.abspath(os.environ["PROJECT_DIR"])
path = os.path.abspath(os.path.expanduser(os.environ["FILE"]))
print(os.path.relpath(path, project))
EOF
)

case "$rel" in
  results/*|results|observations/*|observations|CLAUDE.md|.claude/*|tools/arch/*|tools/arch)
    echo "protect-files: '$rel' is protected. Results are written only by harness scripts;" >&2
    echo "protect-files: CLAUDE.md, .claude/ and tools/arch/ belong to the author. Tell the author instead." >&2
    exit 2
    ;;
esac
exit 0
