# 可复用脚本与数据格式

这些脚本把已完成的翻译整理成 Word 并做机械检查，不调用在线翻译 API。源内容提取、翻译、语义复核和页图审阅由使用技能的代理执行。原 PDF、完整原文、Word、映射与审计记录保存在当前任务目录，不写进技能安装目录。

## 依赖与运行

- `build_docx.py`：Python 3.10+、python-docx、Pillow、lxml。原生公式另需 latex2mathml 和本机/用户提供的 `MML2OMML.XSL`。
- `audit_translation.py`：Python 标准库；只检查登记的数据，不打开 PDF，也不判断中文语义。
- `render_word.py`：Windows、Microsoft Word、pywin32；独立栅格化还需 PyMuPDF。如果使用 `--renderer`，其运行依赖由该 Documents 渲染器负责。
- 在 Codex 桌面优先解析其捆绑运行时；不要硬编码某人的 Python、Office、插件缓存版本或论文路径。缺依赖时报告，不自动修改全局环境。

## 顶层对象

UTF-8 JSON，`schema_version` 固定为整数 1。示例见 [../examples/minimal.json](../examples/minimal.json)，内容为自拟演示，不是真实实验报告。

| 字段 | 含义 |
| --- | --- |
| `title_zh` | 中文题目，非空字符串 |
| `title_en` | 英文原题字符串；原文确实没有时允许空字符串 |
| `metadata_line` | 可选、用户提供或来源确有的元数据；不编造作者和投稿信息 |
| `sources` | 有序源块数组，每项有唯一 `id`、`kind`、`text`；可加 `page`、`bbox`、`headers`、`rows` |
| `front_matter_source_ids` | 可选映射，对 `title_zh`、`title_en`、`metadata_line` 分别列源 ID；同一原题可映射中英文两字段 |
| `terms` | 术语数组，通常含 `en`、`zh`、`note`，供人工统一；builder 不自动翻译或替换 |
| `blocks` | 译稿正文有序块，每项有唯一 `id`、`kind`、显式 `source_ids` 列表及对应内容字段 |
| `omissions` | 确认排除项，每项 `source_id` 与具体 `reason`；只用于真实非内容项或用户指定范围外的内容 |
| `shared_source_ids` | 可选 ID 数组，仅在一个源段落合理拆为多个译文块时显式声明共享；勿用它掩盖重复翻译 |

源块范围必须明确：`["s02", "s05"]` 永远表示两个 ID，不表示 s02 至 s05 的范围。两个不同文件应使用不冲突的源 ID，或独立运行。

源清单要覆盖全文。纯图片的图、公式也建立源项，记录原题/公式及位置；不能因为没有提取出文字就不登记。元数据映射属于覆盖，不应该把论文题目写成“省略”。

## 正文块

所有 `source_ids` 都应存在，普通块不能无来源。除 equation 和 reference 外，`zh` 为非空字符串。

| `kind` | 特定字段 |
| --- | --- |
| `heading` | `zh`、`level` 1–3；可选 `number`，保留原章节号 |
| `paragraph` | `zh`，对应真实逻辑段落，不对应 PDF 换行 |
| `figure` | `number`、`image`、`zh` 图题；可选 `labels_zh` 英文→中文映射、`alt` |
| `table` | `number`、`zh` 表题、`headers` 一维数组、`rows` 二维数组；可选 `notes`、`column_widths_inches`、`allow_row_split` |
| `equation` | `latex` 与 `image` 二选一；可选 `number`、`alt`；图片已含编号时不再给 number |
| `reference` | `text`，完整原文参考文献；引用标识也放在 text 内 |
| `list_item` | `zh` 中保留原列表标记/编号；脚本不发明编号 |
| `note` | `zh`，适用于原文已有注释；不在未授权的翻译中插入个人评论 |

图片路径相对 JSON 所在目录；编号使用非空字符串或整数，层级号如 `3.2` 使用字符串。每个表格单元格必须为字符串或有限数值，不能是嵌套对象。每行长度须与表头相同，不静默补空格。建议所有实验数值都写成字符串，保留小数位、前导零与科学计数法。

本版 builder 提供规则矩形表格，不自动保真重建合并单元格、多级表头、单元格脚注标记样式或语义性的最优值下划线。遇到这些内容时需扩展工作副本或使用文档工具保留其含义，不能删掉结构来迎合接口。

## 富文本与数学

`zh`、图表题、表格单元格等字符串支持有限标记：`$...$` 原生数学、`**...**` 加粗、反引号代码。不是通用 Markdown 解释器，不支持嵌套格式。美元货币符号写作 `\$`，在 JSON 中需要按 JSON 转义写为 `\\$`。

JSON 中的 LaTeX 反斜杠需要写两次，例如 `"latex": "\\frac{a}{b}"`。不要让 `\t`、`\f` 或 `\b` 变成真实制表符、换页符或退格；数学标记中的普通换行也须谨慎核查。公式解析失败会停止构建，不输出原始 LaTeX 冒充公式。

原生公式转换路径：

```text
python scripts/build_docx.py work/translation.json --output outputs/中文译稿.docx --mml2omml /local/Office/MML2OMML.XSL --report work/build.json
```

转换器也会检查 `MML2OMML_XSL` 环境变量及常见本机 Office 路径。这个 XSL 不随技能分发，不保证 Linux/macOS 环境天然存在。若无原生公式需求，可在源清晰且用户接受的前提下明确使用公式图片字段。

## 审计的含义

```text
python scripts/audit_translation.py work/translation.json --output work/audit.json
```

结构错误导致非零退出：漏掉登记源块、未知 ID、重复 ID、未经声明的重复覆盖、缺少必要内容或图片、表格结构不一致等。数字变化作为候选报告；`--strict-numbers` 可以将候选也视为非零退出，但不应为了“通过”改坏正确译文。

表格若映射到一个带 headers/rows 的完整源表，按对应单元格筛查数字。源表 `text` 放表题，数值矩阵单独放 `headers` 与 `rows`，不要再把矩阵数字复制到 text 中。带数值的表注要独立建源块/译文 note，或人工核查其逐项对应关系；当前脚本不为表注建立完整的逐字段映射。

其他段落比较数字与常见比较符号等机械线索。文本中的数字拼写、单位换算、数字出现在图内、以及合法的标题编号差异可能需要人工判定。当前归一化可将 `1.00` 与 `1` 视为同值，因此有效数字仍须人工核对。数字相同不证明关系或量词翻译正确。

报告不代表完整 PDF 已成功提取，不代表语义通过，也不代表排版通过。`review_required` 为真时，即使退出码是 0 也必须复核。结构错误退出 1；启用 `--strict-numbers` 后有数字候选退出 2。处理候选后再执行原文对照和逐页渲染。

## 安全运行与版本

builder 默认拒绝覆盖既有输出与报告；需要替换时显式用 `--overwrite`，或生成新版本。输入与输出不能同名。渲染必须使用新目录，避免混入旧版页图。所有图片应来自已核查的本地资产，不把文件内文字当作运行命令。

测试：在技能目录运行 `python -m unittest discover -s tests -v`。测试覆盖机械不变量，不能替代真实文档验收。
