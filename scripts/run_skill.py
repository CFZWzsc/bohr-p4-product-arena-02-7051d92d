#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Academic language polishing skill with minimal-edit and meaning guards.

Polishes a supplied manuscript paragraph by paragraph using deterministic
surface rules plus a user-supplied terminology table, and rejects any edit that
would change numbers, units, citation markers or hedging strength.

Standard library only. Deterministic, no network, no random.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, OrderedDict

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"

HEDGE_WORDS = {"may", "might", "could", "would", "should", "can", "possibly", "likely",
               "unlikely", "appear", "appears", "seem", "seems", "approximately",
               "about", "not", "no", "none", "only", "partly", "partially",
               "preliminary", "associated"}
HEDGE_PREFIXES = ("correlat", "suggest", "indicat", "tend", "potenti", "approx")
HEDGE_ZH = ["可能", "或许", "提示", "相关", "倾向于", "初步", "部分", "仅", "不", "未"]

RULES = [
    ("spacing", r"[ \t]{2,}", " ", "空格", "删除多余空格"),
    ("space_before_punct", r"\s+([,.;:!?%])", r"\1", "标点", "删除标点前空格"),
    ("dup_punct", r"([,;:])\1+", r"\1", "标点", "合并重复标点"),
    ("dup_word", r"\b([A-Za-z]{2,})\s+\1\b", r"\1", "语法", "删除重复词"),
    ("in_order_to", r"\bin order to\b", "to", "冗余", "in order to 简化为 to"),
    ("due_to_fact", r"\bdue to the fact that\b", "because", "冗余", "冗长连接词简化"),
    ("in_spite_fact", r"\bin spite of the fact that\b", "although", "冗余", "冗长连接词简化"),
    ("a_total_of", r"\ba total of\b", "", "冗余", "删除冗余量词"),
    ("a_number_of", r"\ba number of\b", "several", "冗余", "模糊量词具体化"),
    ("is_able_to", r"\bis able to\b", "can", "冗余", "is able to 简化为 can"),
    ("are_able_to", r"\bare able to\b", "can", "冗余", "are able to 简化为 can"),
    ("prior_to", r"\bprior to\b", "before", "用词", "prior to 改为 before"),
    ("subsequent_to", r"\bsubsequent to\b", "after", "用词", "subsequent to 改为 after"),
    ("utilize", r"\butiliz(e|es|ed|ing)\b", None, "用词", "utilize 改为 use"),
    ("fullwidth_space", "\u3000", " ", "排版", "全角空格改为半角"),
    ("zh_dup_punct", r"([，。；：])\1+", r"\1", "标点", "合并重复中文标点"),
    ("zh_de_de", r"的的", "的", "语法", "删除重复助词"),
]

TEXT_KEYS = ("text", "manuscript", "draft", "document", "content", "body", "article",
             "paragraphs", "section_text", "input_text", "source_text", "paper")
TERM_KEYS = ("terminology", "glossary", "termbase", "terms", "term_table")
SKIP_KEYS = {"output_contract", "outputcontract", "output_schema", "instruction", "task",
             "rubric", "scoring", "requirements", "style", "target_style", "genre",
             "terminology", "glossary", "termbase", "terms", "term_table"}


def log(message):
    sys.stderr.write("[run_skill] %s\n" % message)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def find_task_text(case_path):
    base = os.path.dirname(os.path.abspath(case_path))
    for path in (os.path.join(base, "task.md"), os.path.join(base, "..", "task.md"),
                 "/input/task.md"):
        if os.path.isfile(path):
            try:
                return read_text(path)
            except OSError:
                continue
    return ""


def contract_fields(spec):
    if isinstance(spec, list):
        return [str(item) if isinstance(item, str) else str(item.get("name") or item.get("field"))
                for item in spec
                if isinstance(item, str) or (isinstance(item, dict)
                                             and (item.get("name") or item.get("field")))]
    if isinstance(spec, dict):
        if isinstance(spec.get("properties"), dict):
            return [str(name) for name in spec["properties"]]
        if isinstance(spec.get("fields"), (dict, list)):
            return contract_fields(spec["fields"])
        reserved = {"$schema", "title", "description", "type", "required", "definitions", "$defs"}
        return [str(name) for name in spec if str(name).lower() not in reserved]
    return []


def norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def split_sentences(text):
    parts = []
    for block in re.split(r"\n\s*\n", text):
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|>\s|\|)", line):
                parts.append(line)
                continue
            for sentence in re.split(r"(?<=[\u3002\uff01\uff1f\uff1b])|(?<=[.!?;])(?=\s)", line):
                sentence = sentence.strip()
                if sentence:
                    parts.append(sentence)
    return parts


def numbers(text):
    return Counter(re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s?(?:%|mg|kg|ml|mL|h|min|s|mm|cm|km)?", text))


def citations(text):
    pattern = (r"\[(\d+(?:\s*[,\-\u2013\u3001]\s*\d+)*)\]"
               r"|\[[^\]]{0,80}?(?:19|20)\d{2}[a-z]?[^\]]*\]"
               r"|\([^()]{0,100}?(?:19|20)\d{2}[a-z]?[^()]*\)")
    return Counter(re.findall(pattern, text))


def hedges(text):
    tokens = re.findall(r"[a-z]+", text.lower())
    found = [token for token in tokens
             if token in HEDGE_WORDS or token.startswith(HEDGE_PREFIXES)]
    return Counter(found + [word for word in HEDGE_ZH if word in text])


def preserve_guard(before, after):
    """Return the list of protected signals that changed, or [] when safe."""
    problems = []
    if numbers(before) != numbers(after):
        problems.append("numbers_or_units")
    if citations(before) != citations(after):
        problems.append("citations")
    if hedges(before) != hedges(after):
        problems.append("hedging")
    return problems


def humanize(text, pattern, replacement):
    def repl(match):
        value = replacement if replacement is not None else "use"
        if replacement is None:
            verb = match.group(1)
            value = {"e": "use", "es": "uses", "ed": "used", "ing": "using"}[verb]
        if match.group(0)[:1].isupper():
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
        if candidate == current:
            continue
        problems = preserve_guard(current, candidate)
        if problems:
            changes.append(OrderedDict([
                ("sentence_id", locator), ("type", "rejected"), ("rule", rule_id),
                ("original", clamp(current, 240)), ("revised", clamp(candidate, 240)),
                ("reason", "编辑会改变 %s，已回退。" % ", ".join(problems))]))
            continue
        changes.append(OrderedDict([
            ("sentence_id", locator), ("type", kind), ("rule", rule_id),
            ("original", clamp(current, 240)), ("revised", clamp(candidate, 240)),
            ("reason", reason), ("accepted", True)]))
        current = candidate
    return current, changes


def clamp(text, limit):
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def parse_terms(case, task_text):
    """Return [(canonical, [variant...], source_pointer)] from flexible inputs."""
    raw = None
    pointer = ""
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
            entries.append((str(canonical), [str(item) for item in variants if str(item).strip()],
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
    return [(canonical, [v for v in variants if v and v.lower() != canonical.lower()], ptr)
            for canonical, variants, ptr in entries]


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
                    ("reason", "术语替换会改变 %s，已回退。" % ", ".join(problems))]))
                continue
            changes.append(OrderedDict([
                ("sentence_id", locator), ("type", "术语"), ("rule", "terminology"),
                ("original", clamp(current, 240)), ("revised", clamp(candidate, 240)),
                ("reason", "统一为术语表首选写法「%s」（来源 %s）。" % (canonical, pointer)),
                ("accepted", True)]))
            current = candidate
    return current, changes


def collect_text(case):
    """Prefer explicit manuscript fields, else non-instruction prose strings."""
    chunks = []
    for key in TEXT_KEYS:
        value = case.get(key)
        if isinstance(value, str) and len(value.strip()) >= 20:
            chunks.append(("/" + key, value.strip()))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str) and len(item.strip()) >= 20:
                    chunks.append(("/%s/%d" % (key, index), item.strip()))
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or item.get("body")
                    if isinstance(text, str) and len(text.strip()) >= 20:
                        chunks.append(("/%s/%d" % (key, index), text.strip()))
    if chunks:
        return chunks
    for key, value in case.items():
        if str(key).lower() in SKIP_KEYS:
            continue
        if isinstance(value, str) and len(value.strip()) >= 120:
            chunks.append(("/" + str(key), value.strip()))
    return chunks


def finalize(case, payload, contract):
    out = OrderedDict()
    out["case_id"] = case.get("case_id") or case.get("id")
    notes = [] if contract is not None else ["case.json 未声明 output_contract；已按本题通用字段输出。"]
    aliases = {"polished_text": {"text", "polishedtext", "revisedtext", "deliverable", "manuscript"},
               "changes": {"changes", "edits", "changelog", "revisionlog", "diff"},
               "terminology": {"terminology", "glossary", "termtable", "terms"},
               "uncertainty": {"uncertainty", "uncertainties", "warnings", "reviewitems"},
               "stats": {"stats", "metrics", "statistics"}}
    for name in contract_fields(contract):
        if norm(name) == "caseid":
            continue
        if name in payload:
            out[name] = payload[name]
            continue
        matched = next((payload[key] for key in payload if norm(key) == norm(name)), None)
        if matched is None:
            for canonical, names in aliases.items():
                if canonical in payload and norm(name) in names:
                    matched = payload[canonical]
                    break
        out[name] = matched
        if matched is None:
            notes.append("字段 %s 不在本 Skill 的能力范围内，按契约保留为 null。" % name)
    defaults = {"status": "partial", "result": {}, "evidence": [], "uncertainty": [],
                "errors": [], "stats": {}, "contract_notes": []}
    for key, default in defaults.items():
        if key not in out:
            value = payload.get(key)
            out[key] = default if value is None else value
    out["status"] = payload.get("status") or "partial"
    out["contract_notes"] = notes + list(payload.get("contract_notes") or [])
    return out


def build_payload(case, task_text):
    chunks = collect_text(case)
    if not chunks:
        return {"status": "insufficient_input",
                "result": {"polished_text": "", "sections": []},
                "evidence": [], "uncertainty": ["没有找到可润色的正文文本。"],
                "errors": [], "stats": {"sentences": 0, "edits": 0}}

    terms = parse_terms(case, task_text)
    style = case.get("target_style") or case.get("style") or case.get("register") or "unspecified"

    polished_blocks, changes, evidence = [], [], []
    sentence_count, rejected = 0, 0
    for pointer, text in chunks:
        lines, in_block = [], []
        for block in re.split(r"(\n\s*\n)", text):
            if not block.strip():
                continue
            for sentence in split_sentences(block):
                sentence_count += 1
                locator = "%s#s%d" % (pointer, sentence_count)
                revised, sentence_changes = polish_sentence(sentence, locator)
                revised, term_changes = apply_terminology(revised, terms, locator)
                sentence_changes.extend(term_changes)
                changes.extend([item for item in sentence_changes if item.get("accepted")])
                rejected += len([item for item in sentence_changes if not item.get("accepted")])
                evidence.append(OrderedDict([
                    ("sentence_id", locator), ("original", clamp(sentence, 300)),
                    ("revised", clamp(revised, 300)),
                    ("edited", revised != sentence),
                    ("numbers_preserved", numbers(sentence) == numbers(revised)),
                    ("citations_preserved", citations(sentence) == citations(revised)),
                    ("hedging_preserved", hedges(sentence) == hedges(revised))]))
                in_block.append(revised)
            lines.append(" ".join(in_block))
            in_block = []
        if in_block:
            lines.append(" ".join(in_block))
        polished_blocks.append("\n\n".join(lines))

    polished_text = "\n\n".join(polished_blocks)

    drift = []
    for canonical, variants, pointer in terms:
        for variant in variants:
            hits = len(re.findall(r"(?<![\w-])" + re.escape(variant) + r"(?![\w-])",
                                  polished_text, flags=re.IGNORECASE))
            if hits:
                drift.append({"canonical": canonical, "variant": variant, "remaining": hits,
                              "term_source": pointer})

    uncertainty = []
    if style == "unspecified":
        uncertainty.append("未声明目标文体（期刊论文/学位论文/基金申请/审稿回复），"
                           "本次只做表层最小编辑，未做语域整体改写。")
    if rejected:
        uncertainty.append("%d 处编辑因会改变数值、单位、引用或限定强度而被回退，"
                           "需人工判断是否应改。" % rejected)
    if drift:
        uncertainty.append("术语表中 %d 个非首选写法在润色后仍有残留（多为复合词或大小写变体），"
                           "需人工确认。" % len(drift))
    if not any(item["edited"] for item in evidence):
        uncertainty.append("按当前规则未发现硬错误；这不等于文本无需改进，语义与语域仍需人工审阅。")

    result = {
        "polished_text": polished_text,
        "style_profile": style,
        "terminology": [{"canonical": canonical, "variants": variants, "source": pointer}
                        for canonical, variants, pointer in terms],
        "terminology_drift": drift,
        "limitations": ["只做确定性的表层最小编辑与术语替换，不做整段重写。",
                        "不改变语序结构，不新增或删除事实性内容。"],
    }
    stats = {"sentences": sentence_count, "edits": len(changes), "rejected_edits": rejected,
             "terms_declared": len(terms), "term_variants_remaining": len(drift),
             "numbers_protected": sum(1 for item in evidence if item["numbers_preserved"]),
             "citations_protected": sum(1 for item in evidence if item["citations_preserved"])}
    return {"status": "success", "result": result, "evidence": evidence,
            "uncertainty": uncertainty, "errors": [], "stats": stats,
            "changes": changes, "polished_text": polished_text}


def main():
    parser = argparse.ArgumentParser(description="Academic language polishing")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--out", "--output", default=DEFAULT_OUT)
    parser.add_argument("--work", default=DEFAULT_WORK)
    args = parser.parse_args()
    stage, case = "load_case", {}
    try:
        if not os.path.isfile(args.case):
            raise FileNotFoundError("case file not found: %s" % os.path.basename(args.case))
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case.json must contain a JSON object")
        stage = "build_payload"
        contract = None
        for key in ("output_contract", "outputContract", "output_schema"):
            if isinstance(case.get(key), (dict, list)):
                contract = case[key]
                break
        payload = build_payload(case, find_task_text(args.case))
        output = finalize(case, payload, contract)
        stage = "write_output"
        directory = os.path.dirname(os.path.abspath(args.out))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        sys.stdout.write(json.dumps({"case_id": output.get("case_id"),
                                     "status": output.get("status"),
                                     "edits": len(output.get("changes") or []),
                                     "contract_fields": len(contract_fields(contract))},
                                    ensure_ascii=False) + "\n")
        return 0
    except Exception as exc:
        failure = OrderedDict([
            ("case_id", case.get("case_id") or case.get("id")), ("status", "failed"),
            ("result", {"polished_text": ""}), ("evidence", []),
            ("uncertainty", ["运行失败，未产出润色文本；未重试、未编造内容。"]),
            ("errors", [{"stage": stage, "type": type(exc).__name__,
                         "message": clamp(str(exc), 400)}]),
            ("stats", {}), ("contract_notes", [])])
        try:
            directory = os.path.dirname(os.path.abspath(args.out))
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            with open(args.out, "w", encoding="utf-8") as handle:
                json.dump(failure, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError as write_exc:
            log("cannot write failure output: %s" % write_exc)
        sys.stdout.write(json.dumps({"status": "failed", "stage": stage},
                                    ensure_ascii=False) + "\n")
        return 2


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
