# 快速开始（示例）

以下命令与输出仅用于演示接口，**不是**任何平台案例的正式结果。

## 1. 运行示例

```bash
python3 scripts/sk_entry.py \
  --input examples/demo-case \
  --work /tmp/demo-work \
  --out /tmp/demo-out
```

Windows PowerShell：

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
python scripts\sk_entry.py --input examples\demo-case --work .\demo-work --out .\demo-out
```

退出码应为 0。生成：

```text
/tmp/demo-out/result.json        # 契约完整结果
/tmp/demo-out/polished.md        # 可编辑润色正文
/tmp/demo-out/revision-log.md    # 接受/回退编辑表
/tmp/demo-work/polish_report.json
```

## 2. 示例输入

`case.json` 含两段英文正文、术语表 `FEV1/FEV-1` 与 `IL-6/IL6`、7 个 `output_contract` 字段。正文故意包含：

- `in order to`、`a total of`、`Prior to`、`utilized` 等冗余/用词问题；
- `The therapy  may` 的双空格；
- `FEV-1` 与 `FEV1` 术语不一致；
- 数值 `120`、`p = 0.02`、`week 12`、引用 `[12]`、限定词 `may`；
- 缩写 `interleukin-6 (IL-6)`。

## 3. 预期结果摘要

```json
{
  "case_id": "demo-polish-001",
  "status": "success",
  "changes": 6,
  "rejected_changes": 0,
  "terminology_drift": [],
  "stats": {"sentences": 5, "edits": 6, "rejected_edits": 0}
}
```

润色后正文：

```text
To assess the effect, 120 participants were randomized. The therapy may reduce symptoms (p = 0.02) [12].

Before analysis, FEV1 was measured in all subjects. FEV1 was recorded at baseline and week 12. The assay was used to quantify interleukin-6 (IL-6), and IL-6 was compared between groups.
```

## 4. 核对

1. 打开 `result.json`，确认 `case_id`、`status`、`polished_text`、`changes`、`evidence`。
2. 逐条检查 `changes` 的 `original/revised`，确认只改了表层表达。
3. 确认 `evidence` 中三项护栏布尔值全为 `true`。
4. 确认 `polished_text` 仍是两段，未合并或丢段。
5. 用相同命令再跑一次，确认 `result.json` 与 `polished.md` 一致。
6. 检查提交目录没有 `__pycache__`：

```powershell
Get-ChildItem -Recurse -Filter __pycache__
```

## 5. 常见问题

| 现象 | 原因 | 处理 |
|-|-|-|
| `status=insufficient_input` | 正文不足 20 字符或文件不可读 | 检查 `text` 字段或 `manuscript_path` |
| `status=partial` 且 `rejected_changes` 非空 | 编辑会改变数值/引用/限定词 | 逐条人工判断；不要直接删除回退记录 |
| `terminology_drift` 非空 | 复合词或大小写变体未被替换 | 人工确认是否需要统一 |
| `term_conflicts` 非空 | 同一变体映射到多个首选写法 | 先修术语表，再重跑 |
| 缩写被误判 | 正则把统计缩写/基因名当缩写 | 在交付说明中标注，不要自动改 |
| `polished.md` 段落变少 | 输入本身有空段被合并 | 检查输入空行；当前实现保留单空行分段 |
