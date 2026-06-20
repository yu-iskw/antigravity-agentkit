# Contributing to antigravity-agentkit

Thank you for helping improve AgentKit. This document is for **repository developers**—people working on the package, CLI, docs, and CI in this repo.

End-user installation and day-to-day agent authoring are covered in [README.md](README.md) and [`docs/guides/`](docs/guides/).

## Development environment

### Prerequisites

| Tool                                    | Purpose                                                         |
| --------------------------------------- | --------------------------------------------------------------- |
| [Python 3.10+](https://www.python.org/) | Runtime (see `.python-version` for the pinned version)          |
| [uv](https://github.com/astral-sh/uv)   | Python dependencies and virtualenv                              |
| [mise](https://mise.jdx.dev/)           | Pinned CLI toolchain (Trunk, Trivy, OSV-Scanner, Grype, CodeQL) |

### Bootstrap

```bash
git clone https://github.com/yu-iskw/antigravity-agentkit.git
cd antigravity-agentkit
mise trust
make setup
```

`make setup` runs `make setup-tools` (mise install + Trunk linter setup) and `make setup-python` (`uv sync`).

Run the CLI from the project virtualenv:

```bash
uv run antigravity-agentkit --help
```

Optional Antigravity SDK for integration tests and `run`:

```bash
uv sync --extra antigravity
```

If `mise install --locked` fails because of extra tools in `~/.config/mise/config.toml`, retry with `MISE_LOCKED=false mise install` or use `make setup-tools` (which may fall back without `--locked`).

## Project layout

```text
src/antigravity_agentkit/   # Package source (import: antigravity_agentkit)
  cli.py                    # Typer CLI entrypoint
  loader.py                 # Load agent directories
  compiler.py               # Compile to runtime config
  validator.py              # Validation levels and profiles
  project.py                # AgentProject orchestration
  sdk.py                    # Optional Antigravity SDK adapters
  schema/                   # Pydantic models
  tests/                    # Colocated pytest suite
examples/                   # hello_world, skills, subagents, mcp
docs/
  guides/                   # End-user guides
  schemas/                  # JSON Schema for manifests
  rfcs/                     # Design documents
  adr/                      # Architecture decision records
dev/                        # Shell scripts invoked by Makefile
.claude/                    # Claude Code skills, agents, hooks
```

Design rationale: [RFC 0001](docs/rfcs/0001-declarative-antigravity-agentkit.md).

## Day-to-day commands

| Command                     | Description                                             |
| --------------------------- | ------------------------------------------------------- |
| `make lint`                 | Trunk check (Ruff, Pyright, Pylint, Bandit, Semgrep, …) |
| `make format`               | Trunk format + import sort (`ssort`)                    |
| `make dead-code`            | Vulture unused-code scan                                |
| `make test`                 | pytest with coverage (`dev/test_python.sh`)             |
| `make build`                | Build sdist and wheel                                   |
| `make codeql`               | Local CodeQL (`security-and-quality` suite)             |
| `make scan-vulnerabilities` | OSV-Scanner, Trivy, Grype (serial via mise)             |

Before opening a pull request, run at minimum:

```bash
make lint && make dead-code && make test && make build
```

When you change executable code paths, also run `make codeql` locally if CodeQL is available on your machine.

### CodeQL on Apple Silicon

The CodeQL bundle in `mise.lock` is x64. On Linux or macOS **ARM64**, `make setup-tools` skips the CodeQL version check. Use an x64 host or emulation for local CodeQL, or rely on the [GitHub CodeQL workflow](.github/workflows/codeql.yml) in CI.

### Trunk / mise troubleshooting

- Missing managed linter: `mise run trunk-install` or `make setup-tools`
- Keep Trivy and OSV-Scanner versions aligned between `mise.lock` and `.trunk/trunk.yaml` when bumping either

## Code style

Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) with these repo defaults:

- Type hints on public functions
- `snake_case` functions, `PascalCase` classes
- Max line length **100** (Ruff)
- Cyclomatic complexity **≤ 10** per function (Ruff `C901`)
- Imports sorted by Ruff (`I` rule) and `ssort`

Do **not** silence linters with inline suppressions (`# noqa`, `# type: ignore`, `# pylint: disable`, Trunk disable comments) unless a maintainer explicitly agrees on a policy change.

Tests live under `src/antigravity_agentkit/tests/` and must match `test_*.py`. Prefer pure, decoupled units over mocks for external I/O—see testing notes in [AGENTS.md](AGENTS.md).

## Git workflow

1. Branch from `main`
2. Use [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): description`
   - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
3. Run `make lint && make test` before pushing
4. Open a pull request with a clear summary and test plan

Commit `uv.lock` and `mise.lock` when dependencies or toolchain versions change.

## Continuous integration

| Workflow                                                   | Purpose               |
| ---------------------------------------------------------- | --------------------- |
| [trunk_check.yml](.github/workflows/trunk_check.yml)       | Lint on pull requests |
| [test.yml](.github/workflows/test.yml)                     | Python tests via uv   |
| [mise_toolchain.yml](.github/workflows/mise_toolchain.yml) | Verify mise toolchain |
| [codeql.yml](.github/workflows/codeql.yml)                 | CodeQL analysis       |

## Architecture decisions

Significant design changes should be recorded as ADRs under [`docs/adr/`](docs/adr/). Use the `manage-adr` skill or the `adr` CLI when available.

## AI-assisted development

Shared instructions for coding agents (Cursor, Claude Code, Codex, Copilot, Gemini) live in [AGENTS.md](AGENTS.md). Claude Code–specific layout is in [CLAUDE.md](CLAUDE.md) and [`.claude/`](.claude/).

Skills under `.claude/skills/` cover common loops: `lint-and-fix`, `test-and-fix`, `build-and-fix`, `codeql-fix`, `setup-dev-env`, and others listed in AGENTS.md.

## Security

- Dependency audit: `uv audit --preview-features audit` (or `uv audit` when stable)
- Vulnerability scan: `make scan-vulnerabilities` (OSV-Scanner exits **1** when findings exist—that is expected)
- Static analysis: Trunk security linters + CodeQL in CI

Report security issues responsibly through GitHub Security Advisories or by contacting the maintainers listed in [pyproject.toml](pyproject.toml).

## Publishing (maintainers)

Release automation uses scripts in `dev/`:

```bash
make build
make test-publish   # TestPyPI
make publish        # PyPI
```

Coordinate version bumps in `pyproject.toml` and changelog fragments when Changie is configured.

## Questions

- **Using AgentKit to build agents:** [docs/guides/](docs/guides/)
- **Working on this repository:** this file and [AGENTS.md](AGENTS.md)
- **Design intent:** [docs/rfcs/0001-declarative-antigravity-agentkit.md](docs/rfcs/0001-declarative-antigravity-agentkit.md)
