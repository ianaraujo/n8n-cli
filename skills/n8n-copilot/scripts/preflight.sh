#!/usr/bin/env bash
# PreToolUse hook for the n8n-copilot skill.
#
# Blocks n8n CLI calls when the CLI isn't installed or required env vars
# are missing. Exit 2 is the only code that blocks a PreToolUse tool call
# and feeds stderr back to Claude; any other non-zero is treated as a
# non-blocking error and the tool runs anyway. So: exit 0 on success,
# exit 2 on a problem we want Claude to see and correct.

set -u

# --- Scope: only gate commands that actually invoke `n8n`. -------------------
# PreToolUse fires for every Bash call; skip unrelated ones quickly.
if command -v jq >/dev/null 2>&1; then
  cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
  if [ -n "$cmd" ] && ! grep -qE '(^|[;&|[:space:]])n8n([[:space:]]|$)' <<<"$cmd"; then
    exit 0
  fi
fi

# --- Check 1: CLI entrypoint on PATH. ----------------------------------------
# The CLI is installed globally with `uv tool install .` (see CLAUDE.md),
# which places `n8n` on PATH. uv itself is not needed at runtime.
if ! command -v n8n >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Blocked: `n8n` CLI not found on PATH.

Install it from the n8n-cli repo:
  cd <n8n-cli>/cli && uv tool install .

Ensure uv's tool bin directory (usually ~/.local/bin) is on PATH, then retry.
EOF
  exit 2
fi

# --- Check 2: required env vars. ---------------------------------------------
missing=()
[ -z "${N8N_BASE_URL:-}" ] && missing+=(N8N_BASE_URL)
[ -z "${N8N_API_KEY:-}"  ] && missing+=(N8N_API_KEY)

if [ ${#missing[@]} -gt 0 ]; then
  {
    printf 'Blocked: missing required env var(s): %s\n\n' "${missing[*]}"
    cat <<'EOF'
Set them in your shell profile (~/.bashrc, ~/.zshrc):
  export N8N_BASE_URL=http://localhost:5678
  export N8N_API_KEY=<your-api-key>

Reload the shell, then retry.
EOF
  } >&2
  exit 2
fi

# --- Check 3: N8N_BASE_URL has a valid scheme. -------------------------------
# Catches a common misconfiguration (bare host, trailing newline, typo).
case "$N8N_BASE_URL" in
  http://*|https://*) ;;
  *)
    echo "Blocked: N8N_BASE_URL must start with http:// or https:// (got: '$N8N_BASE_URL')" >&2
    exit 2
    ;;
esac

exit 0
