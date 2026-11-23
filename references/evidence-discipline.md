# 证据纪律：最小编辑、护栏回退、不编造

## 1. 三条硬规则

1. **不改变事实**：数值、单位、统计量、引用标记、限定/否定强度必须与原文一致。
2. **不掩盖失败**：被护栏拦下的编辑写入 `rejected_changes`，不能静默删除。
3. **不越权**：不新增文献、不改结论、不做事实核查、不声称期刊录用或平台评分。

## 2. 一条编辑的完整证据

```json
{
  "sentence_id": "text#s5",
  "type": "术语",
  "rule": "terminology",
  "original": "Before analysis, FEV-1 was measured in all subjects.",
  "revised": "Before analysis, FEV1 was measured in all subjects.",
  "reason": "统一为术语表首选写法「FEV1」（来源 /terminology/FEV1）。",
  "accepted": true,
  "char_start": 120,
  "char_end": 171
}
```

复核步骤：

1. 用 `sentence_id` 在 `evidence` 中找对应句子，确认 `original` 一致。
2. 按 `char_start/char_end` 打开原文，确认区间就是该句。
3. 检查 `numbers_preserved`、`citations_preserved`、`hedging_preserved` 全为 `true`。
4. 人工判断改写是否只动了表层表达；若改动了含义，必须回退并在交付说明中记录。

## 3. 护栏失败的正确处理

| 触发 | 例子 | 处置 |
|-|-|-|
| 数值/单位变化 | `10 mg` → `ten milligrams`；`p = 0.02` → `p = 0.03` | 回退，`rejected_changes[].reason=numbers_or_units` |
| 引用变化 | `[12]` → `[13]`；`(Smith, 2020)` → `(Smith, 2021)` | 回退 |
| 限定词变化 | `may reduce` → `reduces`；`no effect` → `effect` | 回退 |
| 术语替换引入数字 | `IL-6` → `IL6` 时误伤 `IL-6R` | 由边界匹配预防；仍触发则回退 |

回退不是失败，而是**保护事实**。`status=partial` 是如实降级。

## 4. 术语残留

- `terminology_drift` 记录润色后仍出现的非首选写法、次数与术语来源。
- 常见原因：复合词（`FEV-1a`）、大小写变体、术语表未覆盖的屈折形式。
- 不为了清零残留而做无边界的全局替换；残留交人工确认。

## 5. 缩写

- 定义前使用、重复使用但无定义，写入 `abbreviations` 与 `needs_human_confirmation`。
- 不自动补定义，不自动展开缩写；这些都可能改变事实。

## 6. 文体与范围

- `target_style` 未声明时，只做表层最小编辑，不尝试期刊/学位论文/基金申请的语域重写。
- `success` 只表示"未触发已知护栏"，不表示文本已可投稿。
- 长文（>20000 字符）仍需人工通读，`uncertainty` 会提示。

## 7. 禁止事项

- 不写平台分数、评审结论、期刊录用结果。
- 不把 `examples/demo-case` 的输出冒充正式案例结果。
- 不写令牌、密钥、个人路径或账号信息。
- 不修改输入文件，不删除无法处理的文件；只记录 `skipped`。
