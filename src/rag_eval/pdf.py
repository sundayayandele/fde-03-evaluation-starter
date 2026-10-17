"""Minimal PDF writer (Helvetica text pages) for building test corpora the system under test
can ingest. No dependencies; long lines are wrapped and text flows over pages."""

from __future__ import annotations

import textwrap
from pathlib import Path


def _escape(text: str) -> str:
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def paginate(paragraphs: list[str], width: int = 95, lines_per_page: int = 48) -> list[list[str]]:
    lines: list[str] = []
    for para in paragraphs:
        lines.extend(textwrap.wrap(para, width) or [""])
        lines.append("")
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
    return pages or [[""]]


def write_pdf(path: Path, pages: list[list[str]]) -> Path:
    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    page_ids = [3 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_id = 3 + 2 * len(pages)
    for i, lines in enumerate(pages):
        body = ["BT /F1 10 Tf 13 TL 50 750 Td", *(f"({_escape(line)}) '" for line in lines),
                "ET"]
        content = "\n".join(body).encode("latin-1")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                       f"/Contents {page_ids[i] + 1} 0 R >>".encode())
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content
                       + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
            .encode())
    Path(path).write_bytes(bytes(out))
    return Path(path)
