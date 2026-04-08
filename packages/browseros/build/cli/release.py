#!/usr/bin/env python3
"""Release CLI - Modular release automation for BrowserOS"""

from pathlib import Path
from typing import Optional
import re

import typer

from ..common.context import Context
from ..common.module import Module, ValidationError
from ..common.utils import log_info, log_error

from ..modules.release import (
    AVAILABLE_MODULES,
    ListModule,
    AppcastModule,
    GithubModule,
    PublishModule,
    DownloadModule,
)

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

app = typer.Typer(
    help="Release automation commands",
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)

github_app = typer.Typer(
    help="GitHub release operations",
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)
app.add_typer(github_app, name="github")


def validate_version(version: str) -> None:
    if not SEMVER_RE.match(version):
        log_error(f"Invalid version '{version}' - expected format: MAJOR.MINOR.PATCH (e.g. 0.31.0)")
        raise typer.Exit(1)


def create_release_context(version: str, repo: Optional[str] = None) -> Context:
    """Create a Context scoped to release operations."""
    ctx = Context(
        root_dir=Path.cwd(),
        architecture="",
        build_type="release",
    )
    ctx.release_version = version
    ctx.github_repo = repo or ""
    return ctx


def execute_module(ctx: Context, module: Module) -> None:
    """Validate then execute a module, exiting on any failure."""
    try:
        module.validate(ctx)
    except ValidationError as e:
        log_error(f"Validation failed: {e}")
        raise typer.Exit(1)

    try:
        module.execute(ctx)
    except Exception as e:
        log_error(f"Module '{type(module).__name__}' failed: {e}")
        raise typer.Exit(1)


@app.command("modules")
def show_modules() -> None:
    """List all available release modules."""
    log_info("Available release modules:")
    log_info("-" * 50)
    for name, module_class in AVAILABLE_MODULES.items():
        log_info(f"  {name}: {module_class.description}")
    log_info("-" * 50)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[str] = typer.Option(
        None, "--version", "-v", help="Version to operate on (e.g., 0.31.0)"
    ),
    list_artifacts: bool = typer.Option(
        False, "--list", "-l", help="List artifacts for version from R2"
    ),
    appcast: bool = typer.Option(
        False, "--appcast", "-a", help="Generate appcast XML snippets"
    ),
    publish: bool = typer.Option(
        False, "--publish", "-p", help="Publish to download/ paths (make live)"
    ),
    download: bool = typer.Option(
        False, "--download", "-d", help="Download artifacts to temp directory"
    ),
    os_filter: Optional[str] = typer.Option(
        None, "--os", help="Filter by OS: macos, windows, linux"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for downloads (default: temp dir)"
    ),
):
    """Release automation for BrowserOS.

    \b
    Quick Operations:
      browseros release --list                                         # List all available versions
      browseros release --list --version 0.31.0                       # List artifacts for version
      browseros release --version 0.31.0 --appcast                    # Generate appcast XML
      browseros release --version 0.31.0 --publish                    # Publish to download/ paths
      browseros release --version 0.31.0 --download                   # Download all artifacts
      browseros release --version 0.31.0 --download --os macos        # Download macOS only
      browseros release --version 0.31.0 --download --output ./dist   # Custom output dir

    \b
    GitHub Release:
      browseros release github create --version 0.31.0
      browseros release github create --version 0.31.0 --publish

    \b
    List Modules:
      browseros release modules
    """
    if ctx.invoked_subcommand is not None:
        return

    has_flags = any((list_artifacts, appcast, publish, download))
    if not has_flags:
        typer.echo("Error: specify a flag (--list, --appcast, --publish, --download) or a sub-command.")
        typer.echo("Run --help for usage, or 'browseros release modules' to list available modules.")
        raise typer.Exit(1)

    requires_version = any((appcast, publish, download))
    if requires_version and not version:
        log_error("--version is required for --appcast, --publish, and --download")
        raise typer.Exit(1)

    if version:
        validate_version(version)

    release_ctx = create_release_context(version or "")

    if list_artifacts:
        log_info(f"Listing artifacts for v{version}" if version else "Listing all available releases")
        execute_module(release_ctx, ListModule())

    if appcast:
        log_info(f"Generating appcast for v{version}")
        execute_module(release_ctx, AppcastModule())

    if publish:
        log_info(f"Publishing v{version} to download/ paths")
        execute_module(release_ctx, PublishModule())

    if download:
        log_info(f"Downloading artifacts for v{version}")
        execute_module(release_ctx, DownloadModule(os_filter=os_filter, output_dir=output))


@github_app.command("create")
def github_create(
    version: str = typer.Option(
        ..., "--version", "-v", help="Version to release (e.g., 0.31.0)"
    ),
    draft: bool = typer.Option(
        True, "--draft/--no-draft", help="Create as draft (default: true)"
    ),
    repo: Optional[str] = typer.Option(
        None, "--repo", "-r", help="GitHub repo (owner/name)"
    ),
    skip_upload: bool = typer.Option(
        False, "--skip-upload", help="Skip uploading artifacts to GitHub"
    ),
    title: Optional[str] = typer.Option(
        None, "--title", "-t", help="Release title (default: v{version})"
    ),
    publish_to_download: bool = typer.Option(
        False, "--publish", "-p", help="Also publish to download/ paths after creating release"
    ),
):
    """Create a GitHub release from R2 artifacts.

    \b
    Examples:
      browseros release github create --version 0.31.0
      browseros release github create --version 0.31.0 --publish
      browseros release github create --version 0.31.0 --no-draft
    """
    validate_version(version)
    ctx = create_release_context(version, repo)

    log_info(f"Creating GitHub release for v{version}")
    execute_module(ctx, GithubModule(draft=draft, skip_upload=skip_upload, title=title))

    if publish_to_download:
        log_info(f"Publishing v{version} to download/ paths")
        execute_module(ctx, PublishModule())


if __name__ == "__main__":
    app()
