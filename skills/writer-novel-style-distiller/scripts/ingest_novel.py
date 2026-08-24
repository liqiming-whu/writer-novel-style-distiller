#!/usr/bin/env python3
"""Read, clean and segment user-provided novels for style distillation.

Standard-library only. Supports txt/md/html/docx/epub. The output work directory
is private analysis material and must not be packaged into a generated style skill.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "utf-16")
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CHAPTER_RE = re.compile(
    r"^\s*(?:"
    r"第[〇零一二两三四五六七八九十百千万\d]+(?:卷|章|节|回)(?:[：:、.．\-—\s].{0,45})?"
    r"|卷[〇零一二两三四五六七八九十百千万\d]+(?:[：:、.．\-—\s].{0,45})?"
    r"|Chapter\s+\d+(?:\s*[:.\-—]\s*.{0,45})?"
    r"|(?:序章|楔子|尾声|终章|大结局|结局|后日谈|作者后记|后记)(?:[：:、.．\-—\s].{0,45})?"
    r"|(?:番外|外传)(?:[〇零一二两三四五六七八九十百千万\d]+)?(?:[：:、.．\-—\s].{0,45})?"
    r"|\d{1,4}[.、．]\s*[^。！？!?]{1,35}"
    r")\s*$",
    re.IGNORECASE,
)
GLOBAL_NOISE = re.compile(
    r"(?:本书来自|txt小说下载|手机用户请访问|最新网址|请记住本站|加入书签|"
    r"求收藏|求推荐票|版权归原作者|仅供学习交流|www\.|https?://)", re.IGNORECASE
)
EDGE_META = re.compile(
    r"^(?:书名|作者|内容简介|作品简介|作者简介|责任编辑|出版|ISBN|版权|"
    r"目录|推荐语|媒体推荐|免责声明|下载说明|制作信息)\s*[：:]?", re.IGNORECASE
)


class TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "section", "article", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav"}:
            self.skip_depth += 1
        elif not self.skip_depth and tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav"} and self.skip_depth:
            self.skip_depth -= 1
        elif not self.skip_depth and tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def effective_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def decode_bytes(data: bytes) -> tuple[str, str]:
    errors: list[str] = []
    for enc in TEXT_ENCODINGS:
        try:
            text = data.decode(enc)
            if text.count("�") > max(2, len(text) // 5000):
                errors.append(f"{enc}: too many replacement characters")
                continue
            return text, enc
        except UnicodeError as exc:
            errors.append(f"{enc}: {exc.__class__.__name__}")
    raise UnicodeError("decode failed; " + "; ".join(errors))


def html_to_text(raw: str) -> str:
    parser = TextExtractor()
    parser.feed(raw)
    return html.unescape(parser.text())


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for p in root.iter(ns + "p"):
        chunks: list[str] = []
        for node in p.iter():
            if node.tag == ns + "t" and node.text:
                chunks.append(node.text)
            elif node.tag in {ns + "tab", ns + "br"}:
                chunks.append("\t" if node.tag == ns + "tab" else "\n")
        paragraphs.append("".join(chunks))
    return "\n".join(paragraphs)


def epub_spine_files(zf: zipfile.ZipFile) -> list[str]:
    try:
        container = ET.fromstring(zf.read("META-INF/container.xml"))
        rootfile = next(node for node in container.iter() if node.tag.endswith("rootfile"))
        opf_path = rootfile.attrib["full-path"]
        opf = ET.fromstring(zf.read(opf_path))
        base = Path(opf_path).parent
        manifest: dict[str, str] = {}
        for node in opf.iter():
            if node.tag.endswith("item") and node.attrib.get("id") and node.attrib.get("href"):
                manifest[node.attrib["id"]] = str((base / node.attrib["href"]).as_posix())
        ordered: list[str] = []
        for node in opf.iter():
            if node.tag.endswith("itemref") and node.attrib.get("idref") in manifest:
                ordered.append(manifest[node.attrib["idref"]])
        return ordered
    except Exception:
        return sorted(name for name in zf.namelist() if name.lower().endswith((".xhtml", ".html", ".htm")))


def read_epub(path: Path) -> str:
    pages: list[str] = []
    with zipfile.ZipFile(path) as zf:
        for name in epub_spine_files(zf):
            try:
                raw = zf.read(name)
            except KeyError:
                continue
            text, _ = decode_bytes(raw)
            pages.append(html_to_text(text))
    return "\n\n".join(pages)


def read_source(path: Path) -> tuple[str, str, bytes]:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path), "docx-xml", data
    if suffix == ".epub":
        return read_epub(path), "epub-spine", data
    text, encoding = decode_bytes(data)
    if suffix in {".html", ".htm", ".xhtml"}:
        text = html_to_text(text)
    return text, encoding, data


def normalize_lines(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

    counts = Counter(line for line in lines if 2 <= len(line) <= 60)
    repeated_noise = {line for line, count in counts.items() if count >= 4 and GLOBAL_NOISE.search(line)}
    if repeated_noise:
        warnings.append(f"removed {len(repeated_noise)} repeated watermark/ad lines")

    out: list[str] = []
    total = len(lines)
    for i, line in enumerate(lines):
        if line in repeated_noise:
            continue
        if GLOBAL_NOISE.search(line) and len(line) <= 100:
            continue
        edge = i < min(160, total // 5 + 20) or i >= max(0, total - 100)
        if edge and EDGE_META.search(line) and len(line) <= 100 and not CHAPTER_RE.match(line):
            continue
        if line.startswith("```") or line == "---":
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        out.append(line)

    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, warnings


def chapter_title(line: str) -> str | None:
    candidate = line.strip().strip("*＿_")
    if 1 <= len(candidate) <= 60 and CHAPTER_RE.match(candidate):
        return candidate
    return None


def structural_role(title: str) -> str:
    compact = re.sub(r"\s+", "", title)
    if re.match(r"^(?:序章|楔子)", compact):
        return "prologue"
    if re.match(r"^(?:终章|大结局|结局)", compact):
        return "finale"
    if re.match(r"^尾声", compact):
        return "epilogue"
    if re.match(r"^(?:番外|外传|后日谈)", compact):
        return "extra"
    if re.match(r"^(?:作者后记|后记)", compact):
        return "author_afterword"
    return "chapter"


def split_units(text: str, window: int = 6000, overlap: int = 300) -> tuple[list[dict], str, list[str]]:
    lines = text.splitlines()
    markers: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        title = chapter_title(line)
        if title:
            markers.append((i, title))

    warnings: list[str] = []
    units: list[dict] = []
    if len(markers) >= 2:
        prefix = "\n".join(lines[: markers[0][0]]).strip()
        if effective_chars(prefix) >= 500:
            units.append({"title": "前置文本", "text": prefix, "kind": "preface_or_prologue"})
        elif prefix:
            warnings.append("dropped short pre-chapter metadata/preface")
        for n, (start, title) in enumerate(markers):
            end = markers[n + 1][0] if n + 1 < len(markers) else len(lines)
            body = "\n".join(lines[start + 1 : end]).strip()
            if effective_chars(body) < 80:
                warnings.append(f"very short chapter candidate: {title}")
            units.append({"title": title, "text": body, "kind": structural_role(title)})
        return units, "chapter", warnings

    compact = text.strip()
    if not compact:
        return [], "window", ["empty corpus after cleaning"]
    warnings.append("fewer than two reliable chapter markers; switched to analysis windows")
    start = 0
    idx = 1
    step = max(500, window - overlap)
    while start < len(compact):
        end = min(len(compact), start + window)
        chunk = compact[start:end].strip()
        if chunk:
            units.append({"title": f"分析窗口 {idx}", "text": chunk, "kind": "window"})
        if end >= len(compact):
            break
        start += step
        idx += 1
    return units, "window", warnings


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    vals = sorted(values)
    pos = int(round((len(vals) - 1) * q))
    return vals[max(0, min(pos, len(vals) - 1))]


def build_sample_plan(
    units: list[dict], limit: int = 16, completion_status: str = "unknown"
) -> list[dict]:
    n = len(units)
    if n <= limit:
        return [{"unit_index": i + 1, "reason": "short corpus: close-read all units"} for i in range(n)]

    choices: dict[int, set[str]] = {}
    required: set[int] = set()

    def add(index: int, reason: str) -> None:
        index = max(0, min(index, n - 1))
        choices.setdefault(index, set()).add(reason)

    for idx, reason in [
        (0, "opening"), (1, "opening"),
        (round((n - 1) * 0.2), "early section"),
        (round((n - 1) * 0.25), "first quarter"),
        (round((n - 1) * 0.4), "pre-midpoint"),
        (round((n - 1) * 0.5), "midpoint"),
        (round((n - 1) * 0.6), "post-midpoint"),
        (round((n - 1) * 0.75), "third quarter"),
        (round((n - 1) * 0.8), "late section"),
        (n - 2, "ending"), (n - 1, "ending"),
    ]:
        add(idx, reason)

    if completion_status == "complete":
        fictional = [
            i for i, unit in enumerate(units)
            if unit.get("kind") not in {"author_afterword", "preface_or_prologue"}
        ]
        for i in fictional[-2:]:
            add(i, "complete work: terminal main arc")
            required.add(i)
        for i, unit in enumerate(units):
            role = unit.get("kind")
            if role in {"finale", "epilogue", "extra", "author_afterword"}:
                add(i, f"complete work: full coverage of {role}")
                required.add(i)

    lengths = [effective_chars(u["text"]) for u in units]
    add(max(range(n), key=lambda i: lengths[i]), "longest unit")
    eligible = [i for i, x in enumerate(lengths) if x >= 500]
    if eligible:
        add(min(eligible, key=lambda i: lengths[i]), "short complete unit")

    punct = [u["text"].count("！") + u["text"].count("？") + u["text"].count("……") for u in units]
    add(max(range(n), key=lambda i: punct[i]), "punctuation-density outlier")

    dialogue = [sum(len(x) for x in re.findall(r"[“「『](.*?)[”」』]", u["text"], re.S)) for u in units]
    add(max(range(n), key=lambda i: dialogue[i]), "dialogue-heavy unit")

    rows = [
        {"unit_index": i + 1, "reason": "; ".join(sorted(reasons))}
        for i, reasons in sorted(choices.items())
    ]
    selected: list[dict] = []
    for row in rows:
        index = row["unit_index"] - 1
        if len(selected) < limit or index in required:
            selected.append(row)
    return selected


def paragraph_index(text: str, source_id: str, unit_index: int) -> list[dict]:
    rows: list[dict] = []
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    for i, para in enumerate(paras, 1):
        rows.append({
            "source_id": source_id,
            "unit_index": unit_index,
            "paragraph_index": i,
            "paragraph_hash": hashlib.sha256(para.encode("utf-8")).hexdigest()[:12],
            "characters": effective_chars(para),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare novel corpus for style distillation")
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--window", type=int, default=6000)
    ap.add_argument("--overlap", type=int, default=300)
    ap.add_argument("--sample-limit", type=int, default=16)
    ap.add_argument(
        "--completion-status", choices=("unknown", "ongoing", "complete"), default="unknown",
        help="Set complete only from an explicit user statement or reliable source metadata.",
    )
    ap.add_argument(
        "--completion-basis", default=None,
        help="Examples: user_explicit, publisher_metadata, table_of_contents.",
    )
    args = ap.parse_args()
    if args.completion_status == "complete" and not args.completion_basis:
        print("ERROR: --completion-status complete requires --completion-basis", file=sys.stderr)
        return 2

    out = args.output.resolve()
    unit_dir = out / "units"
    out.mkdir(parents=True, exist_ok=True)
    unit_dir.mkdir(parents=True, exist_ok=True)

    manifest_files: list[dict] = []
    all_units: list[dict] = []
    all_warnings: list[str] = []
    paragraph_rows: list[dict] = []

    for source_no, path in enumerate(args.inputs, 1):
        path = path.expanduser().resolve()
        if not path.exists() or not path.is_file():
            print(f"ERROR: source not found: {path}", file=sys.stderr)
            return 2
        try:
            raw_text, encoding, raw_bytes = read_source(path)
        except Exception as exc:
            print(f"ERROR: failed to read {path}: {exc}", file=sys.stderr)
            return 2
        cleaned, clean_warnings = normalize_lines(raw_text)
        units, unit_type, split_warnings = split_units(cleaned, args.window, args.overlap)
        source_id = f"S{source_no:02d}"
        manifest_files.append({
            "source_id": source_id,
            "file_name": path.name,
            "path": str(path),
            "format": path.suffix.lower().lstrip(".") or "text",
            "encoding": encoding,
            "sha256": sha256_bytes(raw_bytes),
            "raw_characters": effective_chars(raw_text),
            "clean_characters": effective_chars(cleaned),
            "unit_type": unit_type,
            "unit_count": len(units),
            "warnings": clean_warnings + split_warnings,
        })
        all_warnings.extend(f"{source_id}: {w}" for w in clean_warnings + split_warnings)
        for unit in units:
            global_index = len(all_units) + 1
            unit_text = unit["text"].strip()
            row = {
                "unit_index": global_index,
                "source_id": source_id,
                "source_unit_index": len([u for u in all_units if u["source_id"] == source_id]) + 1,
                "title": unit["title"],
                "kind": unit["kind"],
                "characters": effective_chars(unit_text),
                "sha256": hashlib.sha256(unit_text.encode("utf-8")).hexdigest(),
                "file": f"units/unit-{global_index:04d}.txt",
                "text": unit_text,
            }
            all_units.append(row)
            paragraph_rows.extend(paragraph_index(unit_text, source_id, global_index))

    if not all_units:
        print("ERROR: no valid text units after cleaning", file=sys.stderr)
        return 3

    corpus_parts: list[str] = []
    chapter_lines: list[str] = []
    for unit in all_units:
        header = f"===== UNIT {unit['unit_index']:04d} | {unit['source_id']} | {unit['title']} ====="
        corpus_parts.extend([header, unit["text"], ""])
        (out / unit["file"]).write_text(header + "\n" + unit["text"] + "\n", encoding="utf-8")
        public_row = {k: v for k, v in unit.items() if k != "text"}
        chapter_lines.append(json.dumps(public_row, ensure_ascii=False))

    (out / "corpus.normalized.txt").write_text("\n".join(corpus_parts), encoding="utf-8")
    (out / "chapters.jsonl").write_text("\n".join(chapter_lines) + "\n", encoding="utf-8")
    (out / "paragraph-index.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in paragraph_rows) + "\n", encoding="utf-8"
    )

    sample_plan = build_sample_plan(all_units, args.sample_limit, args.completion_status)
    (out / "sample-plan.json").write_text(json.dumps(sample_plan, ensure_ascii=False, indent=2), encoding="utf-8")

    unit_kinds = Counter(u["kind"] for u in all_units)

    def unit_locators(kinds: set[str]) -> list[dict]:
        return [
            {"unit_index": u["unit_index"], "title": u["title"], "kind": u["kind"]}
            for u in all_units if u.get("kind") in kinds
        ]

    main_sequence = [
        u for u in all_units if u.get("kind") in {"chapter", "finale", "epilogue", "window"}
    ]
    terminal_candidates = main_sequence[-2:] if args.completion_status == "complete" else []
    terminal_ids = {u["unit_index"] for u in terminal_candidates}
    terminal_ids.update(
        u["unit_index"] for u in all_units
        if u.get("kind") in {"finale", "epilogue", "extra"}
    )
    terminal_arc_units = [
        {"unit_index": u["unit_index"], "title": u["title"], "kind": u["kind"]}
        for u in all_units if u["unit_index"] in terminal_ids
    ]
    finale_units = unit_locators({"finale"})
    epilogue_units = unit_locators({"epilogue"})
    extra_units = unit_locators({"extra"})
    afterword_units = unit_locators({"author_afterword"})
    main_ending_units = finale_units or (
        [
            {"unit_index": main_sequence[-1]["unit_index"], "title": main_sequence[-1]["title"],
             "kind": main_sequence[-1]["kind"]}
        ] if args.completion_status == "complete" and main_sequence else []
    )

    manifest = {
        "schema_version": "1.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_files": manifest_files,
        "corpus": {
            "full_text_covered": True,
            "effective_characters": sum(u["characters"] for u in all_units),
            "unit_count": len(all_units),
            "unit_kinds": dict(unit_kinds),
            "chapter_detection_confident": unit_kinds.get("chapter", 0) >= 2,
            "early_mid_late_compared": False,
        },
        "sampling": {
            "close_read_units": sample_plan,
            "selection_reasons": sorted({r["reason"] for r in sample_plan}),
        },
        "completion": {
            "status": args.completion_status,
            "basis": args.completion_basis,
            "user_explicitly_declared": args.completion_basis == "user_explicit",
            "main_ending_present": bool(main_ending_units) if args.completion_status == "complete" else None,
            "epilogue_present": bool(epilogue_units) if args.completion_status == "complete" else None,
            "extras_present": bool(extra_units) if args.completion_status == "complete" else None,
            "author_afterword_present": bool(afterword_units) if args.completion_status == "complete" else None,
            "terminal_arc_units": terminal_arc_units,
            "main_ending_units": main_ending_units,
            "epilogue_units": epilogue_units,
            "extra_units": extra_units,
            "author_afterword_units": afterword_units,
            "coverage": {
                "main_ending_analyzed": False,
                "epilogue_analyzed": False,
                "extras_checked": args.completion_status == "complete",
                "extras_analyzed": False,
            },
        },
        "limitations": all_warnings,
        "raw_text_packaged": False,
        "independent_blind_review": False,
    }
    (out / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "output": str(out),
        "sources": len(manifest_files),
        "units": len(all_units),
        "effective_characters": manifest["corpus"]["effective_characters"],
        "completion_status": args.completion_status,
        "completion_basis": args.completion_basis,
        "terminal_arc_units": [u["unit_index"] for u in terminal_arc_units],
        "epilogue_units": [u["unit_index"] for u in epilogue_units],
        "extra_units": [u["unit_index"] for u in extra_units],
        "author_afterword_units": [u["unit_index"] for u in afterword_units],
        "sample_units": [r["unit_index"] for r in sample_plan],
        "warnings": all_warnings,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
