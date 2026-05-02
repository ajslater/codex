# Handoff: lint silently no-ops inside Claude worktrees

## TL;DR

When Claude Code creates a git worktree under `.claude/worktrees/<name>/`,
gitignore-style linters (`prettier`, `eslint`, `remark`) walk **upward**
from the worktree's cwd, find the **main checkout's** `.prettierignore`
(or `.remarkignore`, etc.) which correctly lists `.claude` as ignored,
and conclude that the worktree itself is ignored. They then either:

- exit with an error (`remark` — "Cannot process specified file: it's ignored"), or
- silently process **zero files** while reporting success (`prettier`, likely `eslint`).

Result: `make lint` from inside a Claude worktree only actually runs the
Python tools (ruff, basedpyright, ty, complexipy, vulture, radon, codespell)
plus the explicit-file tools (shellharden, hadolint, actionlint). The
JS/Markdown tools are no-ops. CI catches what local lint silently skips,
which makes this an irritating-but-not-dangerous bug — until it isn't.

## Empirical evidence (gathered 2026-05-02 from this worktree)

Run from `/Users/aj/Code/codex/.claude/worktrees/nervous-tereshkova-2ec2fd/`:

| Tool | Behavior | Honest? |
|---|---|---|
| `bun run remark --quiet .` | "Cannot process specified file: it's ignored", exit 1 | ✅ noisy |
| `bun run prettier --check .` | "All matched files use Prettier code style!" — but `prettier . --list-different \| wc -l` = **0** | ❌ silent |
| `bun run eslint_d --cache .` | Likely silent no-op (untested in detail; same upward-walk semantics) | ❌ |
| `uv run ruff check .` | Works correctly (root-relative `extend-exclude` in pyproject.toml) | ✅ |
| `uv run basedpyright .` | Works | ✅ |
| `uv run ty check .` | Works | ✅ |
| `shellharden`, `hadolint`, `actionlint` | Work (explicit file args) | ✅ |

Removing the `.claude` line from BOTH `.prettierignore` files (worktree's
*and* main checkout's at `~/Code/codex/.prettierignore`) makes remark
exit cleanly. Removing it from only the worktree's does NOT — confirming
the upward walk reaches the main checkout's ignore file.

Anchoring the pattern (`.claude` → `/.claude/`) does **not** help when
walking up, because the pattern is anchored to the file's directory, and
the worktree IS inside `<main>/.claude/`.

## Why this is structural

Two correct, mutually exclusive requirements:

1. From the **main** checkout, lint must skip `.claude/worktrees/*` —
   those are independent branches, possibly mid-edit and broken.
2. From inside a **worktree**, lint must process the worktree's files.

Any tool that resolves ignore patterns by walking up from cwd cannot
satisfy both as long as worktrees live under a path the project ignores.

## Options (ranked)

### Option 1 — Move worktrees outside the project tree (recommended)

Configure Claude Code's worktree base path to a location *outside*
`~/Code/codex/`. Candidates:

- `~/Code/codex-worktrees/<name>/` (sibling of project)
- `~/.claude/worktrees/codex-<name>/` (centralized under user's claude dir)

Tools running from a worktree no longer walk up into the main project's
`.claude` ignore. The worktree is still a real `git worktree` —
`gh pr create`, `git push`, etc. behave identically. **One config
change, fixes every project, doesn't touch any repo's lint configs.**

**Tradeoff:** worktree paths no longer co-locate with the project. Lose
muscle memory for `cd ~/Code/codex/.claude/worktrees/<name>/`, gain
working linters.

**Action item:** identify the exact Claude Code setting / env var that
controls the worktree base path. Possibilities to investigate:

- `~/.claude/settings.json` — search for `worktree`, `worktrees`,
  `basePath`, `worktreePath`.
- Claude Code CLI docs for a `--worktree-base` flag or
  `CLAUDE_WORKTREE_BASE` env var.
- Per-project `.claude/settings.json` override.

### Option 2 — Per-tool workarounds (not recommended)

Force each broken tool to use only the worktree's local config:

- `remark`: `--ignore-path .remarkignore` (may or may not stop the
  upward walk; needs testing).
- `prettier`: `--ignore-path .prettierignore`. Same caveat. Also doesn't
  help silent-skip — would need a wrapper that asserts `>0` files were
  processed.
- `eslint`: flat config doesn't walk up the same way; may already be OK
  if invoked correctly.
- Add a guard in `bin/lint.sh` so we notice when a tool processes 0
  files (e.g., compare against expected count from `find`).

Per-repo, fragile, doesn't scale to other projects, only papers over
what we know about. Future tools (auto-format on save, pre-commit
hooks) will hit the same blind spot.

### Option 3 — Restructure ignore patterns (not viable)

Replace `.claude` with explicit subdirs (`.claude/agents/`,
`.claude/commands/`, `.claude/skills/`, `.claude/settings*.json`, etc.)
leaving `.claude/worktrees/` un-ignored. Then walking up doesn't mark
the worktree as ignored.

But: lint from the **main** checkout would recurse into every worktree,
which is exactly what we don't want — those branches may be mid-edit.

Breaks requirement 1 above. Don't do this.

## Recommended next step

Pursue Option 1. First task: locate the Claude Code worktree-base
setting. Once known, move new worktrees there; existing in-flight
worktrees can be migrated with `git worktree move <old> <new>`.

## Files / patterns involved (for reference)

Repos with a bare `.claude` ignore pattern that contributes to the
upward-walk problem:

- `.prettierignore:5` (and `.remarkignore` symlink-to-it)
- `.gitignore:5`
- `.dockerignore:6`
- `frontend/.prettierignore:4`
- `frontend/.remarkignore` (separate file, `.claude` near top)
- `frontend/.gitignore:5`
- `cfg/eslint.config.base.js:77`

Python tools in `pyproject.toml` use root-relative globs (`**/.*`,
`**/__pycache__`) and are unaffected because their root IS the worktree
when invoked from inside it.

## Cross-link

- Discovered while finishing PR https://github.com/ajslater/codex/pull/702
  (OPDS2 belongsTo / publisher conformance fixes). Lint passed locally
  but flagged a confusing remark error; investigation revealed the
  silent-skip behavior of prettier/eslint in worktrees.
