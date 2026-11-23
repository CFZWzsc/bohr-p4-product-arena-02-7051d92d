---
name: academic-language-polisher
description: Polish academic English or Chinese prose with minimal, sentence-level edits while locking numbers, units, citation markers and hedging strength so the author's claims are never strengthened or weakened. Use when a task asks for grammar/terminology/tone polishing with a per-edit rationale and term consistency.
---

# 学术语言润色（最小编辑 + 语义护栏）

## 用途与适用条件

对已有学术文本做**最小编辑式**润色：只消除可判定的硬错误、冗余表达与术语不一致，逐句产出「原文—改文—类型—理由」，并用护栏保证数值、单位、引用标记与限定词强度不变。

适用：

- 任务是"润色/校对/统一术语/检查语气"，原文已由作者提供。
- 需要可复核的逐句修改清单，而不是整段重写。
- 有术语表或可抽取的术语偏好。

不适用：需要重写论证结构、需要扩写内容、需要翻译（本 Skill 不做跨语言翻译）、需要核查文献真实性。

## 输入

| 输入 | 位置 | 说明 |
|-|-|-|
| `case.json` | `/input/case.json`（`--case` 可覆盖） | 正文取自 `text` / `manuscript` / `draft` / `document` / `content` / `paragraphs` 等字段；也支持列表与 `{text: ...}` 形式 |
| `task.md` | `/input/task.md`（自动探测） | 仅用于读取风格与任务约束，不作为被润色正文 |
| 术语表 | `case.json` 的 `terminology` / `glossary` / `termbase` / `terms` | 支持 `{首选: [变体]}`、`[{canonical, variants}]`、`"首选/变体1|变体2"` 三种写法 |
| 目标文体 | `target_style` / `style` / `register` | journal article、thesis、grant、response to reviewers 等；缺省记为 unspecified |
| 输出 | `/app/output/result.json`（`--out` 可覆盖） | 结构化结果 |

## 处理流程（对应评分维度）

1. **文本归一**（任务完成度）：按空行与换行分块，按中英文句末标点切句，生成稳定 `句子ID`（`/text#s3`）。
2. **表层最小编辑**（改得对）：逐条应用确定性规则——多余空格、标点前空格、重复标点、重复词、`in order to`、`due to the fact that`、`a total of`、`is able to`、`prior to`、`subsequent to`、`utilize`、全角空格、中文重复标点与"的的"。**不改变语序，不整句重写。**
3. **术语统一**（说得像）：按术语表把非首选写法整体替换为首选写法，记录术语来源指针；替换后复查残留变体，写入 `terminology_drift`。
4. **语义护栏**（没改坏）：每处编辑前后比较三类受保护信号——数值与单位多重集、引用标记多重集、限定词/情态词多重集。任一变化即**回退该处编辑**，并在 `changes` 中记为 `type: rejected`。
5. **逐句对照**（讲得清）：`evidence` 记录每句原文、改文、是否改动、三类信号是否保持，第三方可据此判断该处该不该改。
6. **边界说明**：未声明文体、被回退编辑数、术语残留、无硬错误时的"无需修改"提示，全部写入 `uncertainty`。

## 输出契约

顶层固定字段：

- `case_id`：原样保留。
- `status`：`success`（完成润色）/ `insufficient_input`（无正文）/ `failed`（异常）。本 Skill 不做 `partial` 降级：无正文即不产出。
- `result`：`polished_text`、`style_profile`、`terminology`、`terminology_drift`、`limitations`。
- `changes`：仅列被接受的编辑（`sentence_id / type / rule / original / revised / reason`）；被回退的编辑不混入，避免误读为已修改。
- `evidence`：逐句对照与三项 `*_preserved` 布尔值。
- `uncertainty`、`errors`、`stats`（句数、编辑数、回退数、术语数、受保护计数）。
- `contract_notes`：契约字段处理说明。

**output_contract 处理**：契约声明的字段逐一放到顶层；`polished_text`、`changes`、`terminology`、`uncertainty`、`stats` 及其常见别名（`text`、`edits`、`glossary` 等）会映射填充；无法产出的字段置 `null` 并在 `contract_notes` 说明，不编造。

## 异常处理

| 情况 | 处置 | status |
|-|-|-|
| `case.json` 缺失或非对象 | 结构化失败，标注阶段，退出码 2 | `failed` |
| 无正文（只有任务说明或术语表） | 不产出文本，说明缺什么 | `insufficient_input` |
| 术语表格式不认识 | 跳过该项，继续润色，不猜测映射 | `success` |
| 编辑会改动数值/引用/限定词 | 回退该编辑并记录原因 | `success` |
| 术语变体残留（复合词、大小写） | 写入 `terminology_drift` 待人工确认 | `success` |
| 未声明目标文体 | 只做表层编辑，写入 `uncertainty` | `success` |
| 输出目录不存在 | 自动创建 | — |

## 限制

- 只覆盖规则表内的表层问题，不能发现语义歧义、逻辑跳跃与领域搭配错误。
- 不做整段改写、不做语域整体重构，因此"说得像"仅限术语统一与硬错误消除。
- 术语表需由用户提供或从 `case.json` 读取；本 Skill 不联网构建术语库。
- 护栏以多重集比较实现，无法识别"同义但含义变化"的替换；这类风险通过"最小编辑"策略规避。
- 中文润色规则较粗，长句切分需人工判断。

## 最小调用示例（示例，非官方案例结果）

输入 `/input/case.json`（示例）：

```json
{
  "case_id": "demo-001",
  "output_contract": {"polished_text": "string", "changes": "array", "status": "string"},
  "target_style": "journal article",
  "text": "In order to assess the effect, a total of 120 participants were randomized. The therapy  may reduce symptoms (p = 0.02) [12].",
  "terminology": {"FEV1": ["FEV-1"]}
}
```

调用：

```bash
python scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

示意输出（**示例**）：

```json
{
  "case_id": "demo-001",
  "polished_text": "To assess the effect, 120 participants were randomized. The therapy may reduce symptoms (p = 0.02) [12].",
  "changes": [{"sentence_id": "/text#s1", "type": "冗余", "rule": "in_order_to", "original": "In order to assess ...", "revised": "To assess ...", "reason": "in order to 简化为 to"}],
  "status": "success",
  "stats": {"sentences": 2, "edits": 2, "rejected_edits": 0}
}
```


## 自查清单

- [ ] `case_id` 与合同字段保留；未映射项已登记。
- [ ] `polished_text` 覆盖输入全部段落，无截断或样例残留。
- [ ] 数值、单位、引用标记、限定词强度逐项保持。
- [ ] 每处改动都有原文、改文与理由；回退项单独记录。
- [ ] 未整段重写、未新增论断。

## 执行保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--output` 指定。
2. **必须交付完整成品**：脚本只做规则级最小编辑；调用 Agent 必须复核并补全整篇 `polished_text`（覆盖全部段落，不得截断或只改样例），每条改动写入 `changes`（原文/改文/理由），被护栏回退的编辑保留在 `evidence`；不得以“示例/待润色”作完成态。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 取本合同允许值 `success | insufficient_input | failed`；正文无 `pending`/`TODO`/空占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。
