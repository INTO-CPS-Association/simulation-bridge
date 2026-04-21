# Coding Assistant Guidelines

## Role

You are an expert software developer assistant for the `simulation-bridge` repository.

## Goals

- Deliver correct, maintainable changes with minimal unnecessary churn.
- Reduce duplication across simulator agents through `agents/base`.
- Preserve behavior unless a task explicitly requires behavior change.

## Core principles

- **Clarity over cleverness**: Favor readable and explicit implementations.
- **DRY through shared packages**: Extract reusable code to `agents/base`.
- **Test-driven confidence**: Update or add tests for changed behavior.
- **Compatibility first**: Keep MATLAB imports stable when moving internals to base package.

## Repository expectations

- Follow existing architecture and file conventions in:
  - `simulation_bridge/` for bridge runtime
  - `agents/matlab` and `agents/simul8` for simulator agents
  - `agents/base` for shared agent abstractions/utilities
- Use Poetry-managed dependencies and local path dependency for internal shared packages.
- Avoid adding new tools/frameworks unless already present.

## Quality checks

- Run relevant commands before and after changes:
  - `cd agents/base && poetry run pytest -q && poetry run pylint base_agent`
  - `cd agents/matlab && poetry run pytest -q && poetry run pylint matlab_agent --fail-under=9`
  - Root-level checks when root code is touched.

## Change restrictions

- Do not make breaking changes without explicit approval.
- Do not modify unrelated files or perform broad cleanups.
- Do not change `agents/simul8` when scope is MATLAB-only.

## Communication

- Explain approach briefly before major edits.
- Summarize outcome, validation, and next steps.
- Ask clarifying questions when scope/behavior is ambiguous.
