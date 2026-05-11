# DeepAlpha 石油情报分析报告

## 用户问题

油价会涨吗？

## 系统识别结果

- 资产类型：oil
- 用户意图：供给驱动
- 紧急程度：normal
- 推荐账号：@Reuters、@Bloomberg、@IsraelWarRoom、@sentdefender、@RH_Waves
- 抓取任务：from:@Reuters OR from:@Bloomberg、from:@IsraelWarRoom OR from:@sentdefender
- 路由原因：当前原油市场处于【供给驱动】阶段

## 当前市场阶段

- 阶段：supply_risk

## 综合判断

- 方向：**利多原油**
- 抓取总量：520
- 清洗后有效情报：80
- 错误数：0

## 置信度

- 聚合置信度：**0.51**
- 平均影响等级：2.7

## 关键证据

- `@SENTOVA` [利多原油, 影响5级] Oil spikes, equities puke on the open. Textbook geopolitical premium. This is the latest chapter in 触发 2 个信号: Hormuz, tanker seizure
- `@JavierBlas` [利多原油, 影响5级] According to both the NYT and the WSJ, President Trump is skeptical of the latest proposal from Iran 触发 2 个信号: blockade, Hormuz
- `@JavierBlas` [利多原油, 影响5级] According to , Iran has given the US a new proposal for reaching a deal on the reopening of the Stra 触发 2 个信号: blockade, Hormuz
- `@JavierBlas` [利多原油, 影响5级] If Hormuz blockade continues, all would change. But perspective matters. See the IMF global economic 触发 2 个信号: blockade, Hormuz
- `@Reuters` [利多原油, 影响5级] Healthcare workers in Tehran expressed concern over a possible medicine shortage as a naval blockade 触发 2 个信号: blockade, Hormuz

## v0.2 事件级判断

- 输入推文：80 条
- 聚合事件：8 个
- 事件级方向：**利多原油**
- 事件级置信度：**0.42**
- 是否需要二次确认：是
- 说明：基于 5 个事件级方向信号聚合。

## 核心事件与证据链

### oil / energy / crude

- 事件ID：`f8fb922c73dbc545`
- 来源账号：@aeberman12
- 独立来源数：1
- 扩散/重复来源数：0
- 证据质量：single_source / single_source
- 来源平均可信度：6.0
- 信号类型：information_signal
- 方向判断：暂无明确方向
- 是否需要二次确认：是
- 摘要：oil / energy / crude：证据质量 single_source，方向 暂无明确方向，需要二次确认。

### oil

- 事件ID：`38f36904727cfb85`
- 来源账号：@Reuters
- 独立来源数：1
- 扩散/重复来源数：2
- 证据质量：single_source / single_source
- 来源平均可信度：10.0
- 信号类型：information_signal
- 方向判断：利多原油
- 是否需要二次确认：是
- 摘要：oil：证据质量 single_source，方向 利多原油，需要二次确认。

### trump / Strait Hormuz / Iran Hormuz

- 事件ID：`fd0d0bb6a428405c`
- 来源账号：@Alhadath_Brk、@JavierBlas、@Reuters、@dave_brown24
- 独立来源数：4
- 扩散/重复来源数：1
- 证据质量：strong / strong_multi_source
- 来源平均可信度：6.8
- 信号类型：information_signal
- 方向判断：利多原油
- 是否需要二次确认：否
- 摘要：trump / Strait Hormuz / Iran Hormuz：证据质量 strong，方向 利多原油，可进入方向判断。

### oil / sanctions / sanction / supply

- 事件ID：`0d2a2b32f199087e`
- 来源账号：@JavierBlas、@RKelanic、@Reuters
- 独立来源数：3
- 扩散/重复来源数：1
- 证据质量：strong / strong_multi_source
- 来源平均可信度：8.0
- 信号类型：information_signal
- 方向判断：利多原油
- 是否需要二次确认：否
- 摘要：oil / sanctions / sanction / supply：证据质量 strong，方向 利多原油，可进入方向判断。

### oil / crude / energy / inventory

- 事件ID：`8b6fc7ae9ec27d42`
- 来源账号：@aeberman12
- 独立来源数：1
- 扩散/重复来源数：1
- 证据质量：single_source / single_source
- 来源平均可信度：6.0
- 信号类型：information_signal
- 方向判断：暂无明确方向
- 是否需要二次确认：是
- 摘要：oil / crude / energy / inventory：证据质量 single_source，方向 暂无明确方向，需要二次确认。


## 相关来源账号

- `@Reuters`
- `@Bloomberg`
- `@IsraelWarRoom`
- `@sentdefender`
- `@RH_Waves`
- `@SENTOVA`
- `@JavierBlas`

## 图谱文件路径

- `./graph_data/关系图谱.json`

## 风险提示

- X/Twitter 信息可能存在误传、延迟、删除、账号改名或上下文缺失。
- 单一来源消息需要等待更多高可信来源确认。
- 地缘和能源市场变化较快，应结合后续官方公告、通讯社报道和市场价格反应继续跟踪。

## 免责声明

本报告仅用于信息分析与风险提示，不构成投资建议
