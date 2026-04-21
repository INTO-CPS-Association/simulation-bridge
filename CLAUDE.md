# CLAUDE.md

Repository-level behavioral guidelines for coding assistants working on `simulation-bridge`.

## 1) Think before coding

- State key assumptions when requirements are ambiguous.
- Prefer explicit tradeoffs over silent choices.
- If something is unclear and blocks correctness, ask before implementing.

## 2) Keep solutions simple and scoped

- Implement only what is requested; avoid speculative features.
- Prefer minimal abstractions unless reuse is clear and immediate.
- Keep diffs focused: each changed line should map to the task.

## 3) Make surgical changes

- Follow existing patterns, naming, and module layout.
- Do not refactor unrelated code while implementing a feature/fix.
- Remove only dead code introduced by your own edits.

## 4) Verify outcomes

- Define concrete success criteria before editing.
- Run existing tests/lint for touched areas (root and agent packages when relevant).
- Prefer failing test reproduction before bug fixes where practical.

## 5) Agent-specific conventions

- Shared agent code belongs in `agents/base` and is consumed via Poetry path dependency.
- Do not change `agents/simul8` when task explicitly asks to update MATLAB only.
- Preserve MATLAB public import paths with compatibility wrappers when extracting shared code.

## 6) Communication quality

- Briefly explain approach, then implement.
- Report what changed, why, and how it was validated.
- Call out remaining risks or follow-ups explicitly.
