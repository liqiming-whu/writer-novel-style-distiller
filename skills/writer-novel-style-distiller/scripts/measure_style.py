#!/usr/bin/env python3
"""Compute reproducible style signals for a prepared novel corpus.

The metrics are descriptive prompts for close reading, not automatic literary
judgments. No raw source excerpts are written to the report.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])|…{2,}")
DIALOGUE_RE = re.compile(r"[“「『](.*?)[”」』]|\"([^\"\n]{1,500})\"", re.S)
HEADER_RE = re.compile(r"^===== UNIT .* =====$", re.M)

LEXICONS = {
    "first_person": ["我", "我们", "咱", "咱们"],
    "third_person": ["他", "她", "他们", "她们"],
    "mental": ["觉得", "以为", "明白", "知道", "想起", "记得", "意识到", "心里", "心中", "暗想"],
    "comparison": ["像", "仿佛", "好似", "如同", "宛如", "似的", "一般"],
    "transition": ["但是", "可是", "不过", "然而", "于是", "因此", "所以", "随后", "接着", "忽然"],
    "visual": ["看", "望", "盯", "瞥", "光", "影", "亮", "暗", "颜色"],
    "auditory": ["听", "响", "声音", "脚步", "风声", "雨声", "笑声", "喊", "叫"],
    "tactile": ["冷", "热", "凉", "烫", "疼", "痛", "麻", "痒", "摸", "握", "触"],
    "olfactory": ["闻", "气味", "香味", "臭味", "腥味", "烟味", "霉味"],
    "gustatory": ["吃", "喝", "甜", "苦", "酸", "辣", "咸", "涩", "味道"],
    "emotion_labels": ["悲伤", "难过", "愤怒", "开心", "喜悦", "恐惧", "绝望", "激动", "感动"],
    "ai_risk": ["此刻", "见状", "随即", "不由得", "不禁", "心潮澎湃", "百感交集", "五味杂陈", "嘴角微微勾起", "空气仿佛凝固"],
}
DIALOGUE_TAGS = ["说道", "说", "问道", "问", "答道", "道", "笑道", "低声道", "轻声道", "沉声道"]
PUNCT = ["！", "？", "……", "——", "；", "：", "，", "。"]


def effective_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return float(vals[0])
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return float(vals[lo])
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": 0, "median": 0, "p10": 0, "p20": 0, "p80": 0, "p90": 0}
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 2),
        "median": round(statistics.median(values), 2),
        "p10": round(quantile(values, 0.10), 2),
        "p20": round(quantile(values, 0.20), 2),
        "p80": round(quantile(values, 0.80), 2),
        "p90": round(quantile(values, 0.90), 2),
    }


def per_wan(count: int, chars: int) -> float:
    return round(count / max(chars, 1) * 10000, 2)


def clean_unit_text(text: str) -> str:
    return HEADER_RE.sub("", text, count=1).strip()


def dialogue_characters(text: str) -> int:
    total = 0
    for match in DIALOGUE_RE.finditer(text):
        total += effective_chars(match.group(1) or match.group(2) or "")
    return total


def classify_opening(text: str) -> str:
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    if not paragraphs:
        return "empty"
    first = paragraphs[0][:120]
    if first.startswith(("“", "「", "『", '"')):
        return "dialogue"
    if re.match(r"^(?:翌日|次日|清晨|黄昏|夜里|夜间|这天|多年后|\d+年|第\w+日|春|夏|秋|冬)", first):
        return "time_anchor"
    if re.match(r"^.{0,16}(?:城|山|峰|村|镇|街|院|宫|府|宗|门|楼|房|室|堂)[，。 ]", first):
        return "place_anchor"
    if re.search(r"(?:抬手|起身|推开|走进|站起|转身|跑|冲|抓|放下|抬头|低头)", first):
        return "action"
    if re.search(r"(?:想|觉得|以为|记得|明白|知道)", first):
        return "interiority"
    return "narrative_or_environment"


def classify_ending(text: str) -> str:
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    if not paragraphs:
        return "empty"
    last = paragraphs[-1][-160:]
    if last.endswith(("”", "」", "』", '"')):
        return "dialogue"
    if last.endswith(("？", "?")):
        return "question"
    if last.endswith(("……", "…")):
        return "ellipsis"
    if re.search(r"(?:抬手|起身|推开|走进|站起|转身|伸手|拿起|放下|坐下|点头|摇头)[^。！？]{0,30}[。！？]?$", last):
        return "visible_action"
    if re.search(r"(?:原来|才知道|竟然|不是|真相|秘密|名字|身份)", last):
        return "information_reveal"
    return "statement_or_image"


def non_overlapping_counts(text: str, words: list[str]) -> dict[str, int]:
    """Count the longest matching marker at each position to avoid nested double counts."""
    pattern = re.compile("|".join(re.escape(word) for word in sorted(words, key=len, reverse=True)))
    return dict(Counter(pattern.findall(text)))


def marker_counts(text: str, chars: int) -> dict:
    result: dict[str, dict] = {}
    for name, words in LEXICONS.items():
        hits = non_overlapping_counts(text, words)
        total = sum(hits.values())
        result[name] = {"count": total, "per_10k": per_wan(total, chars), "items": hits}
    return result


def max_dialogue_streak(paragraphs: list[str]) -> int:
    best = current = 0
    for p in paragraphs:
        if p.startswith(("“", "「", "『", '"')):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def unit_metrics(text: str, unit_meta: dict) -> dict:
    text = clean_unit_text(text)
    chars = effective_chars(text)
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    para_lengths = [effective_chars(p) for p in paragraphs]
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if effective_chars(s) >= 2]
    sent_lengths = [effective_chars(s) for s in sentences]
    dialog_chars = dialogue_characters(text)
    punctuation = {p: {"count": text.count(p), "per_10k": per_wan(text.count(p), chars)} for p in PUNCT}
    tags = non_overlapping_counts(text, DIALOGUE_TAGS)
    return {
        "unit_index": unit_meta["unit_index"],
        "title": unit_meta.get("title"),
        "kind": unit_meta.get("kind"),
        "characters": chars,
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "sentence_length": summary(sent_lengths),
        "paragraph_length": summary(para_lengths),
        "ultrashort_paragraph_pct": round(sum(x <= 15 for x in para_lengths) / max(len(para_lengths), 1) * 100, 2),
        "long_paragraph_pct": round(sum(x >= 180 for x in para_lengths) / max(len(para_lengths), 1) * 100, 2),
        "dialogue_ratio": round(dialog_chars / max(chars, 1), 4),
        "max_dialogue_paragraph_streak": max_dialogue_streak(paragraphs),
        "punctuation": punctuation,
        "dialogue_tags": tags,
        "markers": marker_counts(text, chars),
        "opening_type": classify_opening(text),
        "ending_type": classify_ending(text),
    }


def aggregate(units: list[dict]) -> dict:
    if not units:
        return {}
    total_chars = sum(u["characters"] for u in units)
    total_paragraphs = sum(u["paragraphs"] for u in units)
    total_sentences = sum(u["sentences"] for u in units)
    weighted_dialogue = sum(u["dialogue_ratio"] * u["characters"] for u in units) / max(total_chars, 1)
    punct = {}
    for p in PUNCT:
        count = sum(u["punctuation"][p]["count"] for u in units)
        punct[p] = {"count": count, "per_10k": per_wan(count, total_chars)}
    markers = {}
    for name in LEXICONS:
        count = sum(u["markers"][name]["count"] for u in units)
        markers[name] = {"count": count, "per_10k": per_wan(count, total_chars)}
    tag_counts = Counter()
    for u in units:
        tag_counts.update(u["dialogue_tags"])
    return {
        "units": len(units),
        "characters": total_chars,
        "paragraphs": total_paragraphs,
        "sentences": total_sentences,
        "unit_characters": summary([u["characters"] for u in units]),
        "sentence_mean_by_unit": summary([u["sentence_length"]["mean"] for u in units]),
        "sentence_median_by_unit": summary([u["sentence_length"]["median"] for u in units]),
        "paragraph_mean_by_unit": summary([u["paragraph_length"]["mean"] for u in units]),
        "paragraph_median_by_unit": summary([u["paragraph_length"]["median"] for u in units]),
        "ultrashort_paragraph_pct_by_unit": summary([u["ultrashort_paragraph_pct"] for u in units]),
        "dialogue_ratio": round(weighted_dialogue, 4),
        "dialogue_ratio_by_unit": summary([u["dialogue_ratio"] for u in units]),
        "max_dialogue_paragraph_streak": max(u["max_dialogue_paragraph_streak"] for u in units),
        "punctuation": punct,
        "markers": markers,
        "dialogue_tags": dict(tag_counts.most_common()),
        "opening_types": dict(Counter(u["opening_type"] for u in units)),
        "ending_types": dict(Counter(u["ending_type"] for u in units)),
    }


def thirds(units: list[dict]) -> dict:
    n = len(units)
    if n < 3:
        return {"available": False, "reason": "fewer than three units"}
    a = max(1, n // 3)
    b = max(a + 1, (2 * n) // 3)
    return {
        "available": True,
        "early": aggregate(units[:a]),
        "middle": aggregate(units[a:b]),
        "late": aggregate(units[b:]),
    }


def markdown_report(result: dict) -> str:
    agg = result["aggregate"]
    lines = [
        "# 全量文风指标报告",
        "",
        "> 这些指标用于引导精读，不自动等于文风结论。密度值是样本观测，不是后续创作配额。",
        "",
        "## 语料概况",
        "",
        f"- 分析单位：{agg['units']}",
        f"- 有效字符：{agg['characters']}",
        f"- 段落：{agg['paragraphs']}",
        f"- 句子：{agg['sentences']}",
        f"- 加权对白占比：{agg['dialogue_ratio']:.1%}",
        "",
        "## 句段",
        "",
        f"- 单位句长中位数分布：P20={agg['sentence_median_by_unit']['p20']}，中位={agg['sentence_median_by_unit']['median']}，P80={agg['sentence_median_by_unit']['p80']}",
        f"- 单位段长中位数分布：P20={agg['paragraph_median_by_unit']['p20']}，中位={agg['paragraph_median_by_unit']['median']}，P80={agg['paragraph_median_by_unit']['p80']}",
        f"- 极短段占比分布：P20={agg['ultrashort_paragraph_pct_by_unit']['p20']}%，中位={agg['ultrashort_paragraph_pct_by_unit']['median']}%，P80={agg['ultrashort_paragraph_pct_by_unit']['p80']}%",
        f"- 连续纯对白段最大值：{agg['max_dialogue_paragraph_streak']}",
        "",
        "## 标点（每万有效字符）",
        "",
    ]
    for p, data in agg["punctuation"].items():
        lines.append(f"- `{p}`：{data['per_10k']}")
    lines.extend(["", "## 词表提示（每万有效字符）", ""])
    for name, data in agg["markers"].items():
        lines.append(f"- {name}：{data['per_10k']}")
    lines.extend(["", "## 章首类型", ""])
    for name, count in agg["opening_types"].items():
        lines.append(f"- {name}：{count}")
    lines.extend(["", "## 章末类型", ""])
    for name, count in agg["ending_types"].items():
        lines.append(f"- {name}：{count}")
    lines.extend([
        "",
        "## 人工复核提醒",
        "",
        "- 第一／第三人称词频不能单独决定叙事人称，对话中的代词会干扰。",
        "- 感官词和心理词使用简单词表，只提示精读位置。",
        "- 章首／章末分类是启发式；窗口模式下不应当作真实章节规律。",
        "- 对话标签采用最长词优先的非重叠计数，仍需结合具体角色与引号位置人工复核。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure whole-corpus style signals")
    ap.add_argument("--workdir", required=True, type=Path)
    args = ap.parse_args()
    workdir = args.workdir.resolve()
    chapter_file = workdir / "chapters.jsonl"
    if not chapter_file.exists():
        print(f"ERROR: missing {chapter_file}; run ingest_novel.py first", file=sys.stderr)
        return 2

    metas = [json.loads(line) for line in chapter_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    units: list[dict] = []
    for meta in metas:
        path = workdir / meta["file"]
        if not path.exists():
            print(f"ERROR: missing unit file {path}", file=sys.stderr)
            return 2
        units.append(unit_metrics(path.read_text(encoding="utf-8"), meta))

    result = {
        "schema_version": "1.0",
        "notes": [
            "Descriptive signals only; close reading is required.",
            "Observed ranges are not generation quotas.",
        ],
        "aggregate": aggregate(units),
        "drift_thirds": thirds(units),
        "units": units,
    }
    (workdir / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (workdir / "metrics-report.md").write_text(markdown_report(result), encoding="utf-8")

    manifest_path = workdir / "source-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("corpus", {})["early_mid_late_compared"] = len(units) >= 3
        manifest["corpus"]["metrics_file"] = "metrics.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "metrics": str(workdir / "metrics.json"),
        "report": str(workdir / "metrics-report.md"),
        "units": len(units),
        "characters": result["aggregate"]["characters"],
        "dialogue_ratio": result["aggregate"]["dialogue_ratio"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())