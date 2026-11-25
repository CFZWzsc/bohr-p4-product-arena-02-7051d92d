---
name: academic-language-polisher
description: Use when a case supplies an academic manuscript and asks for language polishing or terminology consistency; performs deterministic minimal edits with guards that preserve numbers, units, citations and hedging, then writes a contract-complete /app/output/result.json plus polished.md.
---

## 执行纪律（硬性，优先于下文流程）

1. 先落盘骨架：读到 `/input/case.json` 后立即写 `/app/output/result.json` 骨架 —— `case_id` 取自输入，`output_contract` 的每个键都要在，未完成的填 `unknown` 或空容器，**绝不省略键**。
2. 字段一个不缺：交付前逐键核对 `output_contract`；缺数据时保留键并在 `uncertainty` 写明原因，不编造数字、日期、引用。
3. 广度优先：先让所有要求的产物以最小合格版本存在，再加深高价值部分。
4. 预算保护：脚本一次执行即完成全部判断与产出，不依赖第二个回合；接近预算时用现有中间结果收尾。
5. 写盘前自检：JSON 可解析、契约键不缺、`case_id` 与输入一致、`status` 如实。
6. 失败也交付：异常路径仍写出 `result.json`（如实标注中断位置与已完成部分），进程退出码为 0。

# 学术语言润色（最小编辑 / 术语统一 / 事实与引用护栏）

## 用途

对论文、学位论文、基金申请、审稿回复等学术文本做**确定性的表层润色**，并在改写前后保留事实与来源：

1. 删除冗余表达、修正重复词/多余空格/标点前空格、统一常见学术用词（`in order to` → `to`、`prior to` → `before`、`utilize` → `use`）。
2. 按作者提供的术语表统一写法（如 `FEV-1` → `FEV1`），并报告残留变体。
3. 对每一句做**护栏检查**：数值与单位、引用标记、限定/否定词的多重集必须保持不变；会改变这些信号的编辑一律回退并记录。
4. 逐句输出原文/改写、字符定位、受保护信号，生成 `polished.md` 与修订日志。
5. 输出 `result.json`，覆盖输入 `output_contract` 的每一个键，并给出 `status`、`uncertainty`、`errors`、`stats`。

本 Skill **不做整段重写**，不新增文献，不改变论证结论。

## 适用条件

- 输入包含 `case.json`，正文位于 `text` / `manuscript` / `draft` / `document` / `content` / `paragraphs` 等字段，或通过 `manuscript_path` / `files` / `path` 指向本地正文文件。
- 任务要求语言润色、术语统一、投稿前语言检查、审稿意见回复的语言修订。
- 需要保留数值、单位、统计量、引用编号、作者-年份引用、限定词强度。
- 需要确定性复跑与可审计的修订记录。

## 不适用

- 从零写作、扩写、压缩、改变论证结构或结论。
- 翻译（中译英/英译中）与语域整体重写；本 Skill 只做表层最小编辑。
- 事实核查、文献补全、引用格式重排（GB/T 7714、APA、Vancouver 等）。
- 图表排版、LaTeX 编译、Word 修订痕迹、批注写入。
- 抄袭检测、AI 生成检测、期刊投稿系统操作。

## 输入形态

```text
/input/
  case.json          # 必需：case_id、正文、可选 terminology / target_style、output_contract
  manuscript.md      # 可选：正文文件（case.json 无正文时读取）
```

正文来源优先级：

1. `text` / `manuscript` / `draft` / `document` / `content` / `body` / `article` / `paragraphs` / `section_text` / `input_text` / `source_text` / `paper` / `manuscript_text` / `abstract` / `chapter`。
2. `manuscript_path` / `document_path` / `input_file` / `source_file` / `file` / `files` / `path` / `manuscript_file` / `draft_path`。
3. `case.json` 同目录下第一个可读的 `.md` / `.txt` / `.tex` / `.rst` / `.html` / `.pdf` 等正文文件（排除 `case.json`、`task.md`）。

术语表支持：

```json
{"terminology": {"FEV1": ["FEV-1", "fev-1"], "IL-6": ["IL6"]}}
```

或数组形式：

```json
{"terminology": [
  {"canonical": "FEV1", "variants": ["FEV-1"]},
  {"term": "IL-6", "avoid": ["IL6"]},
  {"preferred": "randomized", "synonyms": ["randomised"]}
]}
```

也支持 `"FEV1/FEV-1|fev-1"` 字符串条目。

## 调用方式

```bash
python3 /skills/weekly-skill/scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

等价薄封装：

```bash
python3 /skills/weekly-skill/scripts/run_skill.py --input /input --work /app/work --out /app/output
```

- `--input`：目录或 `case.json`，默认 `/input`；兼容 `--case`。
- `--work`：工作目录，写 `polish_report.json`，默认 `/app/work`。
- `--out`：目录（写 `result.json`）或 `.json` 文件，默认 `/app/output`；兼容 `--output`。
- 仅标准库；不联网；确定性；退出码恒为 0。
- `--out` 指向已存在目录时写该目录下 `result.json`，不会把目录当文件替换（避免 Windows `WinError 5`）。

## 输出契约

`result.json` 顶层固定包含：

| 字段 | 含义 |
|-|-|
| `case_id` | 与输入一致 |
| `status` | `success` / `partial` / `insufficient_input` / `failed` |
| `polished_text` | 润色后的完整正文，段落与换行结构保持不变 |
| `changes` | 已接受的编辑：句子 ID、类型、规则、原文、改写、原因、字符区间 |
| `rejected_changes` | 被护栏回退的编辑：原因（数值/单位、引用、限定词）与字符区间 |
| `terminology` | 术语表：首选写法、变体、来源指针 |
| `terminology_drift` | 润色后仍残留的非首选写法及次数 |
| `abbreviations` | 缩写：定义、首次定义位置、使用次数、是否先用后定义 |
| `evidence` | 逐句记录：句子 ID、字符区间、原文、改写、三类护栏布尔值、受保护信号 |
| `uncertainty` | 文体未声明、回退编辑、术语残留、术语冲突、长文限制 |
| `needs_human_confirmation` | 术语冲突、残留、缩写异常、被回退编辑 |
| `result` | 聚合对象：`polished_text`、`style_profile`、术语、漂移、缩写、限制 |
| `stats` | 句子数、编辑数、回退数、保护计数、字符数 |
| `version_record` | 输入/输出 sha256、字符数、规则版本、`source_mutation=none` |
| `errors` / `skipped` | 真实错误与跳过文件 |
| `contract_notes` | 每个契约键的映射或"无法判断"说明 |
| `contract_extras` | 契约键、映射方式、未知键、被接受的额外键 |

**契约覆盖规则**：`output_contract` 的每个键都出现在顶层。别名（`revised_text`→`polished_text`、`edits`→`changes`、`glossary`→`terminology`、`fact_map`→`evidence` 等）填真实值；已知生产者但无值、或完全未知的键写结构化 `cannot_determine` 对象，并记录在 `contract_extras.unknown_fields`；不留 `null` 或空占位冒充结果。

除 `result.json` 外还写：

- `/app/output/polished.md`：可直接交付的润色正文。
- `/app/output/revision-log.md`：接受/回退编辑的表格，便于逐条复核。
- `/app/work/polish_report.json`：完整运行报告。

## 处理流程

1. **读取 case.json**；缺失或损坏 → `failed`，仍写完整契约结果。
2. **定位正文**：按字段 → 路径 → 目录扫描的顺序；PDF 只抽取文本层。
3. **分块**：按空行分段落，段内按行处理；保留原有空行和换行。每句记录在原文中的字符偏移。
4. **规则编辑**：按固定顺序执行 30+ 条最小编辑规则；每条编辑都做护栏比较，通过才接受。
5. **术语统一**：按术语表替换变体；同样逐条过护栏。
6. **审计**：逐句写 `evidence`；汇总 `changes`、`rejected_changes`；检测缩写定义与残留变体。
7. **状态判定**：有回退、术语残留或术语表冲突 → `partial`；否则 `success`；无正文 → `insufficient_input`。
8. **写出**：`result.json`、`polished.md`、`revision-log.md`、`polish_report.json`。

**护栏定义**：

- 数值与单位：`NUMBER_RE` 抽取数值+单位（含 `%`、`mg`、`mL`、`mM`、`°C`、`min` 等），比较多重集。
- 引用：数字引用 `[12]`、`[3-5]`，作者-年份 `[Smith 2020]`、`(Smith, 2020)`。
- 限定/否定：`may/might/could/should/can/approximately/not/no/suggest/indicate/correlate` 及中文「可能/提示/相关/初步/不/未」等。

## 证据要求

- 每条编辑必须有 `sentence_id`（`<来源>#s<N>`）与 `char_start/char_end`，能定位回原文。
- `evidence` 中每句都要有 `numbers_preserved`、`citations_preserved`、`hedging_preserved` 三个布尔值；任一为 `false` 的编辑不得出现在 `changes` 中。
- 被回退的编辑必须出现在 `rejected_changes`，并写明触发了哪类护栏；不能静默丢弃。
- `version_record` 提供输入/输出 sha256，便于确认产物确实来自该输入。
- 不声称平台评分、期刊录用或人工审稿结论；`examples/demo-case` 是合成示例。

## 异常处理

| 情况 | 处置 | status |
|-|-|-|
| `case.json` 缺失/损坏 | 记录错误，写空结果 | `failed` |
| 正文为空或不足 20 字符 | 不产出改写 | `insufficient_input` |
| 正文只在不可读文件/无文本层 PDF | 记 `skipped`，不伪造文本 | `insufficient_input` |
| 无术语表 | 只做表层编辑，`terminology=[]` | 原状态 |
| 术语变体映射到多个首选写法 | 不擅自选择，记 `term_conflicts` | `partial` |
| 替换会改变数值/单位/引用/限定词 | 回退，记 `rejected_changes` | `partial` |
| 术语替换后仍有残留（复合词、大小写） | 记 `terminology_drift` | `partial` |
| 缩写先用后定义 / 重复使用但无定义 | 记 `abbreviations` 与人工确认项 | 不降级 |
| 未声明 `target_style` | 只做表层编辑，`uncertainty` 说明未做语域改写 | 不降级 |
| 输出目录不存在 / `--out` 是目录 | 自动创建并写 `result.json` | 原状态 |
| 未捕获异常 | 兜底写 `failed` 结果，退出码 0 | `failed` |

## 限制

- 只做表层最小编辑与术语替换，**不会**改善论证逻辑、段落衔接或语域。
- 规则是确定性的有限集合，不可能覆盖所有学术写作问题；`success` 只表示"未触发已知护栏"，不表示文本已完美。
- 数值/引用/限定词护栏基于多重集比较，等价改写（如 `10 mg` → `10 milligrams`）会被保守回退。
- 缩写检测基于正则，可能把统计缩写、基因名或单位误判为缩写；结果需人工确认。
- 不做引用格式规范化、不做参考文献与正文的对应核查。
- 不解析 `.docx`、`.doc`、`.odt`；请先转为 `.md` / `.txt`。
- 不写 Word 修订痕迹、批注或 PDF 标注。

## 最小示例

```bash
python3 scripts/sk_entry.py --input examples/demo-case --work /tmp/demo-work --out /tmp/demo-out
```

示例输入见 `examples/demo-case/case.json`，运行说明与预期摘要见 `examples/quickstart.md`。

## 交付自检

- [ ] `python3 scripts/sk_entry.py --input <案例目录> --work <工作目录> --out <输出目录>` 退出码 0。
- [ ] `result.json` 的 `case_id` 与输入一致，`status` 属于四个枚举值。
- [ ] `output_contract` 每个键都在顶层，且不是 `null` / `pending` / 空占位。
- [ ] `polished_text` 与输入段落数一致；没有丢段、并段、改标题层级。
- [ ] 每条 `changes` 都能在 `evidence` 中找到对应句子，且三项护栏布尔值全为 `true`。
- [ ] `rejected_changes` 中每条都有明确护栏原因。
- [ ] 所有数值、单位、引用标记、限定/否定词在润色前后一致。
- [ ] 术语表首选写法已统一；残留变体与冲突已记录。
- [ ] `polished.md` 与 `result.json.polished_text` 一致。
- [ ] 相同命令重复执行，`result.json` 内容一致。
- [ ] 提交目录无 `__pycache__`、无令牌、无本机绝对路径。

## 执行 Agent 的强制步骤

1. 运行入口命令，确认退出码 0。
2. 读取 `result.json`，检查 `status`、`changes`、`rejected_changes`、`terminology_drift`、`contract_extras`。
3. 逐条复核 `changes`：打开原文对应 `char_start`，确认改写只动了允许的表层表达。
4. 检查 `rejected_changes`，判断是否有应当改写但被护栏误拦的情况；如有，人工处理后写入说明，不能直接改 `result.json` 冒充通过。
5. 通读 `polished.md`，确认段落结构、术语与论证强度未变；把复核结论写入 `/app/output/revision-log.md`。
6. 不要修改输入文件；不要声称平台评分或期刊录用结果。
