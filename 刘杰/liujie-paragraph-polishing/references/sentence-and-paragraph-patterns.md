# 句子与段落范式

以下例句只示范表达方式，不是来自待修改论文的事实。不得直接复制其中的实验、控制或结论。保留原稿的技术名词，不为了词汇变化而给同一概念不断换名。

## 1 主体先行不等于每句 We

根据句子任务选择主语：

| 任务 | 可用主语与动词 |
|---|---|
| 说明对象 | “The model represents …” |
| 提出方法 | “We formulate …” |
| 说明组件 | “The constraint preserves …” |
| 介绍比较 | “The second comparison isolates …” |
| 报告结果 | “The method reduces … under …” |
| 引用图表 | “Table 2 compares …” |
| 解释证据 | “These results support …” |

被动语态不是错误。操作对象比执行者更重要时，可以写“The weights remain fixed during adaptation.”。避免无必要的“It is observed that…”和“An investigation was carried out to…”。

**绕弯：**

> “For the purpose of investigating whether the observed difference could be attributed to changes in the input configuration, a series of comparisons was performed.”

**直接：**

> “We test whether the input configuration explains the observed difference. The comparisons vary the input configuration while keeping the remaining settings fixed.”

前置条件很短且决定句意时不必强行后移。“At the lowest budget, the two methods recover the same number of targets.”很清楚。

## 2 让动词承载动作

优先将名词化操作还原为具体动作：

| 拖长表达 | 更直接的表达 |
|---|---|
| perform an evaluation of | evaluate |
| conduct an investigation into | investigate |
| make a comparison between | compare |
| provide an explanation for | explain |
| carry out the estimation of | estimate |
| it can be seen from the results that | 直接报告结果 |
| in order to be able to | to |
| due to the fact that | because |

这些是判断提示，不是自动替换字典。若名词是已定义的统计量、方法名或技术对象，保留它。

## 3 拆句时保留关系

**拥挤：**

> “The estimator, which is trained on the calibration observations and uses a source representation that remains fixed during adaptation, reduces the objective while leaving the source representation unchanged.”

保留原句所述关系，可拆为：

> “We train the estimator on the calibration observations. It uses a source representation that remains fixed during adaptation. The estimator reduces the objective without changing that representation.”

以上只改变句式，保留训练依据、固定对象和目标值降低的关系，不增加输入适配或映射变化等原句未述的操作。若原稿另有“improving stability”等主张，应核对已有证据，保留已支持的结果及条件；未经支持的主张纠正须与纯句式改写分开说明，不能凭语言直觉补写或删除。

不要以固定“每句不超过若干词”为标准；判断读者能否一次识别主句、条件和比较对象。

## 4 句间有真实递进

- 后一句接住前一句已有的对象，再增加信息。
- 使用 this / these 时，让最近的指代对象明确；必要时重复具体名词。
- However 表示确有转折，therefore 表示确有推论，whereas 表示具体对比。
- 不为显得连贯而在每句前添加 Moreover、Furthermore、Additionally。

**流水账：**

> “Then, we conduct another experiment using a different setting.”

**问题驱动：**

> “The first comparison changes both the representation and the update rule. The next comparison fixes the representation and varies only the update rule. It tests whether the update rule explains the observed difference.”

只有实际固定了该条件时才能这样写；若原稿没有控制，清楚报告不足，不能替作者补造控制。

## 5 段落的四种常见任务

### 定义段

对象及用途 → 定义或公式 → 关键性质 → 后文为何需要它。

### 方法段

要解决的问题 → 关键操作 → 操作依据 → 输出或可检验后果。

### 结果段

主要发现 → 关键比较与证据 → 对问题的解释 → 尚存问题（如有）。

### 讨论段

综合判断 → 与已有解释的关系 → 能排除和不能排除的解释 → 有针对性的下一步（如有）。

不要求每段都有四句。两句话已完成任务时，不增加模板句；一段跨了两个独立任务时，才考虑拆段。

## 6 把读图描述改成结果判断

**绕弯：**

> “As can be seen from the results presented in Table 2, it can be observed that the method achieves an improvement.”

**直接：**

> “The method improves the primary metric at the lowest budget. Table 2 reports the comparison with the matched control.”

实际采用时给出原稿已有的指标、比较对象和关键数值。不要让读者猜“improvement”指什么。

图表之后的解释应告诉读者该结果回答了什么。不要接一句“The results are shown in the figure.”就结束。

## 7 删除赘述的判据

问：**删除这句话后，科学判断是否变强、变义或失去证据来源？**

- 若不会，并且该句没有增加定义、方法、证据、推论或有后果的局限，可删除或合并。
- 若会，保留必要信息，改成更短且贴近判断的限定。

**可压缩的自我辩护：**

> “It is important to emphasize that the interpretation of these results should be approached with considerable caution.”

**有实际内容的限定：**

> “The comparison uses one device, so it does not estimate variation across devices.”

第二句说明了限制影响的具体推论，不能仅因含有否定句而删除。

## 8 比较句保持对象对称

明确是哪些方法、相同还是不同的数据、哪个预算、哪个终点。避免把两种不同指标放在同一个“更好”下面。

如果完整方法优于移除组件的对照，但另一个替代方法表现更好，可写：

> “The component improves recovery relative to its removal control. The alternative objective achieves a higher recovery rate under the same budget.”

两句表达不同问题。不能改成“The proposed method outperforms existing approaches.”。

## 9 时态、术语和语法

- 领域事实、定义、算法行为及图表内容通常用现在时。
- 已完成的实验操作和研究回顾可用过去时；同一段内按叙述任务保持一致。
- 不把一条熟悉的技术术语换成生硬“高级词”；首次出现的必要缩写给出含义。
- 通俗指读者容易理解逻辑，不指删除专业概念或把严谨关系口语化。
- 学习导师的论证顺序，同时修复原稿中的语法瑕疵；不能把 “a higher security” 等不自然表达当作风格特征保留。
