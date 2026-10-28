# 脚本使用的数据约定

这些是内部工作文件，服务摘要完整性、来源追踪和稳定排版，不要求用户填写。论文事实与解释由全文阅读产生，脚本不填内容。

## notes/ID.json

必需字段：`id`、`title`、`pdf_path`、`sections`。建议元数据：`year`、`venue`、`rank`、`rank_note`、`authors`、`status`（正式/预印本状态和所读版本）、`url`、`category`。`pdf_path` 和图片 `path` 可用绝对路径，或相对当前 JSON 文件所在目录的路径。

`sections` 按以下顺序且各出现一次：摘要、贡献、关键技术（实现方法）、实验设计、实验结果对比、总结。每节为 `{"heading": "章名", "blocks": [...]}`，每节含实质正文或图解，支持：

- 文字：`{"type": "p", "text": "内容", "source": "PDF 第 3 页 §2.1"}`。
- 子标题：`{"type": "subheading", "text": "输入与验证"}`。
- 图片：`{"type": "image", "path": "../figures/P01/framework.png", "caption": "原文 Figure 1 方法流程", "interpretation": "具体读图说明", "source": "PDF 第 4 页 Figure 1"}`。

正文/图必须有 `source`。阅读判断或建议可写“阅读判断，依据 PDF 第 X 页…”以区分身份；摘要来源标明 Abstract。图片须 PNG/JPEG，必要时可设置 `max_width_cm`、`max_height_cm`；文字 `align` 或图解释 `interpretation_align` 可为 `left` 以修正长标识符导致的字距。摘要只使用 `p`，多个原段落对应多个块。

## abstract_alignment/ID.json

```json
{
  "id": "P01",
  "source_pdf": "../sources/P01_paper.pdf",
  "source_pages": [1],
  "english_abstract": "完整英文摘要，已清理排版换行与断词。",
  "sentences": [
    {"en": "第一句完整原文。", "zh": "第一句完整译文。"},
    {"en": "第二句完整原文。", "zh": "第二句完整译文。"}
  ]
}
```

句子按原顺序连续排列，按真实句意分句；小数、缩写和 URL 不机械按句点拆分。`english_abstract` 必须包含完整原摘要。连接全部 `en` 后应与之相同（仅忽略空白），连接 `zh` 应与 notes 摘要相同。内部对齐文件不包含 Word 中的来源行。

## 校验与构建

用依赖工具返回的 Python 执行（下列路径替换为本机实际绝对路径）：

```text
python scripts/audit_notes.py --notes-dir BATCH/notes --alignment-dir BATCH/abstract_alignment --output BATCH/work/note-audit.json
python scripts/build_notes.py --notes-dir BATCH/notes --output BATCH/论文精读笔记.docx
```

校验检测：六章、字段、摘要拼接一致性、每句非空、PDF 可解析和页码范围、笔记与摘要使用同一 PDF、图片能打开、正文与图的来源齐全。非零退出表示结构错误待修正。它不验证译文语义、原摘要是否抄全、图片是否裁全、数值解释或科研建议是否正确；这些必须人工式回看原文和渲染页面。

可由已有索引另存稳定 ID 列表，通过校验脚本 `--expected-ids`（空白分隔的 ID 文件或 JSON 字符串数组）验证全批覆盖。没有清单参数时只检查现有 notes，不能由此宣称没有漏篇。已有笔记使用别的数据结构时可继续沿用，但保留同等的摘要对齐、来源与覆盖检查。
