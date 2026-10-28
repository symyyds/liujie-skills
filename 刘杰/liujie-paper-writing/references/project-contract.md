# 项目状态、目录与证据契约

这些记录帮助恢复长流程及核验交付，不代替用户真实批准或科研判断。只在项目阶段获准后创建项目目录，不因加载技能就在桌面生成资料库。

## 目录布局

使用用户指定目录；未指定时建议一个题目缩写目录并纳入 S0 确认。沿用已有布局，以下是可调整的默认映射，不挪动原始数据：

    00_scope/          项目约定、设备条件、官方投稿要求与模板版本
    01_literature/     corpus.csv、方向总结、pdf/、missing.csv
    02_gallery/        figure-index.csv、图像、index.html
    03_plan/           原方案、实验清单、依赖图、评价协议
    04_data_audit/     数据清单、划分、哈希、质量报告
    05_experiments/    代码、环境、configs/、runs/、原始/汇总结果
    06_baselines/      来源台账、长表、HTML/LaTeX比较表
    07_paper/          LaTeX、.bib、图表数据/脚本/导出、prompts/、PDF
    08_audit/          覆盖矩阵、主张证据表、审计与修复记录
    09_delivery/       文件索引、复现指引、受限材料获取说明
    project-manifest.json

保留全部中间文件；大文件可引用既有绝对路径并记录哈希、权限和获取方式。不要无意义复制整个数据集。禁止把凭证/私钥放进交付包。

## 阶段状态机

状态依次为 awaiting_start → in_progress → awaiting_acceptance → accepted。blocked 表示有真实阻塞，不算完成；skipped 表示用户同意跳过，不等于执行成功。

每个 history 事件包含 phase、event（start_approved/completed/accepted/blocked/scope_changed）、实际发生时间、scope、user_quote（批准/验收事件必填）、artifacts 和 unresolved。批准时间来自实际消息/会话记录，不可编造。完成事件不能替代 accepted。用户同时批准当前验收和下一阶段时，记录两个不同事件及同一真实原话。

阶段开始消息范式：“S3 将审查这些数据集的完整性、划分与泄漏，产出质量报告；预计使用这些资源。是否开始？”

阶段结束消息范式：“S3 完成：这些项通过，这些问题已修复/仍存在，证据在这些路径。S4 拟按清单实现并运行这些实验，预算为这些。是否验收 S3 并开始 S4？”

用户既有的明确授权持续有效；只在改变范围或触及尚未批准阶段时再询问。不得用本文件恢复已被用户撤销的授权。

## project-manifest.json

从 assets/project-manifest.json 复制空白模板。所有 ID 全局同类唯一；登记实际文件，空数组不代表证据存在。相对路径以清单所在目录为根；schema_version 为 1。

| 区域 | 内容约定 |
|---|---|
| project | title、kind（empirical/theoretical/review）、target_venue、submission_cycle |
| scope | deliverable（full_paper/partial）、approval_quote、selected_phases、required_roles、required_experiment_ids、required_metric_ids、diagram_mode、accepted_placeholders |
| phase_state | current、status、history；只记真实批准和完成事件 |
| papers | id、title、venue、year、doi_or_url；baseline 来源必须可定位 |
| datasets | id、artifact_ids、audit_status（passed/conditional/failed/pending）、limitations、approval_quote（有限条件通过时） |
| experiments | id、status（succeeded/failed/blocked/not_run/excluded）、dependency_ids、run_ids；excluded 另记 exclusion_reason、approval_quote |
| runs | id、experiment_id、status（succeeded/failed/running）、dataset_ids、config_artifact_id、code_artifact_id、log_artifact_id、result_artifact_ids、seed、started_at、ended_at |
| metrics | id、name、unit、direction（max/min）；非单调指标分组说明，不勉强评最优 |
| baseline_values | id、paper_id（本工作用 ours）、metric_id、comparison_group、source_kind（reported/reproduced/ours/estimated_from_figure）、value、unit、protocol、source_locator、source_artifact_ids、run_ids、comparable；缺数 value=null 并填 missing_reason |
| claims | id、text、evidence_artifact_ids、verified（布尔）、limitations |
| artifacts | id、role、path、sha256、status（present/placeholder）、description |
| baseline_table | artifact_id、source_data_artifact_id、manuscript_locator、verified_in_manuscript（布尔） |
| issues | id、severity（blocking/major/minor）、status（open/resolved/accepted）、description、resolution、approval_quote |

完整实证论文的核心 role：scope、corpus_inventory、figure_gallery、experiment_plan、data_audit、experiment_results、baseline_table、baseline_source_data、manuscript_source、manuscript_pdf、integrity_report、delivery_index、reproduction_instructions。若从中途启动，可登记已存在的产物。非必要的 S1 被用户明确省略时在 scope.skip_reasons 登记原话和原因，不假造语料库；其他研究类型按批准后的适用范围调整。

baseline_values 中每个数值对应一个论文/协议/指标，不在记录中放“最优”等人工判定代替原值。reported 须有原文文件证据和页/表位置；reproduced/ours 须指向真实成功 run。相同指标的 ours 与至少一个外部数值只有在 comparison_group、unit、protocol 兼容且 comparable=true 时才构成可比组。原报与复现即使数值相同也保留独立记录。

artifacts 的 sha256 是实际文件哈希。清单本身不登记自身哈希，避免自引用。目录不冒充文件证据；目录内容用可核验的索引文件及必要单文件记录。accepted_placeholders 是用户明确同意的图占位 artifact ID，不能用于豁免论文、baseline、实验数据等关键材料。

## 检查器与人工审查

scripts/audit_project.py 仅用 Python 标准库，读取清单与所登记文件：核对类型、ID/链接、文件存在/哈希、实验运行、指标与 baseline、关键产物和未决问题。draft 模式允许进行中的空缺并提示；final 模式要求清单所声明的交付范围齐备。输出退出码 0 表示结构检查无 error，1 表示发现问题，2 表示输入/执行错误；均不是科学真实性认证。

交付全篇实证论文时不得为让脚本通过而改成 partial、删掉 required IDs、删掉失败记录、缩短范围或移除 required roles。只根据用户批准的真实范围变更更新清单，并保留变更记录。脚本看不到未登记问题，因此须与原方案逐项人工对账。

可把结构审计报告写入 08_audit，但不要让报告记录自身哈希。交付审计还必须验证 LaTeX/PDF 中表确实存在、数值高亮正确、引用有效和版式可读；布尔标志只能在做完该检查后填写。
