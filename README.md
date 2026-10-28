# 刘杰科研 Skills

面向 Codex 的中文科研工作流技能集：论文检索与精读、论文全文翻译、实验研究与论文写作、英文段落精修。

## 技能一览

| 展示名 | 调用名称 | 主要用途 |
|---|---|---|
| 刘杰-论文检索与精读笔记.skill | `$liujie-paper-reading` | 检索、下载、原图解读与六章中文 Word 精读笔记 |
| 刘杰-论文翻译.skill | `$liujie-paper-translation` | 全文忠实翻译成可编辑中文 Word，核对覆盖、数字与排版 |
| 刘杰-论文写作.skill | `$liujie-paper-writing` | 从文献、实验设计和执行，到 baseline 对比、LaTeX 成稿与审计 |
| 刘杰-段落润色.skill | `$liujie-paragraph-polishing` | 主体先行、问题递进、证据匹配与减少防御性写作 |

## 安装

1. 下载仓库 ZIP，或执行：

   ```sh
   git clone https://github.com/symyyds/liujie-skills.git
   ```

2. 将仓库的整个 `刘杰` 文件夹复制到 Codex 的个人技能目录。常用安装结构：

   ```text
   ~/.codex/skills/刘杰/
   ├── liujie-paper-reading/SKILL.md
   ├── liujie-paper-translation/SKILL.md
   ├── liujie-paper-writing/SKILL.md
   └── liujie-paragraph-polishing/SKILL.md
   ```

   使用 `CODEX_HOME` 时放入其 `skills/` 目录；已配置 `~/.agents/skills/` 的环境也可以使用该目录。选择一个个人技能目录安装，避免重复加载。更新前保留自己的定制版本。

3. Codex 通常会自动发现技能变化；未出现时重新打开应用或新建对话。

单项分发包位于 [`packages/刘杰/`](packages/刘杰/)。`.skill` 是包含完整技能目录的 ZIP 格式压缩包；也可以用解压工具解开后安装其中的文件夹。

## 使用示例

### 找论文与精读

```text
使用 $liujie-paper-reading，检索【研究主题】近一年的相关论文，核验出版信息和等级，下载可获取的全文，按模板整理中文精读笔记。
```

完整笔记包含：摘要、贡献、关键技术（实现方法）、实验设计、实验结果对比、总结。摘要完整翻译；方法、图表和实验解释保留来源。研究主题、年份和期刊等级以当前任务为准。

### 论文全文翻译

```text
使用 $liujie-paper-translation，把附上的论文完整翻译为中文 Word。保留段落逻辑、图表公式、数值和限定条件，核对全文覆盖并逐页检查排版。
```

### 实验研究与论文写作

```text
使用 $liujie-paper-writing，根据我的研究方案、数据、设备和目标期刊规划并完成研究与论文。先说明当前阶段的范围和产物，按阶段确认推进。
```

流程包含研究范围、文献图库、实验设计、数据审计、实验执行、baseline 数值比较、图表写作和最终审计。保留真实实验、来源、失败记录和适用范围。

### 英文段落精修

```text
使用 $liujie-paragraph-polishing，精修以下英文段落。保留事实、数值、引用和必要限制，直接说明观点与证据，删去没有信息的自我辩护，输出修改后的正文。
```

## 运行环境

- 技能指令本身可直接安装；执行辅助脚本需要 Python 3.10+。
- 文档脚本的基础依赖列在 [`requirements.txt`](requirements.txt)。优先使用当前环境提供的 Python 和依赖；需要手动安装时可在独立虚拟环境中执行 `python -m pip install -r requirements.txt`。
- Word/PDF 渲染需要当前环境提供的 Documents/PDF 工具，或脚本支持的渲染器。安装依赖本身不代表已经完成视觉核查。
- 文献检索需要可用的网络或检索工具；图表、文献表与文档任务可配合环境中的 PDF、Spreadsheets、Documents 技能。
- 原生公式转换使用的可选依赖按翻译技能中的说明配置。

## 公开版本说明

公开副本移除了私人聊天标识、真实本机路径、私人稿名和原笔记内容。精读模板保留可复用版式，使用通用文字与中性图片占位。技能不依赖作者的历史聊天或私人项目目录。

辅助脚本负责结构、来源记录和排版检查；科研判断、翻译语义及最终页面仍须对照原文与实际结果核验。当前请求决定执行范围，用户的新模板和写作要求优先。

## 仓库结构

```text
刘杰/                  四个技能的可编辑源文件与资源
packages/刘杰/         可单独分发的 .skill 压缩包
requirements.txt       Python 辅助脚本基础依赖
LICENSE                MIT License
```

后续新增技能继续使用 `刘杰-xxx.skill` 展示名，在 `刘杰/` 下增加对应的小写连字符目录。

## 许可证

本仓库采用 [MIT License](LICENSE)。使用者自行提供的论文、数据和图片遵循其各自的许可与访问条件。
