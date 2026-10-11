"""Language-aware download support for individual AI-generated code blocks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_LANGUAGE_EXTENSIONS = {
    "python": ".py", "py": ".py", "html": ".html", "xml": ".xml",
    "css": ".css", "javascript": ".js", "js": ".js", "typescript": ".ts",
    "ts": ".ts", "tsx": ".tsx", "jsx": ".jsx", "json": ".json",
    "sql": ".sql", "java": ".java", "c": ".c", "cpp": ".cpp",
    "c++": ".cpp", "csharp": ".cs", "cs": ".cs", "go": ".go",
    "rust": ".rs", "ruby": ".rb", "php": ".php", "bash": ".sh",
    "shell": ".sh", "sh": ".sh", "yaml": ".yaml", "yml": ".yml",
    "markdown": ".md", "md": ".md", "text": ".txt", "txt": ".txt",
}


@dataclass(frozen=True, slots=True)
class CodeFileType:
    """File-dialog metadata inferred from a fenced-code language label."""

    language: str
    extension: str

    @property
    def file_filter(self) -> str:
        label = self.language.upper() if self.language else "Text"
        return f"{label} file (*{self.extension});;All files (*.*)"


def code_file_type(language: str) -> CodeFileType:
    """Resolve an extension conservatively; unknown languages use plain text."""
    normalized_language = language.strip().lower()
    return CodeFileType(
        language=normalized_language,
        extension=_LANGUAGE_EXTENSIONS.get(normalized_language, ".txt"),
    )


def save_code(content: str, destination: Path | str, file_type: CodeFileType) -> Path:
    """Write raw code as UTF-8 and add its inferred suffix when omitted."""
    output = Path(destination)
    if not output.suffix:
        output = output.with_suffix(file_type.extension)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="")
    return output
