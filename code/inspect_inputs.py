from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
        if text.strip():
            paragraphs.append(text)
    return "\n".join(paragraphs)


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    if target == "inventory":
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                print(path.relative_to(ROOT).as_posix())
        return
    if target == "docx":
        for path in sorted(ROOT.glob("*.docx")):
            print(f"===== {path.name} =====")
            print(read_docx(path))
        return
    if target == "texts":
        paths = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), ROOT / "data" / "config.txt"]
        for path in paths:
            print(f"===== {path.relative_to(ROOT).as_posix()} =====")
            print(path.read_text(encoding="utf-8"))
        return
    if target == "json-summary":
        for path in sorted((ROOT / "data").glob("case_*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            print(path.name, len(data.get("ops", [])), len(data.get("tensors", [])), len(data.get("edges", [])))
        return
    if target == "code-search":
        needles = tuple(sys.argv[2:])
        for path in sorted((ROOT / "code").glob("*.py")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if any(needle in line for needle in needles):
                    print(f"{path.name}:{line_number}: {line}")
        return
    if target == "slice":
        path = Path(sys.argv[2])
        start = int(sys.argv[3])
        end = int(sys.argv[4])
        lines = path.read_text(encoding="utf-8").splitlines()
        for number in range(start, min(end, len(lines)) + 1):
            print(f"{number}: {lines[number - 1]}")
        return
    raise SystemExit(f"unknown target: {target}")


if __name__ == "__main__":
    main()
