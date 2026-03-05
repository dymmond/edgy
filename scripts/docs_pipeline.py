from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

INCLUDE_PATTERN = re.compile(r"\{!\s*>?\s*(?P<path>[^!]+?)\s*!\}")
FENCED_INCLUDE_PATTERN = re.compile(
    r"```(?P<lang>[^\n`]*)\n[ \t]*\{!\s*>?\s*(?P<path>[^!]+?)\s*!\}[ \t]*\n```",
    re.MULTILINE,
)

LANGUAGE_BY_SUFFIX = {
    ".bash": "bash",
    ".dockerfile": "dockerfile",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".py": "python",
    ".sh": "bash",
    ".toml": "toml",
    ".txt": "text",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
}

MARKDOWN_SUFFIXES = {".md", ".markdown"}


class DocsPipelineError(RuntimeError):
    """Raised when docs generation or build fails."""


def _normalize_newlines(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def infer_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if path.name.lower() == "dockerfile":
        return "dockerfile"
    return LANGUAGE_BY_SUFFIX.get(suffix, "text")


def _resolve_include_path(include_expr: str, source_file: Path, include_base_dir: Path) -> Path:
    """Resolve includes using MkDocs mdx_include base-path behavior first."""
    candidates = [
        (include_base_dir / include_expr).resolve(),
        (source_file.parent / include_expr).resolve(),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise DocsPipelineError(
        f"Include path does not exist for {source_file}: {include_expr} -> "
        f"{candidates[0]} (base), {candidates[1]} (source-relative)"
    )


def render_markdown_with_includes(
    content: str, source_file: Path, include_base_dir: Path, stack: set[str] | None = None
) -> str:
    """Render include directives in a markdown file to deterministic markdown."""
    stack = set() if stack is None else set(stack)
    source_key = str(source_file.resolve())
    if source_key in stack:
        chain = " -> ".join([*stack, source_key])
        raise DocsPipelineError(f"Cyclic markdown include detected: {chain}")
    stack.add(source_key)

    content = _normalize_newlines(content)

    def replace_fenced(match: re.Match[str]) -> str:
        include_expr = match.group("path").strip()
        include_path = _resolve_include_path(include_expr, source_file, include_base_dir)

        included = _normalize_newlines(include_path.read_text(encoding="utf-8"))
        body = included.rstrip("\n")
        language = match.group("lang").strip() or infer_language(include_path)
        if body:
            return f"```{language}\n{body}\n```"
        return f"```{language}\n```"

    def replace(match: re.Match[str]) -> str:
        include_expr = match.group("path").strip()
        include_path = _resolve_include_path(include_expr, source_file, include_base_dir)

        included = _normalize_newlines(include_path.read_text(encoding="utf-8"))
        body = included.rstrip("\n")
        suffix = include_path.suffix.lower()

        # Markdown includes are inlined as markdown, everything else is fenced.
        if suffix in MARKDOWN_SUFFIXES:
            rendered = render_markdown_with_includes(
                body, include_path, include_base_dir, stack=stack
            )
            return rendered.rstrip("\n")

        language = infer_language(include_path)
        if body:
            return f"```{language}\n{body}\n```"
        return f"```{language}\n```"

    # Expand include directives that are already wrapped in fenced code blocks.
    rendered = FENCED_INCLUDE_PATTERN.sub(replace_fenced, content)
    # Expand remaining include directives.
    rendered = INCLUDE_PATTERN.sub(replace, rendered)
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def prepare_docs_tree(source_dir: Path, output_dir: Path) -> list[Path]:
    """Generate build-ready docs by expanding include directives."""
    if not source_dir.is_dir():
        raise DocsPipelineError(f"Source docs directory not found: {source_dir}")
    include_base_dir = source_dir

    tmp_output_dir = output_dir.parent / f".{output_dir.name}.tmp"
    if tmp_output_dir.exists():
        shutil.rmtree(tmp_output_dir)
    tmp_output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []

    for source_file in sorted(source_dir.rglob("*")):
        if source_file.is_dir():
            continue

        relative = source_file.relative_to(source_dir)
        target = tmp_output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)

        if source_file.suffix.lower() in MARKDOWN_SUFFIXES:
            original = source_file.read_text(encoding="utf-8")
            rendered = render_markdown_with_includes(original, source_file, include_base_dir)
            target.write_text(rendered, encoding="utf-8")
        else:
            shutil.copy2(source_file, target)

        generated.append(target)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    tmp_output_dir.replace(output_dir)

    return [output_dir / path.relative_to(tmp_output_dir) for path in generated]


def run_zensical(
    *,
    project_root: Path,
    config_file: Path,
    command: str,
    clean: bool = False,
    dev_addr: str | None = None,
    open_browser: bool = False,
) -> None:
    """Run a Zensical command with a fixed config file."""
    cli = ["zensical", command, "--config-file", str(config_file)]
    if command == "build" and clean:
        cli.append("--clean")
    if command == "serve":
        if dev_addr:
            cli.extend(["--dev-addr", dev_addr])
        if open_browser:
            cli.append("--open")

    try:
        subprocess.run(cli, check=True, cwd=project_root)
    except subprocess.CalledProcessError as exc:
        raise DocsPipelineError(
            f"Zensical command failed with exit code {exc.returncode}: {' '.join(cli)}"
        ) from exc
