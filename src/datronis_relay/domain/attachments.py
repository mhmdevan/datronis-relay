from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileAttachment:
    """A file the user uploaded that Claude can read via its Read tool.

    One type handles both documents and images. The adapter downloads the
    payload to an absolute path on the bot host; the Claude client adds a
    line to the prompt pointing Claude at that path. Claude's Read tool
    is multimodal-aware, so PDFs, text files, and images all go through
    the same code path.

    The `FileAttachment` is immutable; cleanup (`path.unlink`) happens in
    the `MessagePipeline` finally-block so temp files never leak.
    """

    path: Path
    filename: str
    mime_type: str
    size_bytes: int

    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")
