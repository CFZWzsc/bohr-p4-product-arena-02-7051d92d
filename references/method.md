# 方法说明：规则、护栏、术语与定位

## 1. 正文读取

优先级：

1. `case.json` 中的正文字段（`text`、`manuscript`、`draft`、`document`、`content`、`body`、`article`、`paragraphs`、`section_text`、`input_text`、`source_text`、`paper`、`manuscript_text`、`abstract`、`chapter`）。
2. 路径字段（`manuscript_path`、`document_path`、`input_file`、`source_file`、`file`、`files`、`path`、`manuscript_file`、`draft_path`），相对 `case.json` 所在目录解析。
3. 同目录扫描（最多 10 个文件），排除 `case.json`、`task.md`、缓存目录。

支持 `.txt/.md/.markdown/.tex/.rst/.html/.htm/.csv/.tsv/.log/.yaml/.yml` 与带文本层 `.pdf`。编码顺序 UTF-16 BOM → UTF-8 → GB18030 → Big5 → Latin-1。

## 2. 结构保持

- 按空行切段落，段落内按行处理，行内按句切分。
- 输出时段落之间保留一个空行，段内行之间保留换行；不合并段落、不删除标题行。
- 句子切分：中文句号/问号/感叹号/分号后切；英文 `.!?;` 后跟空白切。`e.g.` 等缩写可能被切开，但对编辑与护栏无影响。

## 3. 编辑规则

规则按固定顺序执行，每条规则只做一次全局替换（`re.IGNORECASE`），因此同一句可能被多条规则依次修改，每条都单独记录。

| 类别 | 规则 |
|-|-|
| 冗余连接 | `in order to`→`to`；`due to the fact that`/`based on the fact that`/`in light of the fact that`→`because`；`in spite of the fact that`→`although`；`in the event that`→`if`；`for the purpose of`→`to`；`whether or not`→`whether` |
| 冗余量词 | `a total of`→删除；`a number of`→`several`；`each and every`→`every`；`end result`→`result`；`past history`→`history`；`completely eliminate`→`eliminate`；`very unique`→`unique`；`more preferable`→`preferable`；`in close proximity to`→`near`；`on a daily basis`→`daily` |
| 能力表达 | `has/have the ability to`、`is/are able to`→`can` |
| 用词 | `prior to`→`before`；`subsequent to`→`after`；`utilize`→`use`；`commence`→`begin`；`terminate`→`end`；`ascertain`→`determine` |
| 语法/排版 | 重复词、重复标点、空格、标点前空格、全角空格、`的的` |

动词替换保留时态/单复数：`utilized`→`used`、`utilizing`→`using`、`commenced`→`began`、`terminated`→`ended`。

## 4. 三重护栏

对每次候选编辑，比较编辑前后的三个多重集：

1. `NUMBER_RE`：数值 + 可选单位。数值前不能紧跟字母、数字、点或连字符，避免把 `FEV-1`、`IL-6` 中的数字当成独立测量值。
2. `CITATION_RE`：`[12]`、`[3-5]`、`[Smith 2020]`、`(Smith, 2020)`。
3. `HEDGE_WORDS` / `HEDGE_PREFIXES` / `HEDGE_ZH`：情态动词、频率/程度限定、否定词、`suggest/indicate/correlate` 词族、中文限定词。

任一多重集变化 → 回退该条编辑，写入 `rejected_changes`，`status` 降为 `partial`。

## 5. 术语表

接受三种形态：

- 对象：`{"FEV1": ["FEV-1"], "IL-6": ["IL6"]}`
- 数组对象：`canonical/preferred/term` + `variants/avoid/forms/synonyms`
- 字符串：`"FEV1/FEV-1|fev-1"`

替换规则：

- 变体边界：前后不能是字母、数字、连字符（`(?<![\w-])... (?![\w-])`），避免 `FEV-1a` 被部分替换。
- 大小写不敏感匹配，替换为首选写法原文。
- 每次替换同样过三重护栏。
- 润色后扫描残留变体，写入 `terminology_drift`；同一变体映射到多个首选写法，写入 `term_conflicts`，不擅自选择。

## 6. 缩写检测

- 定义：`Full Name (ABBR)`，最多 6 个词的定义 + 1–12 位大写缩写。
- 记录定义位置、使用次数、定义前使用次数。
- 定义前已使用 → `used_before_definition`；重复使用但无定义 → `undefined_repeated_abbreviation`。
- 仅提示，不自动改写，避免误改基因名/统计缩写。

## 7. 定位与证据

- 每句有 `sentence_id = <来源>#s<N>`，`N` 是全文句序。
- `char_start/char_end` 是该句在来源文本中的字符区间，按顺序用 `find` 回填。
- `evidence[]` 逐句记录原文、改写、是否编辑、三项护栏布尔值、受保护信号。
- `changes[]` 与 `rejected_changes[]` 都带句子 ID 与字符区间，可与 `evidence` 交叉核对。

## 8. 状态判定

| status | 条件 |
|-|-|
| `success` | 产出正文；无回退编辑、无术语残留、无术语冲突 |
| `partial` | 有回退编辑，或术语残留，或术语表内部冲突 |
| `insufficient_input` | 没有 ≥20 字符的正文 |
| `failed` | `case.json` 缺失或损坏 |

## 9. 确定性

- 不使用 `random`、`time`、`datetime`、网络。
- 规则顺序固定，术语按输入顺序，文件按路径排序。
- 输出不含时间戳与机器绝对路径。
- 同一输入重复运行，`result.json` 与 `polished.md` 内容一致。
