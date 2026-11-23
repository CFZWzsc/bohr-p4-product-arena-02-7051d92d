# 题面要求逐条落地

本文件把 `product-arena-02-7051d92d` 的题面要求映射到本 Skill 的具体字段与行为，便于评审逐项核对。正式依据是题面原文与平台案例输入；本文件不是平台评分结果。

## 1. 核心任务

| 题面要求 | 本 Skill 的落地 |
|-|-|
| 对学术文本做语言润色 | `RULES` 中 30+ 条确定性最小编辑；`changes[]` 逐条记录 |
| 提高表达清晰度与规范性 | 冗余连接词、模糊量词、重复词、标点/空格、常用学术动词替换 |
| 保持原意与学术严谨性 | 数值/单位、引用、限定词三重护栏；不通过则回退 |
| 统一术语 | `terminology[]`、`terminology_drift[]`、`term_conflicts[]` |
| 保留事实、数据、引用 | `evidence[].numbers_preserved/citations_preserved` |
| 保留限定与否定强度 | `evidence[].hedging_preserved`，`protected_signals.hedging` |
| 产出可编辑正文 | `/app/output/polished.md` + `result.json.polished_text` |
| 可审计 | `changes`、`rejected_changes`、`evidence`、`version_record` |

## 2. 常见问题覆盖

| 问题 | 规则示例 | 记录字段 |
|-|-|-|
| 冗长表达 | `in order to` → `to`；`due to the fact that` → `because`；`a total of` → 删除 | `changes[].rule` |
| 口语/非正式用词 | `utilize` → `use`；`prior to` → `before`；`a number of` → `several` | `changes[].type=用词` |
| 重复与赘余 | `each and every` → `every`；`end result` → `result`；重复词/重复标点 | `changes[].type=冗余/语法` |
| 术语不一致 | `FEV-1` → `FEV1`；`IL6` → `IL-6` | `terminology`、`terminology_drift` |
| 缩写不规范 | 先用后定义、重复使用但无定义 | `abbreviations[].status` |
| 标点/空格 | 多余空格、标点前空格、全角空格、中文重复标点 | `changes[].type=排版/标点` |

## 3. 护栏要求

| 信号 | 抽取方式 | 失败处置 |
|-|-|-|
| 数值与单位 | 数值 + `% / mg / mL / mM / °C / min / h / day` 等 | 拒绝编辑，写入 `rejected_changes` |
| 引用 | `[12]`、`[3-5]`、`[Smith 2020]`、`(Smith, 2020)` | 拒绝编辑 |
| 限定/否定 | `may/might/could/should/can/approximately/not/no/suggest/indicate/correlate` + 中文限定词 | 拒绝编辑 |
| 术语表 | 变体边界匹配（前后不能是字母、数字、连字符） | 拒绝会改变数值/引用/限定的替换 |

## 4. 题面要求的交付材料

| 材料 | 本包中的位置 |
|-|-|
| `SKILL.md`（用途、适用条件、调用、输入输出、异常） | 根目录 `SKILL.md` |
| 运行脚本与资源 | `scripts/sk_entry.py`、`scripts/run_skill.py`、`assets/policy.json` |
| 方法、证据与限制说明 | `references/method.md`、`references/evidence-discipline.md` |
| 最小示例 | `examples/demo-case/`、`examples/quickstart.md` |
| 可编辑正文 | 运行时生成 `polished.md` |
| 修订记录 | 运行时生成 `revision-log.md` |

## 5. 平台约束

- `result.json` 必须含全部原始 `output_contract` 键与 `case_id`：由 `contract_notes` 与 `contract_extras.mapping` 逐键证明。
- 不提交预制润色稿：`examples/demo-case` 是合成示例。
- 不编造编辑效果或评审结论；`status=success` 仅表示未触发已知护栏。
- 仅标准库、无网络、确定性；不写入令牌、密钥、个人路径。
