#!/usr/bin/env python
from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Annotated

import click
from sayer import Option, Sayer, command, info, success

try:
    from scripts.docs_pipeline import DocsPipelineError, prepare_docs_tree, run_zensical
except ModuleNotFoundError:  # pragma: no cover
    from docs_pipeline import DocsPipelineError, prepare_docs_tree, run_zensical

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_DOCS_DIR = ROOT_DIR / "docs"
GENERATED_DOCS_DIR = ROOT_DIR / "docs-generated"
DEFAULT_CONFIG_FILE = ROOT_DIR / "mkdocs.yml"
DEFAULT_SITE_DIR = ROOT_DIR / "site"
DEFAULT_CACHE_DIR = ROOT_DIR / ".cache"
SOURCE_DOCS_SNIPPETS_DIR = ROOT_DIR / "docs_src"


def _snapshot(paths: list[Path]) -> dict[str, int]:
    state: dict[str, int] = {}
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            state[str(path.resolve())] = path.stat().st_mtime_ns
            continue
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file():
                state[str(candidate.resolve())] = candidate.stat().st_mtime_ns
    return state


def _resolve_config(config_file: str) -> Path:
    config_path = (ROOT_DIR / config_file).resolve()
    if not config_path.is_file():
        raise click.ClickException(f"Config file not found: {config_path}")
    return config_path


def _prepare() -> list[Path]:
    generated = prepare_docs_tree(SOURCE_DOCS_DIR, GENERATED_DOCS_DIR)
    info(f"Prepared {len(generated)} docs file(s) in {GENERATED_DOCS_DIR}")
    return generated


def _watch_sources(stop_event: threading.Event, interval: float = 0.5) -> None:
    watch_paths = [SOURCE_DOCS_DIR, SOURCE_DOCS_SNIPPETS_DIR]
    previous = _snapshot(watch_paths)
    while not stop_event.wait(interval):
        current = _snapshot(watch_paths)
        if current == previous:
            continue
        previous = current
        try:
            _prepare()
            success("Docs refreshed")
        except DocsPipelineError as exc:
            click.echo(f"Docs refresh failed: {exc}", err=True)


@command
def prepare() -> None:
    """Generate build-ready markdown by expanding include directives."""
    _prepare()
    success("Docs prepared")


@command
def clean() -> None:
    """Remove generated docs artifacts and build output."""
    for path in [GENERATED_DOCS_DIR, DEFAULT_SITE_DIR, DEFAULT_CACHE_DIR]:
        shutil.rmtree(path, ignore_errors=True)
    success("Removed docs artifacts")


@command
def build(
    config: Annotated[
        str,
        Option(
            str(DEFAULT_CONFIG_FILE.relative_to(ROOT_DIR)),
            "--config-file",
            "-f",
            help="Path to zensical config file relative to repository root.",
        ),
    ],
    clean_cache: Annotated[
        bool,
        Option(False, "--clean", help="Clean Zensical cache before build.", is_flag=True),
    ] = False,
) -> None:
    """Prepare docs and run `zensical build`."""
    config_path = _resolve_config(config)
    _prepare()
    run_zensical(
        project_root=ROOT_DIR,
        config_file=config_path,
        command="build",
        clean=clean_cache,
    )
    success("Docs built with Zensical")


@command
def serve(
    config: Annotated[
        str,
        Option(
            str(DEFAULT_CONFIG_FILE.relative_to(ROOT_DIR)),
            "--config-file",
            "-f",
            help="Path to zensical config file relative to repository root.",
        ),
    ],
    port: Annotated[int, Option(8000, "-p", help="Port to serve documentation")],
    open_browser: Annotated[
        bool,
        Option(False, "--open", help="Open docs in the default browser.", is_flag=True),
    ] = False,
    watch_sources: Annotated[
        bool,
        Option(
            True,
            "--watch-sources/--no-watch-sources",
            help="Watch docs and docs_src and regenerate docs-generated automatically.",
        ),
    ] = True,
) -> None:
    """Prepare docs and run `zensical serve`."""
    config_path = _resolve_config(config)
    _prepare()
    stop_event = threading.Event()
    watch_thread: threading.Thread | None = None
    if watch_sources:
        watch_thread = threading.Thread(target=_watch_sources, args=(stop_event,), daemon=True)
        watch_thread.start()
        info(f"Watching source docs for changes: {SOURCE_DOCS_DIR}, {SOURCE_DOCS_SNIPPETS_DIR}")

    try:
        run_zensical(
            project_root=ROOT_DIR,
            config_file=config_path,
            command="serve",
            dev_addr=f"127.0.0.1:{port}",
            open_browser=open_browser,
        )
    finally:
        stop_event.set()
        if watch_thread is not None:
            watch_thread.join(timeout=1.0)


docs_cli = Sayer(
    name="docs", help="Documentation generation commands", invoke_without_command=True
)
docs_cli.add_command(prepare)
docs_cli.add_command(clean)
docs_cli.add_command(build)
docs_cli.add_command(serve)

if __name__ == "__main__":
    try:
        docs_cli()
    except DocsPipelineError as exc:
        raise click.ClickException(str(exc)) from exc
