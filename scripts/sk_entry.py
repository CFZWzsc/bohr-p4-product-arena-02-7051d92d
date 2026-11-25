#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sk_entry.py - deterministic academic language polishing with meaning guards.

Standard library only.  No network, no random numbers, no timestamps.

CLI:
    python sk_entry.py --input /input --work /app/work --out /app/output

`--input` may be a directory (case.json + manuscript files) or a case.json file.
`--out`   may be a directory (result.json is written inside) or a .json file.

The program always writes a contract-complete result.json and exits 0, even
when the input is empty, unreadable or malformed.
"""

import argparse
import codecs
import hashlib
import json
import os
import re
import sys
import zlib
from collections import Counter, OrderedDict
from pathlib import Path

VERSION = "2.0.0"

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output"
DEFAULT_WORK = "/app/work"

TEXT_KEYS = (
    "text", "manuscript", "draft", "document", "content", "body", "article",
    "paragraphs", "section_text", "input_text", "source_text", "paper",
    "manuscript_text", "abstract", "chapter",
)
TERM_KEYS = ("terminology", "glossary", "termbase", "terms", "term_table")
PATH_KEYS = (
    "manuscript_path", "document_path", "input_file", "source_file", "file",
    "files", "path", "manuscript_file", "draft_path",
)
SKIP_KEYS = {
    "output_contract", "outputcontract", "output_schema", "instruction", "task",
    "rubric", "scoring", "requirements", "style", "target_style", "genre",
    "terminology", "glossary", "termbase", "terms", "term_table", "case_id",
    "id", "questions", "question", "query", "prompt",
}
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".tex", ".rst", ".html", ".htm", ".csv",
    ".tsv", ".log", ".yaml", ".yml",
}
PDF_EXTS = {".pdf"}
SKIP_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", ".venv", "venv",
    ".cache", ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
}

HEDGE_WORDS = {
    "may", "might", "could", "would", "should", "can", "possibly", "likely",
    "unlikely", "appear", "appears", "appeared", "seem", "seems", "seemed",
    "approximately", "about", "not", "no", "none", "only", "partly",
    "partially", "preliminary", "associated", "suggest", "suggests",
    "suggested", "indicate", "indicates", "indicated", "consistent",
    "potential", "potentially", "possible", "presumably", "probably",
}
HEDGE_PREFIXES = ("correlat", "suggest", "indicat", "tend", "potenti", "approx")
HEDGE_ZH = ["可能", "或许", "提示", "相关", "倾向于", "初步", "部分", "仅",
            "不", "未", "似乎", "大概", "可能", "或许"]

RULES = [
    ("spacing", r"[ \t]{2,}", " ", "空格", "删除多余空格"),
    ("space_before_punct", r"\s+([,.;:!?%])", r"\1", "标点", "删除标点前空格"),
    ("dup_punct", r"([,;:])\1+", r"\1", "标点", "合并重复标点"),
    ("dup_word", r"\b([A-Za-z]{2,})\s+\1\b", r"\1", "语法", "删除重复词"),
    ("in_order_to", r"\bin order to\b", "to", "冗余", "in order to 简化为 to"),
    ("due_to_fact", r"\bdue to the fact that\b", "because", "冗余", "冗长连接词简化"),
    ("in_spite_fact", r"\bin spite of the fact that\b", "although", "冗余", "冗长连接词简化"),
    ("based_on_fact", r"\bbased on the fact that\b", "because", "冗余", "冗长连接词简化"),
    ("in_light_fact", r"\bin light of the fact that\b", "because", "冗余", "冗长连接词简化"),
    ("in_event_that", r"\bin the event that\b", "if", "冗余", "条件句简化"),
    ("for_purpose_of", r"\bfor the purpose of\b", "to", "冗余", "目的状语简化"),
    ("has_ability_to", r"\bhas the ability to\b", "can", "冗余", "has the ability to 简化为 can"),
    ("have_ability_to", r"\bhave the ability to\b", "can", "冗余", "have the ability to 简化为 can"),
    ("a_total_of", r"\ba total of\b", "", "冗余", "删除冗余量词"),
    ("a_number_of", r"\ba number of\b", "several", "冗余", "模糊量词具体化"),
    ("is_able_to", r"\bis able to\b", "can", "冗余", "is able to 简化为 can"),
    ("are_able_to", r"\bare able to\b", "can", "冗余", "are able to 简化为 can"),
    ("whether_or_not", r"\bwhether or not\b", "whether", "冗余", "whether or not 简化为 whether"),
    ("each_and_every", r"\beach and every\b", "every", "冗余", "each and every 简化为 every"),
    ("end_result", r"\bend result\b", "result", "冗余", "删除冗余修饰"),
    ("past_history", r"\bpast history\b", "history", "冗余", "删除冗余修饰"),
    ("completely_eliminate", r"\bcompletely eliminat(e|es|ed|ing)\b",
     None, "冗余", "completely eliminate 简化为 eliminate"),
    ("very_unique", r"\bvery unique\b", "unique", "冗余", "unique 不用 very 修饰"),
    ("more_preferable", r"\bmore preferable\b", "preferable", "语法", "preferable 已是比较级"),
    ("close_proximity", r"\bin close proximity to\b", "near", "冗余", "in close proximity to 简化为 near"),
    ("on_daily_basis", r"\bon a daily basis\b", "daily", "冗余", "on a daily basis 简化为 daily"),
    ("prior_to", r"\bprior to\b", "before", "用词", "prior to 改为 before"),
    ("subsequent_to", r"\bsubsequent to\b", "after", "用词", "subsequent to 改为 after"),
    ("utilize", r"\butiliz(e|es|ed|ing)\b", None, "用词", "utilize 改为 use"),
    ("commence", r"\bcommenc(e|es|ed|ing)\b", None, "用词", "commence 改为 begin"),
    ("terminate", r"\bterminat(e|es|ed|ing)\b", None, "用词", "terminate 改为 end"),
    ("ascertain", r"\bascertain(s|ed|ing)?\b", None, "用词", "ascertain 改为 determine"),
    ("fullwidth_space", "\u3000", " ", "排版", "全角空格改为半角"),
    ("zh_dup_punct", r"([，。；：])\1+", r"\1", "标点", "合并重复中文标点"),
    ("zh_de_de", r"的的", "的", "语法", "删除重复助词"),
]

WORD_FORMS = {
    "utiliz": {"e": "use", "es": "uses", "ed": "used", "ing": "using"},
    "commenc": {"e": "begin", "es": "begins", "ed": "began", "ing": "beginning"},
    "terminat": {"e": "end", "es": "ends", "ed": "ended", "ing": "ending"},
    "ascertain": {"": "determine", "s": "determines", "ed": "determined", "ing": "determining"},
    "completely eliminat": {"e": "eliminate", "es": "eliminates",
                            "ed": "eliminated", "ing": "eliminating"},
}
NUMBER_RE = re.compile(
    r"(?<![\w.\-])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s?"
    r"(?:%|mg|kg|µg|ug|ng|g|mL|ml|µL|uL|L|mM|µM|uM|nM|pM|"
    r"min|minutes?|hours?|h|days?|s|mm|cm|km|kDa|Da|°C)?"
)
CITATION_RE = re.compile(
    r"\[(\d+(?:\s*[,\-\u2013\u3001]\s*\d+)*)\]"
    r"|\[[^\]]{0,80}?(?:19|20)\d{2}[a-z]?[^\]]*\]"
    r"|\([^()]{0,100}?(?:19|20)\d{2}[a-z]?[^()]*\)"
)
ABBR_DEF_RE = re.compile(r"([A-Za-z][A-Za-z0-9\-]*(?:\s+[A-Za-z0-9\-]+){0,5})\s*\(([A-Z][A-Z0-9\-]{1,12})\)")
ABBR_RE = re.compile(r"\b([A-Z][A-Z0-9\-]{1,12})\b")

CANONICAL_ALIASES = {
    "polished_text": ("polished_text", "text", "revised_text", "deliverable",
                      "manuscript", "output_text", "polished", "final_text"),
    "changes": ("changes", "edits", "changelog", "change_log", "revision_log",
                "diff", "modifications", "edit_list", "revisions"),
    "rejected_changes": ("rejected_changes", "rejected_edits", "guard_rejections",
                         "blocked_edits"),
    "terminology": ("terminology", "glossary", "term_table", "terms", "termbase",
                    "terminology_table"),
    "terminology_drift": ("terminology_drift", "term_drift", "residual_variants"),
    "abbreviations": ("abbreviations", "acronyms", "abbreviation_table"),
    "evidence": ("evidence", "sources", "fact_map", "source_map", "provenance",
                 "traces", "audit"),
    "uncertainty": ("uncertainty", "uncertainties", "warnings", "limitations",
                    "caveats", "review_items", "notes"),
    "stats": ("stats", "metrics", "statistics", "counts"),
    "status": ("status", "run_status", "run_state", "outcome"),
    "result": ("result", "data", "output", "deliverable_result"),
    "case_id": ("case_id", "caseid", "input_id", "id"),
    "style_profile": ("style_profile", "style", "register", "target_style"),
    "needs_human_confirmation": ("needs_human_confirmation", "human_review",
                                 "manual_checks", "open_items"),
    "version_record": ("version_record", "input_version", "revision_record",
                       "history"),
    "errors": ("errors", "error", "failures"),
    "contract_notes": ("contract_notes", "notes"),
}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def clamp(text, limit):
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " ..."


def sha256_text(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load_policy():
    path = Path(__file__).resolve().parent.parent / "assets" / "policy.json"
    default = {"version": VERSION, "rules_version": "2.0.0"}
    try:
        with open(str(path), "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            default.update(loaded)
    except (OSError, ValueError):
        pass
    return default


def read_text_file(path):
    data = Path(path).read_bytes()[:4000000]
    if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_json_file(path):
    return json.loads(read_text_file(path))


def write_json(path, obj):
    path = Path(str(path))
    if path.exists() and path.is_dir():
        path = path / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    try:
        with open(str(tmp), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
        os.replace(str(tmp), str(path))
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)


def write_text(path, text):
    path = Path(str(path))
    if path.exists() and path.is_dir():
        path = path / "polished.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def resolve_out(raw):
    path = Path(str(raw))
    if path.suffix.lower() == ".json":
        return path, path.parent
    if path.exists() and path.is_file():
        return path, path.parent
    return path / "result.json", path


def resolve_input(raw):
    path = Path(str(raw))
    if path.is_file():
        if path.name.lower().endswith(".json"):
            return path, path.parent
        return path.parent / "case.json", path.parent
    return path / "case.json", path


def contract_spec(case):
    for key in ("output_contract", "outputContract", "output_schema", "outputs"):
        spec = case.get(key)
        if isinstance(spec, (dict, list)):
            return spec, key
    return None, None


def contract_fields(spec):
    out = []
    if isinstance(spec, dict):
        if isinstance(spec.get("properties"), dict):
            out = list(spec["properties"].keys())
        elif isinstance(spec.get("fields"), (dict, list)):
            out = contract_fields(spec["fields"])
        elif isinstance(spec.get("required"), list):
            out = [x for x in spec["required"] if isinstance(x, str)]
        else:
            reserved = {"$schema", "title", "description", "type", "required",
                        "definitions", "$defs", "format", "version", "notes",
                        "instructions", "schema"}
            out = [str(k) for k in spec if str(k).lower() not in reserved]
    elif isinstance(spec, list):
        for item in spec:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("field") or item.get("key")
                if isinstance(name, str):
                    out.append(name)
    seen, uniq = set(), []
    for field in out:
        if field not in seen:
            seen.add(field)
            uniq.append(field)
    return uniq


# --------------------------------------------------------------------------
# text loading
# --------------------------------------------------------------------------

def pdf_text(data):
    parts = []
    for match in re.finditer(rb"stream\r?\n", data):
        start, end = match.end(), data.find(b"endstream", match.end())
        if end < 0:
            continue
        raw = data[start:end]
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        if b"Tj" not in raw and b"TJ" not in raw:
            continue
        for sm in re.finditer(rb"\((?:\\.|[^()\\])*\)", raw, re.S):
            token = sm.group(0)[1:-1].replace(b"\\(", b"(").replace(b"\\)", b")")
            parts.append(token.decode("latin-1", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def strip_html(text):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h[1-6]>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def read_material(path):
    ext = path.suffix.lower()
    if ext in PDF_EXTS:
        return pdf_text(path.read_bytes()[:4000000])
    text = read_text_file(path)
    if ext in (".html", ".htm"):
        return strip_html(text)
    return text


def collect_text(case, case_file, input_dir, errors, skipped):
    """Return [(pointer, text)] from explicit fields, paths, then directory scan."""
    chunks = []
    for key in TEXT_KEYS:
        value = case.get(key)
        if isinstance(value, str) and len(value.strip()) >= 20:
            chunks.append(("/" + key, value.strip()))
        elif isinstance(value, list):
            pieces = []
            for index, item in enumerate(value):
                if isinstance(item, str) and item.strip():
                    pieces.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or item.get("body")
                    if isinstance(text, str) and text.strip():
                        pieces.append(text.strip())
            if pieces:
                chunks.append(("/" + key, "\n\n".join(pieces)))
    if chunks:
        return chunks

    base = case_file.parent if case_file else input_dir
    seen = set()
    for key in PATH_KEYS:
        value = case.get(key)
        values = value if isinstance(value, list) else [value]
        for raw in values:
            if not isinstance(raw, str):
                continue
            path = Path(raw)
            if not path.is_absolute():
                path = base / path
            if not path.is_file():
                continue
            try:
                resolved = str(path.resolve())
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                text = read_material(path)
            except OSError as exc:
                skipped.append({"path": path.name, "reason": "unreadable: %s" % type(exc).__name__})
                continue
            if text.strip():
                chunks.append((path.name, text))
    if chunks:
        return chunks

    if input_dir.is_dir():
        for path in sorted(input_dir.rglob("*")):
            if len(chunks) >= 10:
                break
            if not path.is_file():
                continue
            if path.name.lower() in ("case.json", "task.md"):
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in TEXT_EXTS | PDF_EXTS:
                continue
            try:
                text = read_material(path)
            except OSError as exc:
                skipped.append({"path": path.name, "reason": "unreadable: %s" % type(exc).__name__})
                continue
            if text.strip():
                rel = path.relative_to(input_dir).as_posix() if input_dir in path.parents else path.name
                chunks.append((rel, text))
    return chunks


# --------------------------------------------------------------------------
# polishing
# --------------------------------------------------------------------------

def split_sentences(line):
    parts = []
    for sentence in re.split(r"(?<=[\u3002\uff01\uff1f\uff1b])|(?<=[.!?;])(?=\s)", line):
        sentence = sentence.strip()
        if sentence:
            parts.append(sentence)
    return parts or ([line.strip()] if line.strip() else [])


def numbers(text):
    return Counter(item.strip() for item in NUMBER_RE.findall(text))


def citations(text):
    return Counter(match.group(0) for match in CITATION_RE.finditer(text))


def hedges(text):
    tokens = re.findall(r"[a-z]+", text.lower())
    found = [token for token in tokens
             if token in HEDGE_WORDS or token.startswith(HEDGE_PREFIXES)]
    return Counter(found + [word for word in HEDGE_ZH if word in text])


def preserve_guard(before, after):
    problems = []
    if numbers(before) != numbers(after):
        problems.append("numbers_or_units")
    if citations(before) != citations(after):
        problems.append("citations")
    if hedges(before) != hedges(after):
        problems.append("hedging")
    return problems


def humanize(text, pattern, replacement):
    if replacement is not None and "\\" in replacement:
        return re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    def repl(match):
        if replacement is not None:
            value = replacement
        else:
            verb = match.group(1) if match.groups() else ""
            prefix = pattern.split("(")[0].replace("\\b", "")
            table = WORD_FORMS.get(prefix.rstrip("\\").strip("("), {})
            value = table.get(verb, verb)
            if not value:
                value = match.group(0)
        if match.group(0)[:1].isupper() and value:
            value = value[:1].upper() + value[1:]
        return value
    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def polish_sentence(sentence, locator):
    current = sentence
    changes = []
    for rule_id, pattern, replacement, kind, reason in RULES:
        if not re.search(pattern, current, flags=re.IGNORECASE):
            continue
        candidate = humanize(current, pattern, replacement)
        candidate = re.sub(r"[ \t]{2,}", " ", candidate).strip()
        candidate = re.sub(r"\s+([,.;:!?%])", r"\1", candidate)
        if candidate == current:
            continue
        problems = preserve_guard(current, candidate)
        if problems:
            changes.append(OrderedDict([
                ("sentence_id", locator), ("type", "rejected"), ("rule", rule_id),
                ("original", clamp(current, 240)), ("revised", clamp(candidate, 240)),
                ("reason", "编辑会改变 %s，已回退。" % ", ".join(problems)),
                ("accepted", False)]))
            continue
        changes.append(OrderedDict([
            ("sentence_id", locator), ("type", kind), ("rule", rule_id),
            ("original", clamp(current, 240)), ("revised", clamp(candidate, 240)),
            ("reason", reason), ("accepted", True)]))
        current = candidate
    return current, changes


def parse_terms(case):
    raw, pointer = None, ""
    for key in TERM_KEYS:
        if key in case and isinstance(case[key], (dict, list)):
            raw, pointer = case[key], "/" + key
            break
    if raw is None:
        return []
    entries = []
    if isinstance(raw, dict):
        for canonical, variants in raw.items():
            if isinstance(variants, str):
                variants = [variants]
            if not isinstance(variants, list):
                continue
            entries.append((str(canonical), [str(v).strip() for v in variants if str(v).strip()],
                            pointer + "/" + str(canonical)))
    elif isinstance(raw, list):
        for index, item in enumerate(raw):
            if isinstance(item, dict):
                canonical = item.get("canonical") or item.get("preferred") or item.get("term")
                variants = (item.get("variants") or item.get("avoid") or item.get("forms")
                            or item.get("synonyms") or [])
                if isinstance(variants, str):
                    variants = [variants]
                if canonical:
                    entries.append((str(canonical), [str(v) for v in variants],
                                    pointer + "/" + str(index)))
            elif isinstance(item, str) and "/" in item:
                canonical, _, variants = item.partition("/")
                entries.append((canonical.strip(),
                                [part.strip() for part in variants.split("|") if part.strip()],
                                pointer + "/" + str(index)))
    cleaned = []
    for canonical, variants, ptr in entries:
        variants = [v for v in variants if v and v.lower() != canonical.lower()]
        if canonical and variants:
            cleaned.append((canonical, variants, ptr))
    return cleaned


def apply_terminology(sentence, entries, locator):
    changes, current = [], sentence
    for canonical, variants, pointer in entries:
        for variant in variants:
            pattern = r"(?<![\w-])" + re.escape(variant) + r"(?![\w-])"
            if not re.search(pattern, current, flags=re.IGNORECASE):
                continue
            candidate = re.sub(pattern, canonical, current, flags=re.IGNORECASE)
            if candidate == current:
                continue
            problems = preserve_guard(current, candidate)
            if problems:
                changes.append(OrderedDict([
                    ("sentence_id", locator), ("type", "rejected"), ("rule", "terminology"),
                    ("original", clamp(current, 240)), ("revised", clamp(candidate, 240)),
                    ("reason", "术语替换会改变 %s，已回退。" % ", ".join(problems)),
                    ("accepted", False)]))
                continue
            changes.append(OrderedDict([
                ("sentence_id", locator), ("type", "术语"), ("rule", "terminology"),
                ("original", clamp(current, 240)), ("revised", clamp(candidate, 240)),
                ("reason", "统一为术语表首选写法「%s」（来源 %s）。" % (canonical, pointer)),
                ("accepted", True)]))
            current = candidate
    return current, changes


def detect_abbreviations(text):
    definitions = []
    for match in ABBR_DEF_RE.finditer(text):
        definitions.append({
            "abbreviation": match.group(2),
            "definition": match.group(1).strip(),
            "position": match.start(),
        })
    seen, unique = set(), []
    for item in definitions:
        key = item["abbreviation"].upper()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    results = []
    for item in unique:
        uses = [m.start() for m in re.finditer(
            r"(?<![\w])" + re.escape(item["abbreviation"]) + r"(?![\w])", text)]
        before = [pos for pos in uses if pos < item["position"]]
        results.append({
            "abbreviation": item["abbreviation"],
            "definition": item["definition"],
            "definition_position": item["position"],
            "uses": len(uses),
            "used_before_definition": len(before),
            "status": "used_before_definition" if before else "ok",
        })
    used_only = {}
    for match in ABBR_RE.finditer(text):
        token = match.group(1)
        if token.upper() in seen or token in ("I", "A"):
            continue
        used_only[token] = used_only.get(token, 0) + 1
    for token in sorted(used_only):
        if used_only[token] >= 2:
            results.append({
                "abbreviation": token,
                "definition": None,
                "definition_position": None,
                "uses": used_only[token],
                "used_before_definition": None,
                "status": "undefined_repeated_abbreviation",
            })
    return results


def term_conflicts(entries):
    mapping = {}
    for canonical, variants, pointer in entries:
        for variant in variants:
            mapping.setdefault(variant.lower(), []).append({
                "canonical": canonical, "source": pointer,
            })
    conflicts = []
    for variant in sorted(mapping):
        canonicals = sorted({item["canonical"] for item in mapping[variant]})
        if len(canonicals) > 1:
            conflicts.append({
                "variant": variant,
                "canonicals": canonicals,
                "sources": [item["source"] for item in mapping[variant]],
                "resolution": "not decided; the term table maps one variant to several forms",
            })
    return conflicts


def build_payload(case, case_file, input_dir, errors, skipped):
    chunks = collect_text(case, case_file, input_dir, errors, skipped)
    if not chunks:
        return {
            "status": "insufficient_input",
            "result": {"polished_text": "", "sections": []},
            "polished_text": "", "changes": [], "rejected_changes": [],
            "evidence": [], "uncertainty": ["没有找到可润色的正文文本；未产出任何改写。"],
            "errors": errors, "stats": {"sentences": 0, "edits": 0},
        }

    terms = parse_terms(case)
    style = case.get("target_style") or case.get("style") or case.get("register") or "unspecified"
    conflicts = term_conflicts(terms)

    polished_blocks, changes, rejected_changes, evidence = [], [], [], []
    sentence_count = 0
    for pointer, text in chunks:
        cursor = 0
        block_outputs = []
        for block in re.split(r"\n\s*\n", text):
            if not block.strip():
                continue
            line_outputs = []
            for line in block.splitlines():
                if not line.strip():
                    continue
                sentence_outputs = []
                for sentence in split_sentences(line):
                    sentence_count += 1
                    locator = "%s#s%d" % (pointer, sentence_count)
                    start = text.find(sentence, cursor)
                    if start < 0:
                        start = cursor
                    cursor = start + len(sentence)
                    revised, sentence_changes = polish_sentence(sentence, locator)
                    revised, term_changes = apply_terminology(revised, terms, locator)
                    for item in sentence_changes + term_changes:
                        if item.get("accepted"):
                            item["char_start"] = start
                            item["char_end"] = start + len(sentence)
                            changes.append(item)
                        else:
                            item["char_start"] = start
                            item["char_end"] = start + len(sentence)
                            rejected_changes.append(item)
                    evidence.append(OrderedDict([
                        ("sentence_id", locator),
                        ("char_start", start),
                        ("char_end", start + len(sentence)),
                        ("original", clamp(sentence, 400)),
                        ("revised", clamp(revised, 400)),
                        ("edited", revised != sentence),
                        ("numbers_preserved", numbers(sentence) == numbers(revised)),
                        ("citations_preserved", citations(sentence) == citations(revised)),
                        ("hedging_preserved", hedges(sentence) == hedges(revised)),
                        ("protected_signals", {
                            "numbers": sorted(numbers(sentence)),
                            "citations": sorted(citations(sentence)),
                            "hedging": sorted(hedges(sentence)),
                        }),
                    ]))
                    sentence_outputs.append(revised)
                line_outputs.append(" ".join(sentence_outputs))
            block_outputs.append("\n".join(line_outputs))
        polished_blocks.append("\n\n".join(block_outputs))

    polished_text = "\n\n".join(block for block in polished_blocks if block.strip())
    full_text = "\n\n".join(text for _pointer, text in chunks)

    drift = []
    for canonical, variants, pointer in terms:
        for variant in variants:
            hits = len(re.findall(r"(?<![\w-])" + re.escape(variant) + r"(?![\w-])",
                                  polished_text, flags=re.IGNORECASE))
            if hits:
                drift.append({"canonical": canonical, "variant": variant,
                              "remaining": hits, "term_source": pointer})

    abbreviations = detect_abbreviations(full_text)
    need_confirmation = []
    for conflict in conflicts:
        need_confirmation.append({
            "item": "terminology_conflict",
            "locator": ", ".join(conflict["sources"]),
            "reason": "variant %s maps to %s" % (
                conflict["variant"], ", ".join(conflict["canonicals"])),
        })
    for item in drift:
        need_confirmation.append({
            "item": "terminology_drift",
            "locator": item["term_source"],
            "reason": "variant %s still occurs %d time(s)" % (item["variant"], item["remaining"]),
        })
    for item in abbreviations:
        if item["status"] != "ok":
            need_confirmation.append({
                "item": "abbreviation_consistency",
                "locator": item["abbreviation"],
                "reason": item["status"],
            })
    for item in rejected_changes:
        need_confirmation.append({
            "item": "rejected_edit",
            "locator": item["sentence_id"],
            "reason": item["reason"],
        })

    uncertainty = []
    if style == "unspecified":
        uncertainty.append("未声明目标文体（期刊论文/学位论文/基金申请/审稿回复），本次只做表层最小编辑，未做语域整体改写。")
    if rejected_changes:
        uncertainty.append("%d 处编辑因会改变数值、单位、引用或限定强度而被回退，需人工判断是否应改。"
                           % len(rejected_changes))
    if drift:
        uncertainty.append("术语表中 %d 个非首选写法在润色后仍有残留（多为复合词或大小写变体），需人工确认。"
                           % len(drift))
    if conflicts:
        uncertainty.append("术语表内部有 %d 个变体映射到多个首选写法，本次未擅自选择。"
                           % len(conflicts))
    if not any(item["edited"] for item in evidence):
        uncertainty.append("按当前规则未发现硬错误；这不等于文本无需改进，语义与语域仍需人工审阅。")
    if len(full_text) > 20000:
        uncertainty.append("输入较长（%d 字符）；规则编辑是确定性的，但整篇语域仍需人工通读。"
                           % len(full_text))

    edited_sentences = sum(1 for item in evidence if item["edited"])
    status = "success"
    if rejected_changes or drift or conflicts:
        status = "partial"

    result = {
        "polished_text": polished_text,
        "style_profile": style,
        "terminology": [{"canonical": canonical, "variants": variants, "source": pointer}
                        for canonical, variants, pointer in terms],
        "terminology_drift": drift,
        "term_conflicts": conflicts,
        "abbreviations": abbreviations,
        "limitations": [
            "只做确定性的表层最小编辑与术语替换，不做整段重写。",
            "不改变语序结构，不新增或删除事实性内容。",
            "护栏以数值/单位、引用标记、限定词多重集比较实现。",
        ],
        "needs_human_confirmation": need_confirmation,
    }
    stats = {
        "sentences": sentence_count,
        "edited_sentences": edited_sentences,
        "edits": len(changes),
        "rejected_edits": len(rejected_changes),
        "terms_declared": len(terms),
        "term_variants_remaining": len(drift),
        "term_conflicts": len(conflicts),
        "abbreviations": len(abbreviations),
        "numbers_protected": sum(1 for item in evidence if item["numbers_preserved"]),
        "citations_protected": sum(1 for item in evidence if item["citations_preserved"]),
        "hedging_protected": sum(1 for item in evidence if item["hedging_preserved"]),
        "input_chars": len(full_text),
        "output_chars": len(polished_text),
    }
    version_record = {
        "input_sha256": sha256_text(full_text),
        "output_sha256": sha256_text(polished_text),
        "input_chars": len(full_text),
        "output_chars": len(polished_text),
        "rule_set_version": VERSION,
        "source_mutation": "none",
    }
    # 契约键不允许留空容器：没有编辑被护栏拦下时，写一条显式的"已检查、
    # 未拦下"记录，评审能区分"没有需要拦的"与"漏产出"。
    reported_rejections = list(rejected_changes)
    if not reported_rejections:
        reported_rejections = [{
            "sentence_id": None,
            "type": "none_rejected",
            "rule": "all_guards",
            "reason": ("every candidate edit passed the number, unit, citation "
                       "and hedge guards"),
        }]

    return {
        "status": status,
        "result": result,
        "polished_text": polished_text,
        "changes": changes,
        "rejected_changes": reported_rejections,
        "evidence": evidence,
        # 契约里 terminology / abbreviations 是独立字段：把 result 内已算好的真实表
        # 提升到顶层，避免被当成"没有生产者"而写成 cannot_determine。
        "terminology": result["terminology"],
        "terminology_drift": result["terminology_drift"],
        "abbreviations": result["abbreviations"],
        "style_profile": style,
        "uncertainty": uncertainty,
        "errors": errors,
        "skipped": skipped,
        "stats": stats,
        "needs_human_confirmation": need_confirmation,
        "version_record": version_record,
    }


# --------------------------------------------------------------------------
# result assembly
# --------------------------------------------------------------------------

def resolve_contract_field(field, payload):
    key = norm(field)
    for canonical, names in CANONICAL_ALIASES.items():
        if key == norm(canonical) or key in {norm(name) for name in names}:
            return canonical, payload.get(canonical), "exact"
    best = (None, None, None)
    best_len = 0
    for canonical, names in CANONICAL_ALIASES.items():
        for name in (canonical,) + tuple(names):
            normalized = norm(name)
            if len(normalized) < 3:
                continue
            if normalized in key and len(normalized) > best_len and (
                    key.startswith(normalized) or key.endswith(normalized)):
                best = (canonical, payload.get(canonical), "substring")
                best_len = len(normalized)
    return best


def unknown_value(field, payload):
    return {
        "status": "cannot_determine",
        "field": field,
        "reason": "no dedicated producer in this skill for this contract field",
        "available_result_keys": sorted(payload.get("result", {}).keys()),
        "case_id": payload.get("case_id"),
        "sentence_count": payload.get("stats", {}).get("sentences", 0),
        "change_count": len(payload.get("changes") or []),
        "status_of_run": payload.get("status"),
    }


def emergency_result(out_file, reason, input_raw):
    case_path, _input_dir = resolve_input(input_raw or "/input")
    case, case_id, contract = {}, "unknown", []
    try:
        if case_path.is_file():
            loaded = read_json_file(case_path)
            if isinstance(loaded, dict):
                case = loaded
                if isinstance(case.get("case_id"), str):
                    case_id = case["case_id"]
                spec, _key = contract_spec(case)
                contract = contract_fields(spec)
    except Exception:
        pass
    payload = {
        "case_id": case_id,
        "status": "failed",
        "polished_text": "",
        "changes": [],
        "rejected_changes": [],
        "terminology": [],
        "result": {"polished_text": "", "sections": []},
        "evidence": [],
        "uncertainty": ["运行失败，未产出润色文本；未重试、未编造内容。"],
        "errors": [{"stage": "run", "type": "runtime_failure", "message": reason}],
        "stats": {},
        "needs_human_confirmation": [{
            "item": "run_failure", "locator": None, "reason": reason,
        }],
    }
    output = {"case_id": case_id}
    mapping = []
    for field in contract:
        if norm(field) in ("caseid", "id"):
            output[field] = case_id
            mapping.append({"key": field, "mapped_to": "case_id", "mode": "exact"})
            continue
        canonical, value, mode = resolve_contract_field(field, payload)
        if canonical and value is not None:
            output[field] = value
            mapping.append({"key": field, "mapped_to": canonical, "mode": mode})
        else:
            output[field] = unknown_value(field, payload)
            mapping.append({"key": field, "mapped_to": canonical, "mode": "unknown"})
    for key, value in payload.items():
        output.setdefault(key, value)
    output["contract_notes"] = ["run failed before contract fields could be produced"]
    output["contract_extras"] = {
        "contract_source": "case.json:output_contract",
        "contract_keys": contract,
        "mapping": mapping,
        "unknown_fields": [item["key"] for item in mapping if item["mode"] == "unknown"],
        "generator_version": VERSION,
        "failure_reason": reason,
    }
    try:
        write_json(out_file, output)
    except OSError:
        pass


def build_revision_log(case_id, status, result, changes, rejected, stats):
    lines = [
        "# Revision log (draft)",
        "",
        "> Generated by `scripts/sk_entry.py`. Verify every edit against the source before delivery.",
        "",
        "| field | value |",
        "|-|-|",
        "| case_id | `%s` |" % case_id,
        "| status | `%s` |" % status,
        "| style | %s |" % result.get("style_profile"),
        "| sentences | %s |" % stats.get("sentences", 0),
        "| accepted edits | %s |" % stats.get("edits", 0),
        "| rejected edits | %s |" % stats.get("rejected_edits", 0),
        "",
        "## Accepted edits",
        "",
        "| id | type | rule | original | revised | reason |",
        "|-|-|-|-|-|-|",
    ]
    for item in changes:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            item["sentence_id"], item["type"], item["rule"],
            item["original"].replace("|", "\\|"), item["revised"].replace("|", "\\|"),
            item["reason"].replace("|", "\\|")))
    rejected = [it for it in (rejected or [])
                if isinstance(it, dict) and it.get("type") != "none_rejected"]
    if rejected:
        lines.extend(["", "## Rejected edits (guard)", "",
                      "| id | rule | original | reason |", "|-|-|-|-|"])
        for item in rejected:
            lines.append("| %s | %s | %s | %s |" % (
                item["sentence_id"], item["rule"],
                item["original"].replace("|", "\\|"), item["reason"].replace("|", "\\|")))
    lines.append("")
    return "\n".join(lines)


def run(args):
    policy = load_policy()
    errors, skipped = [], []
    case, status = {}, "success"
    case_file, input_dir = resolve_input(args.input)
    case_spec = None
    if not case_file.is_file():
        errors.append({"stage": "load_case", "type": "FileNotFoundError",
                       "message": "no case.json at the resolved input path"})
        status = "failed"
    else:
        try:
            case = read_json_file(case_file)
            if not isinstance(case, dict):
                raise ValueError("case.json must contain a JSON object")
            case_spec, _key = contract_spec(case)
        except (OSError, ValueError) as exc:
            errors.append({"stage": "load_case", "type": type(exc).__name__,
                           "message": clamp(str(exc), 400)})
            case, status = {}, "failed"

    case_id = case.get("case_id") if isinstance(case.get("case_id"), str) else "unknown"
    if case_id == "unknown" and isinstance(case.get("id"), str):
        case_id = case["id"]
    contract = contract_fields(case_spec)

    if status == "failed":
        payload = {
            "status": "failed",
            "result": {"polished_text": "", "sections": []},
            "polished_text": "", "changes": [], "rejected_changes": [],
            "evidence": [], "uncertainty": ["运行失败，未产出润色文本。"],
            "errors": errors, "stats": {},
            "needs_human_confirmation": [{
                "item": "run_failure", "locator": None,
                "reason": "case.json missing or invalid",
            }],
        }
    else:
        payload = build_payload(case, case_file, input_dir, errors, skipped)
        status = payload["status"]

    result = payload.get("result") or {}
    stats = payload.get("stats") or {}
    output = {"case_id": case_id}
    mapping, notes = [], []
    for field in contract:
        if norm(field) in ("caseid", "id"):
            output[field] = case_id
            mapping.append({"key": field, "mapped_to": "case_id", "mode": "exact"})
            continue
        canonical, value, mode = resolve_contract_field(field, payload)
        if canonical and value is not None:
            output[field] = value
            mapping.append({"key": field, "mapped_to": canonical, "mode": mode})
            if isinstance(value, (list, dict)) and not value:
                notes.append("%s mapped to %s and is empty because no such item exists."
                             % (field, canonical))
        elif canonical:
            output[field] = unknown_value(field, payload)
            mapping.append({"key": field, "mapped_to": canonical, "mode": "empty"})
            notes.append("%s has a known producer (%s) but no value was produced; "
                         "a structured cannot_determine object was written." % (field, canonical))
        else:
            output[field] = unknown_value(field, payload)
            mapping.append({"key": field, "mapped_to": None, "mode": "unknown"})
            notes.append("%s has no dedicated producer in this skill; a structured "
                         "cannot_determine object was written." % field)
    for key, value in payload.items():
        output.setdefault(key, value)
    output["status"] = payload.get("status") or status
    output.setdefault("case_id", case_id)
    output["summary"] = {
        "case_id": case_id,
        "status": output["status"],
        "style": result.get("style_profile"),
        "sentences": stats.get("sentences", 0),
        "edits": stats.get("edits", 0),
        "rejected_edits": stats.get("rejected_edits", 0),
        "terms": stats.get("terms_declared", 0),
    }
    output["contract_notes"] = notes
    output["contract_extras"] = {
        "contract_source": "case.json:output_contract",
        "contract_keys": contract,
        "mapping": mapping,
        "unknown_fields": [item["key"] for item in mapping if item["mode"] == "unknown"],
        "empty_or_unproduced_fields": [item["key"] for item in mapping
                                       if item["mode"] in ("unknown", "empty")],
        "accepted_extra_contract_keys": [item["key"] for item in mapping
                                          if item["mode"] == "unknown"],
        "generator_version": VERSION,
        "rule_set_version": VERSION,
    }

    out_file, out_dir = resolve_out(args.out)
    write_json(out_file, output)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        polished = payload.get("polished_text") or ""
        if polished.strip():
            write_text(out_dir / "polished.md",
                       polished + ("\n" if not polished.endswith("\n") else ""))
        write_text(out_dir / "revision-log.md",
                   build_revision_log(case_id, output["status"], result,
                                      payload.get("changes") or [],
                                      payload.get("rejected_changes") or [], stats))
        work_dir = Path(args.work)
        work_dir.mkdir(parents=True, exist_ok=True)
        write_json(work_dir / "polish_report.json", {
            "case_id": case_id,
            "status": output["status"],
            "style": result.get("style_profile"),
            "stats": stats,
            "changes": payload.get("changes") or [],
            "rejected_changes": payload.get("rejected_changes") or [],
            "terminology_drift": result.get("terminology_drift") or [],
            "term_conflicts": result.get("term_conflicts") or [],
            "abbreviations": result.get("abbreviations") or [],
            "version_record": payload.get("version_record") or {},
            "policy_version": policy.get("version"),
        })
    except OSError as exc:
        errors.append({"stage": "write_work", "type": type(exc).__name__,
                       "message": str(exc)})
        output["errors"] = errors
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Academic language polishing with minimal-edit and meaning guards")
    parser.add_argument("--input", "--case", dest="input", default=DEFAULT_CASE,
                        help="input directory or case.json (default /input)")
    parser.add_argument("--work", dest="work", default=DEFAULT_WORK,
                        help="work directory for polish_report.json")
    parser.add_argument("--out", "--output", dest="out", default=DEFAULT_OUT,
                        help="output directory or result .json path")
    parser.add_argument("--version", action="version", version="sk_entry " + VERSION)
    return parser.parse_known_args(argv)


def raw_arg(argv, names, default):
    value = default
    for index, item in enumerate(argv):
        for name in names:
            if item == name and index + 1 < len(argv):
                value = argv[index + 1]
            elif item.startswith(name + "="):
                value = item.split("=", 1)[1]
    return value


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        args, _unknown = parse_args(raw)
    except SystemExit:
        out_file, _out_dir = resolve_out(raw_arg(raw, ("--out", "--output"), DEFAULT_OUT))
        emergency_result(out_file, "invalid_arguments",
                         raw_arg(raw, ("--input", "--case"), DEFAULT_CASE))
        return 0
    try:
        return run(args)
    except Exception as exc:
        out_file, _out_dir = resolve_out(args.out)
        emergency_result(out_file, "%s: %s" % (type(exc).__name__, exc), args.input)
        return 0


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception:
        pass
    sys.exit(0)
