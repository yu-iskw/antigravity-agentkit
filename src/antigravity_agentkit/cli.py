"""Typer CLI for Antigravity AgentKit."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console

from antigravity_agentkit.compiler import compile_agent_config
from antigravity_agentkit.deploy import (
    build_source_package,
    deploy,
    load_deployment,
)
from antigravity_agentkit.evals import assert_evals_passed, run_evals
from antigravity_agentkit.exceptions import AgentKitError, ValidationError
from antigravity_agentkit.operator_auth import IMPERSONATE_ENV
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.registry import (
    build_agent_registry_metadata,
    build_mcp_server_metadata,
    publish_skill,
)
from antigravity_agentkit.runtime import RuntimeAgent
from antigravity_agentkit.schema.agent import AgentManifest
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.validator import validate_deployment, validate_project

app = typer.Typer(
    name="antigravity-agentkit",
    help=(
        "Antigravity AgentKit — declarative agent compiler and governance layer.\n\n"
        "Implement: init, validate, compile, run, eval\n"
        "Ship: package, deploy, register (require deployment.yaml)"
    ),
    no_args_is_help=True,
)
console = Console()


class _LevelChoice(str, Enum):
    SYNTAX = "syntax"
    SCHEMA = "schema"
    SECURITY = "security"
    CLOUD = "cloud"
    FULL = "full"


class _ProfileChoice(str, Enum):
    DEV_OPEN = "dev-open"
    DEV_RESTRICTED = "dev-restricted"
    PROD_READONLY = "prod-readonly"
    PROD_HUMAN_APPROVAL = "prod-human-approval"
    PROD_LOCKED = "prod-locked"


def _resolve_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _print_plain(text: str) -> None:
    """Print agent or user text without Rich markup interpretation."""
    console.print(text, markup=False, highlight=False)


def _print_error(exc: AgentKitError) -> None:
    console.print(f"[red]Error:[/red] {exc}")


def _load_project(path: Path) -> AgentProject:
    return AgentProject.load(_resolve_path(path))


def _load_ship_context(path: Path) -> tuple[AgentProject, DeploymentManifest]:
    """Load agent project and validated deployment.yaml for ship commands."""
    project = _load_project(path)
    deployment = load_deployment(project.root)
    collector = validate_deployment(project.data, deployment)
    if collector.has_errors():
        raise ValidationError(collector.format_all())
    return project, deployment


@app.command("init")
def init_agent(
    name: str = typer.Argument(..., help="Agent directory name to create."),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Parent directory for the new agent (default: current directory).",
    ),
) -> None:
    """Scaffold a minimal agent directory."""
    display_name = name.replace("-", " ").title()
    manifest_data = {
        "apiVersion": "antigravity-agentkit.dev/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "name": name,
            "displayName": display_name,
            "description": "Minimal Antigravity AgentKit example.",
        },
        "spec": {
            "runtime": {"framework": "antigravity", "vertex": {"enabled": False}},
            "instructions": {"system": "SYSTEM.md"},
        },
    }
    try:
        AgentManifest.model_validate(manifest_data)
    except PydanticValidationError as exc:
        _print_error(ValidationError(f"Invalid agent name {name!r}: {exc}"))
        raise typer.Exit(code=1) from exc

    parent = _resolve_path(output_dir or Path.cwd())
    agent_dir = parent / name
    if agent_dir.exists():
        console.print(f"[red]Directory already exists:[/red] {agent_dir}")
        raise typer.Exit(code=1)

    agent_dir.mkdir(parents=True)
    (agent_dir / "SYSTEM.md").write_text(
        "# Role\n\nYou are a helpful agent.\n",
        encoding="utf-8",
    )
    manifest = yaml.safe_dump(
        manifest_data,
        sort_keys=False,
        allow_unicode=False,
    )
    (agent_dir / "agent.yaml").write_text(manifest, encoding="utf-8")
    console.print(f"[green]Created agent at[/green] {agent_dir}")


@app.command("validate")
def validate_cmd(
    path: Path = typer.Argument(..., help="Path to agent directory."),
    level: _LevelChoice = typer.Option(_LevelChoice.SCHEMA, "--level", "-l"),
    profile: _ProfileChoice = typer.Option(_ProfileChoice.DEV_OPEN, "--profile", "-p"),
) -> None:
    """Validate agent manifest, security rules, and optional deployment.yaml."""
    try:
        project = _load_project(path)
        collector = validate_project(
            project.root,
            project.data,
            level=level.value,  # type: ignore[arg-type]
            profile=profile.value,  # type: ignore[arg-type]
        )
        if collector.diagnostics:
            console.print(collector.format_all())
        if collector.has_errors():
            raise typer.Exit(code=1)
        console.print("[green]Validation passed.[/green]")
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


@app.command("compile")
def compile_cmd(
    path: Path = typer.Argument(..., help="Path to agent directory."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write JSON config to file."),
    production: bool = typer.Option(False, "--production"),
) -> None:
    """Compile agent directory to runtime configuration."""
    try:
        compiled = compile_agent_config(_resolve_path(path), production=production)
        sdk_view = {
            "systemInstructionsLength": len(compiled.system_instructions),
            "mcpServerCount": len(compiled.mcp_servers),
            "toolCount": len(compiled.tools),
            "policyCount": len(compiled.policies),
            "model": compiled.model,
            "vertex": compiled.vertex,
        }
        if output:
            output.write_text(json.dumps(sdk_view, indent=2), encoding="utf-8")
            console.print(f"[green]Wrote[/green] {output}")
        else:
            console.print_json(json.dumps(sdk_view))
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


@app.command("run")
def run_cmd(
    path: Path = typer.Argument(..., help="Path to agent directory."),
    prompt: str = typer.Option(..., "--prompt", "-p", help="User prompt to send."),
    production: bool = typer.Option(False, "--production"),
    interactive: bool = typer.Option(
        False,
        "--interactive/--no-interactive",
        help="Prompt for ask_user policy approvals (default: deny).",
    ),
    impersonate_service_account: str | None = typer.Option(
        None,
        "--impersonate-service-account",
        envvar=IMPERSONATE_ENV,
        help="Impersonate this SA for Vertex/API calls (operator auth only).",
    ),
) -> None:
    """Run a local agent chat turn."""
    import asyncio

    async def _run() -> None:
        runtime = RuntimeAgent.from_directory(_resolve_path(path), production=production)
        _print_plain(
            await runtime.run_chat(
                prompt,
                production=production,
                interactive=interactive,
                impersonate_service_account=impersonate_service_account,
            )
        )

    try:
        asyncio.run(_run())
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


@app.command("eval")
def eval_cmd(
    path: Path = typer.Argument(..., help="Path to agent directory."),
    suite: str | None = typer.Option(None, "--suite", "-s", help="Comma-separated suite filter."),
) -> None:
    """Run evaluation suites in deterministic mock mode."""
    try:
        project = _load_project(path)
        result = run_evals(project, suite_filter=suite)
        for case in result.cases:
            status = "PASS" if case.passed else "FAIL"
            console.print(f"{status} {case.suite_path}:{case.name}")
            for failure in case.failures:
                console.print(f"  - {failure}")
        console.print(f"\n{result.passed}/{result.total} passed")
        assert_evals_passed(result)
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


@app.command("package")
def package_cmd(
    path: Path = typer.Argument(..., help="Path to agent directory."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
) -> None:
    """[Ship] Build a deployable source package (requires deployment.yaml)."""
    try:
        project, _ = _load_ship_context(path)
        package_path = build_source_package(project, output_dir=output_dir)
        console.print(f"[green]Package built at[/green] {package_path}")
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


@app.command("deploy")
def deploy_cmd(
    path: Path = typer.Argument(..., help="Path to agent directory."),
    project_id: str = typer.Option(..., "--project", "-p"),
    location: str = typer.Option(..., "--location", "-l"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Dry-run config output path."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Force dry-run mode."),
) -> None:
    """[Ship] Deploy to Agent Platform or emit deployment config (requires deployment.yaml)."""
    try:
        agent_project, deployment = _load_ship_context(path)
        summary = deploy(
            agent_project,
            deployment,
            project_id,
            location,
            output_path=output,
            dry_run=dry_run or None,
        )
        console.print_json(json.dumps(summary, indent=2))
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


@app.command("publish-skill")
def publish_skill_cmd(
    skill_dir: Path = typer.Argument(..., help="Path to skill package directory."),
    project_id: str | None = typer.Option(None, "--project", "-p"),
    location: str | None = typer.Option(None, "--location", "-l"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
) -> None:
    """Validate and package a skill for Skill Registry publishing."""
    try:
        summary = publish_skill(
            _resolve_path(skill_dir),
            project=project_id,
            location=location,
            output_dir=output_dir,
        )
        console.print_json(json.dumps(summary, indent=2))
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


@app.command("register")
def register_cmd(
    path: Path = typer.Argument(..., help="Path to agent directory."),
    project_id: str = typer.Option(..., "--project", "-p"),
    location: str = typer.Option(..., "--location", "-l"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """[Ship] Emit Agent Registry metadata (requires deployment.yaml)."""
    try:
        agent_project, deployment = _load_ship_context(path)
        metadata = build_agent_registry_metadata(agent_project, deployment)
        metadata["registry"] = {
            "project": project_id,
            "location": location,
            "mcpServers": build_mcp_server_metadata(agent_project),
        }
        if output:
            output.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            console.print(f"[green]Wrote registry metadata to[/green] {output}")
        else:
            console.print_json(json.dumps(metadata, indent=2))
    except AgentKitError as exc:
        _print_error(exc)
        raise typer.Exit(code=1) from exc


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
