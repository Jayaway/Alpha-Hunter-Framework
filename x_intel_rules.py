# -*- coding: utf-8 -*-
"""
X(Twitter) 实时情报抓取系统 - 可执行前置规则
================================================
基于高价值账号清单生成，用于抓取前筛选。
生成时间: 2026-04-27
"""

# ============================================================
# 1. 按优先级分类账号池
# ============================================================

# S级：必须实时监控（推文即价格，几分钟内可移动市场1-3%）
S_LEVEL = [
    # --- 国家领导人（最高优先级，政策/制裁/产量表态直接影响油价）---
    "@realDonaldTrump",       # 美国总统，制裁/OPEC+/Drill baby drill
    "@VladimirPutin",         # 俄罗斯总统，OPEC+产量/乌克兰地缘
    # --- 核心OPEC+官方渠道 ---
    "@KSAmofaEN",             # 沙特外交部英文（MBS决策渠道）
    # --- 原油实时数据/新闻（价格/库存/OPEC决策）---
    "@DeItaone",              # Walter Bloomberg，能源头条快讯
    "@JavierBlas",            # Bloomberg首席能源记者，全球原油实时报道
    "@JKempEnergy",           # John Kemp，数据驱动供需分析
    "@OilandEnergy",          # OilPrice.com，Brent/WTI新闻
    # --- 地缘战争前线（冲突升级=供应中断风险）---
    "@TheStudyofWar",         # ISW每日战役评估
    "@IDF",                   # 以色列国防军，中东行动实时更新
    "@Conflicts",             # 全球冲突突发新闻聚合
    # --- 突发新闻/记者爆料（常领先主流媒体数小时）---
    "@RichardEngel",          # NBC首席外事记者
    "@samdagher",             # Bloomberg资深中东记者
    "@JackDetsch",            # Politico五角大楼记者
    "@SangerNYT",             # NYT国家安全记者
    # --- 宏观新闻源 ---
    "@Reuters",               # 路透社，中性快速事实新闻
    "@Bloomberg",             # 彭博，专业金融数据
    "@WSJ",                   # 华尔街日报
    "@CNBC",                  # 实时商业与市场直播
]

# A级：高频监控（专业分析，信息密度高，15分钟级响应）
A_LEVEL = [
    # --- 原油交易/分析 ---
    "@Rory_Johnston",         # 石油市场研究员，供需模型
    "@OilSheppard",           # FT能源市场编辑
    "@DB_WTI",                # WTI交易评论
    "@ClydeCommods",          # Reuters亚洲原油
    "@anasalhajji",           # 能源经济学家，中东供需
    "@TomKloza",              # OPIS联合创始人，库存/价格
    "@GasBuddyGuy",           # GasBuddy，需求数据
    "@KobeissiLetter",        # 原油突发新闻breakdown
    "@CMEGroup",              # 原油期货合约数据
    "@TankersTrackers",       # 原油运输/库存流动
    "@OOTT",                  # Oil Twitter社区
    # --- 地缘政治/战争前线 ---
    "@RALee85",               # 俄罗斯军事专家
    "@DefenceU",              # 乌克兰国防部官方
    "@WarMonitor3",           # 多场战争实时报道
    "@War_Mapper",            # 战场地图/geolocation
    "@Osinttechnical",        # 开源情报装备验证
    "@sentdefender",          # 中东/欧洲冲突OSINT
    "@IsraelWarRoom",         # 以色列视角中东威胁
    "@MiddleEastEye",         # 独立中东地面报道
    "@visegrad24",            # 中东欧/全球冲突新闻
    # --- 记者爆料 ---
    "@ChristopherJM",         # 长期驻乌克兰记者
    "@IAPonomarenko",         # 乌克兰战地记者
    "@AlexCrawfordSky",       # Sky News特派记者
    "@yarotrof",              # WSJ首席外事记者
    "@markmackinnon",         # Globe and Mail资深国际记者
    "@nickschifrin",          # PBS外事与国防记者
    # --- 宏观/金融 ---
    "@federalreserve",        # 美联储官方
    "@ZeroHedge",             # 另类市场评论
    "@elerianm",              # Allianz首席经济顾问
    "@charliebilello",        # 数据驱动市场统计
    "@LizAnnSonders",         # Charles Schwab首席策略师
    "@GoldmanSachs",          # 高盛市场研究
    "@JPMorgan",              # 摩根大通
    # --- 国家领导人 ---
    "@RTErdogan",             # 土耳其总统，控制黑海-地中海航道
    "@narendramodi",          # 印度总理，全球最大原油进口国
    "@Claudiashein",          # 墨西哥总统
    "@LulaOficial",           # 巴西总统
    "@officialABAT",          # 尼日利亚总统
    "@EmmanuelMacron",        # 法国总统
]

# B级：普通监控（深度分析/补充视角，1小时级）
B_LEVEL = [
    # --- 原油补充 ---
    "@OGJOnline",             # Oil & Gas Journal
    "@offshoremgzn",          # Offshore Magazine
    "@OilVoice",              # 上游原油行业新闻
    "@OilStockTrader",        # 能源板块交易
    "@AndrewPancholi",        # 原油周期/地缘预测
    "@staunovo",              # 原油市场策略
    "@Ole_S_Hansen",          # Saxo Bank商品策略
    "@BrynneKKelly",          # 原油交易洞察
    "@aeberman12",            # 地质学家，长期趋势
    "@RealPeterLinder",       # 50+年原油价格跟踪
    "@Energy_Tidbits",        # 能源研究备忘录
    "@Big_Orrin",             # 物理原油交易
    "@Samir_Madani",          # OPEC政策跟踪
    "@PetroleumEcon",         # 石油经济分析
    "@Barchart",              # 原油实时图表
    "@MrMBrown",              # 原油市场新闻评论
    "@GavinJMaguire",         # Reuters能源转型
    "@RH_Waves",              # 原油价格展望/Hormuz风险
    "@crudegusher",           # Sankey Research
    # --- 地缘/OSINT补充 ---
    "@EuromaidanPR",          # 独立乌克兰公民媒体
    "@IAPonomarenko",         # 乌克兰战地记者（已在A级，此处为分组引用）
    "@MarkHertling",          # 退役美陆军中将
    "@TrentTelenko",          # 后勤/装备分析
    "@MiddleEastMnt",         # 中东新闻覆盖
    "@WarMonitors",           # 中东地缘更新
    "@GPFutures",             # George Friedman团队
    "@George_Friedman",       # 地缘政治预报
    "@InsiderGeo",            # 全球军事OSINT
    "@GeoConfirmed",          # OSINT协作
    "@Tendar",                # 乌克兰OSINT
    "@Noclador",              # 军事地图/分析
    "@tatarigami_UA",         # 乌克兰军事视角
    # --- 记者补充 ---
    "@olgatokariuk",          # 乌克兰冲突一线
    "@ikhurshudyan",          # WP驻基辅
    "@myroslavapetsa",        # BBC驻基辅
    "@BelTrew",               # The Independent国际记者
    "@DanRiversITV",          # ITV News乌克兰
    "@jamiedettmer",          # VOA战地记者
    "@KyivIndependent",       # 乌克兰独立英文媒体
    "@KyivPost",              # 长期乌克兰地面报道
    "@JuliaDavis",            # 俄罗斯宣传翻译
    "@KamilGaleev",           # 后苏联地缘分析
    "@MichaelKofman",         # 俄罗斯军事专家
    "@jmalsin",               # WSJ中东记者
    "@mchancecnn",            # CNN乌克兰实地
    "@fpleitgenCNN",          # CNN驻俄边境
    # --- 宏观/金融补充 ---
    "@FinancialTimes",        # 金融时报
    "@TheEconomist",          # 经济学人
    "@Benzinga",              # 实时交易新闻
    "@StockMKTNewz",          # 股票市场新闻
    "@yardeni",               # Yardeni Research
    "@ecb",                   # 欧洲央行
    "@IMFNews",               # 国际货币基金
    "@PIMCO",                 # 固定收益/宏观
    "@FactSet",               # 金融数据
    "@morganhousel",          # 行为金融大师
    "@ritholtz",              # 市场评论
    "@PaulKrugman",           # 诺贝尔经济学奖
    "@RayDalio",              # Bridgewater创始人
    # --- 国家领导人补充 ---
    "@_FriedrichMerz",        # 德国总理
    "@Keir_Starmer",          # 英国首相
    "@vonderleyen",           # 欧盟委员会主席
    "@prabowo",               # 印尼总统
    "@AlboMP",                # 澳大利亚总理
    "@petrogustavo",          # 哥伦比亚总统
    "@JMilei",                # 阿根廷总统
    "@CyrilRamaphosa",        # 南非总统
    "@WilliamsRuto",          # 肯尼亚总统
    "@President_KR",          # 韩国总统
    # --- 中文圈补充 ---
    "@haohong_cfa",           # 洪灝，中国宏观/全球交叉
    "@caolei1",               # 曹山石，A股/港股/宏观
]

# C级：低频备用（教育/观点/娱乐性，4小时级或按需）
C_LEVEL = [
    # --- 教育/观点 ---
    "@BrianFeroldi",          # 企业分析/估值教学
    "@awealthofcs",           # 长期投资/市场行为
    "@10kdiver",              # 深度财报/投资线程
    "@fluentinfinance",       # 个人理财/投资建议
    "@PeterLBrandt",          # 经典图表交易
    "@thechartist",           # 动量/趋势跟踪
    "@alphatrends",           # 技术分析教育
    "@steenbab",              # 交易心理
    "@alaidi",                # 外汇/全球市场
    "@TheStalwart",           # 市场观察
    "@michaelbatnick",        # 投资行为
    "@ian_cassel",            # 小盘股/价值投资
    "@Travis_Jamison",        # 投资者思维
    "@BoraOzkent",            # 纳斯达克/科技
    "@CathieDWood",           # ARK Invest创新科技
    "@AswathDamodaran",       # 估值大师
    "@matt_levine",           # Bloomberg专栏
    "@SallieKrawcheck",       # 女性理财
    "@howardlindzon",         # 社交交易/市场情绪
    "@jimcramer",             # CNBC个股观点（娱乐性）
    "@DeepakShenoy",          # 新兴市场/印度
    # --- 原油低频 ---
    "@CRUDEOIL231",           # 原油信号/评论
    "@tradingcrudeoil",       # 原油交易专号
    "@TheProfTrades",         # 原油交易设置
    "@findbettertrades",      # 原油价格突破
    "@TradersParadise",       # 商品期货交易
    "@garethsoloway",         # 商品警报
    "@BigDataMiner2",         # 原油数据挖掘
    "@Chevron",               # Chevron官方
    "@WorldOil",              # 全球原油市场
    # --- 记者低频 ---
    "@JaneLytv",              # NBC科技/冲突记者
    "@langfittnpr",           # NPR乌克兰报道
    "@ElBeardsley",           # NPR冲突一线
    "@timkmak",               # NPR国防/乌克兰
    "@mschwirtz",             # NYT俄乌独家
    "@sarahrainsford",        # 前BBC东欧
    "@geoffreyyork",          # Globe and Mail
    "@ngumenyuk",             # 冲突报道专家
    "@liz_cookman",           # 中东冲突突发
    "@IuliiaMendel",          # 前乌克兰总统发言人
    "@SimonOstrovsky",        # 前Vice战地记者
    "@LynseyAddario",         # 普利策摄影记者
    "@tangentsofwar",         # War Reporter聚合
    "@raphaelahren",          # Times of Israel外交
    "@yaakovlappin",          # Jerusalem Post军事
    "@ynetnews",              # 以色列突发新闻
    "@MickyRosenfeld",        # 以色列警方发言人
    "@BklynMiddleton",        # 中东安全风险
    "@ElhananMiller",         # Times of Israel阿拉伯事务
    "@MairavZ",               # 危机组织以色列/中东
    # --- 其他 ---
    "@charlesschwab",         # Charles Schwab投资策略
    "@ftfinancenews",         # FT金融新闻专页
    "@nelderini",             # 能源未来主义者
    "@lockweedmartin",        # 原油分析师
    "@EchidnaPowerful",       # 能源社区推荐
    "@offshore",              # 海上原油
    "@Oilandgasiq",           # 石油天然气洞察
    "@EnergyOutlook",         # 中东原油经济咨询
]


# ============================================================
# 2. 按领域分类账号池
# ============================================================

# --- 原油领域 ---
OIL_GROUP = [
    "@JavierBlas", "@JKempEnergy", "@OilandEnergy", "@OilSheppard",
    "@Rory_Johnston", "@ClydeCommods", "@OGJOnline", "@offshoremgzn",
    "@OilVoice", "@CMEGroup", "@DB_WTI", "@OilStockTrader",
    "@AndrewPancholi", "@staunovo", "@Ole_S_Hansen", "@BrynneKKelly",
    "@aeberman12", "@RealPeterLinder", "@Energy_Tidbits", "@TomKloza",
    "@anasalhajji", "@GasBuddyGuy", "@Big_Orrin", "@CRUDEOIL231",
    "@crudegusher", "@Samir_Madani", "@Chevron", "@WorldOil",
    "@tradingcrudeoil", "@PetroleumEcon", "@Barchart", "@DeItaone",
    "@KobeissiLetter", "@MrMBrown", "@GavinJMaguire", "@nelderini",
    "@lockweedmartin", "@TankersTrackers", "@OOTT", "@RH_Waves",
    "@TheProfTrades", "@findbettertrades", "@TradersParadise",
    "@garethsoloway", "@BigDataMiner2", "@EchidnaPowerful",
    "@offshore", "@Oilandgasiq", "@EnergyOutlook",
]

# --- 黄金领域（从宏观/交易账号中筛选）---
GOLD_GROUP = [
    "@PeterLBrandt",          # 经典图表交易，含黄金
    "@thechartist",           # 动量/趋势跟踪
    "@alaidi",                # 外汇/全球市场（含黄金）
    "@GoldmanSachs",          # 高盛（黄金研究）
    "@JPMorgan",              # 摩根大通（黄金研究）
    "@ZeroHedge",             # 另类评论（含黄金避险分析）
    "@charliebilello",        # 市场统计（含黄金数据）
    "@Barchart",              # 实时图表（含黄金）
    "@DeItaone",              # 快讯（含黄金）
    "@garethsoloway",         # 商品警报（含黄金）
    "@TradersParadise",       # 商品期货（含黄金）
]

# --- 外汇领域 ---
FX_GROUP = [
    "@alaidi",                # 外汇与全球市场
    "@elerianm",              # 全球宏观政策
    "@federalreserve",        # 美联储（美元政策）
    "@ecb",                   # 欧洲央行（欧元政策）
    "@GoldmanSachs",          # 高盛外汇研究
    "@JPMorgan",              # 摩根大通外汇
    "@ZeroHedge",             # 另类外汇评论
    "@DeItaone",              # 快讯（含外汇）
    "@Barchart",              # 实时图表（含外汇）
    "@LizAnnSonders",         # 策略师（含外汇视角）
    "@charliebilello",        # 数据驱动（含美元指数）
    "@Ole_S_Hansen",          # Saxo Bank商品策略（含外汇）
]

# --- 地缘政治领域 ---
GEOPOLITICS_GROUP = [
    "@TheStudyofWar", "@RALee85", "@DefenceU", "@WarMonitor3",
    "@EuromaidanPR", "@War_Mapper", "@Osinttechnical",
    "@IAPonomarenko", "@MarkHertling", "@TrentTelenko",
    "@IDF", "@IsraelWarRoom", "@MiddleEastEye", "@MiddleEastMnt",
    "@Conflicts", "@sentdefender", "@visegrad24", "@WarMonitors",
    "@GPFutures", "@George_Friedman", "@InsiderGeo",
    "@GeoConfirmed", "@Tendar", "@Noclador", "@tatarigami_UA",
    "@Defmon3", "@KamranBokhari",
]

# --- 记者爆料领域 ---
JOURNALIST_SCOOP_GROUP = [
    "@RichardEngel", "@samdagher", "@AlexCrawfordSky", "@yarotrof",
    "@markmackinnon", "@AnshelPfeffer", "@BoothWilliam", "@jmalsin",
    "@ngumenyuk", "@liz_cookman", "@ChristopherJM", "@IAPonomarenko",
    "@olgatokariuk", "@JaneLytv", "@ikhurshudyan", "@myroslavapetsa",
    "@langfittnpr", "@ElBeardsley", "@timkmak", "@mschwirtz",
    "@nickschifrin", "@JackDetsch", "@SangerNYT", "@mchancecnn",
    "@fpleitgenCNN", "@sarahrainsford", "@geoffreyyork", "@BelTrew",
    "@DanRiversITV", "@jamiedettmer", "@EuromaidanPR", "@KyivIndependent",
    "@KyivPost", "@IuliiaMendel", "@JuliaDavis", "@KamilGaleev",
    "@MichaelKofman", "@tatarigami_UA", "@Noclador",
    "@raphaelahren", "@yaakovlappin", "@ynetnews", "@MickyRosenfeld",
    "@BklynMiddleton", "@ElhananMiller", "@MairavZ",
    "@SimonOstrovsky", "@LynseyAddario", "@tangentsofwar",
]

# --- 国家领导人领域 ---
LEADERS_GROUP = [
    "@realDonaldTrump", "@VladimirPutin", "@KSAmofaEN",
    "@Claudiashein", "@LulaOficial", "@officialABAT", "@WilliamsRuto",
    "@RTErdogan", "@narendramodi", "@EmmanuelMacron",
    "@_FriedrichMerz", "@Keir_Starmer", "@vonderleyen",
    "@prabowo", "@AlboMP", "@petrogustavo", "@CyrilRamaphosa",
    "@JMilei", "@President_KR",
]

# --- 加密货币领域（从现有账号中筛选相关）---
CRYPTO_GROUP = [
    "@CathieDWood",           # ARK Invest，含加密投资
    "@howardlindzon",         # 社交交易，含加密情绪
    "@BoraOzkent",            # 科技趋势，含加密
    "@DeItaone",              # 快讯（含加密突发）
    "@ZeroHedge",             # 另类评论（含加密分析）
]

# --- 全球宏观领域 ---
MACRO_GROUP = [
    "@elerianm", "@charliebilello", "@LizAnnSonders", "@ritholtz",
    "@PaulKrugman", "@awealthofcs", "@RayDalio", "@morganhousel",
    "@10kdiver", "@BrianFeroldi", "@fluentinfinance",
    "@WSJ", "@CNBC", "@Bloomberg", "@FinancialTimes", "@Reuters",
    "@ZeroHedge", "@TheEconomist", "@yardeni", "@StockMKTNewz",
    "@Benzinga", "@GoldmanSachs", "@JPMorgan", "@federalreserve",
    "@ecb", "@IMFNews", "@FactSet", "@charlesschwab", "@PIMCO",
    "@ftfinancenews", "@PeterLBrandt", "@TheStalwart",
    "@michaelbatnick", "@AswathDamodaran", "@matt_levine",
    "@SallieKrawcheck", "@DeepakShenoy", "@haohong_cfa", "@caolei1",
]


# ============================================================
# 3. 关键词监控规则（组合关键词对）
# ============================================================

# 格式: (关键词1, 关键词2, 影响领域, 优先级, 说明)
# 当一条推文同时包含关键词1和关键词2时触发

KEYWORD_RULES = [
    # --- 原油核心触发 ---
    ("OPEC", "cut", "oil", "S", "OPEC+减产/增产决策"),
    ("OPEC", "production", "oil", "S", "OPEC产量调整"),
    ("OPEC", "meeting", "oil", "S", "OPEC会议"),
    ("OPEC", "emergency", "oil", "S", "OPEC紧急会议"),
    ("OPEC+", "quota", "oil", "S", "OPEC+配额变化"),
    ("Saudi", "oil", "oil", "S", "沙特原油动态"),
    ("Russia", "oil", "oil", "S", "俄罗斯原油动态"),
    ("Iran", "oil", "oil", "S", "伊朗原油/制裁"),
    ("Iran", "sanction", "oil", "S", "伊朗制裁"),
    ("Iran", "Hormuz", "oil", "S", "霍尔木兹海峡风险"),
    ("Iran", "nuclear", "geopolitics", "S", "伊朗核问题"),
    ("Venezuela", "oil", "oil", "A", "委内瑞拉原油"),
    ("EIA", "inventory", "oil", "S", "EIA库存数据"),
    ("EIA", "crude", "oil", "S", "EIA原油数据"),
    ("API", "inventory", "oil", "A", "API库存数据"),
    ("WTI", "break", "oil", "A", "WTI关键技术位"),
    ("Brent", "break", "oil", "A", "Brent关键技术位"),
    ("crude", "supply", "oil", "A", "原油供应"),
    ("crude", "demand", "oil", "A", "原油需求"),
    ("Strait", "Hormuz", "oil", "S", "霍尔木兹海峡"),
    ("Red Sea", "attack", "oil", "S", "红海袭击/航运"),
    ("Red Sea", "Houthi", "oil", "S", "红海胡塞武装"),
    ("tanker", "attack", "oil", "S", "油轮袭击"),
    ("pipeline", "shutdown", "oil", "A", "管道关闭"),
    ("refinery", "fire", "oil", "A", "炼油厂火灾"),
    ("refinery", "shutdown", "oil", "A", "炼油厂关闭"),

    # --- 地缘战争触发 ---
    ("Ukraine", "counteroffensive", "geopolitics", "S", "乌克兰反攻"),
    ("Ukraine", "missile", "geopolitics", "S", "乌克兰导弹"),
    ("Russia", "nuclear", "geopolitics", "S", "俄罗斯核威胁"),
    ("Russia", "mobilization", "geopolitics", "S", "俄罗斯动员"),
    ("Israel", "Iran", "geopolitics", "S", "以色列-伊朗冲突"),
    ("Israel", "Hezbollah", "geopolitics", "S", "以色列-真主党"),
    ("Israel", "Gaza", "geopolitics", "S", "以色列-加沙"),
    ("Israel", "strike", "geopolitics", "S", "以色列打击"),
    ("Iran", "strike", "geopolitics", "S", "伊朗打击"),
    ("Iran", "retaliate", "geopolitics", "S", "伊朗报复"),
    ("ceasefire", "Israel", "geopolitics", "S", "以色列停火"),
    ("ceasefire", "Ukraine", "geopolitics", "S", "乌克兰停火"),
    ("NATO", "Article 5", "geopolitics", "S", "北约第五条"),
    ("nuclear", "war", "geopolitics", "S", "核战争风险"),
    ("war", "escalation", "geopolitics", "S", "战争升级"),
    ("Taiwan", "war", "geopolitics", "S", "台海冲突"),
    ("Taiwan", "military", "geopolitics", "A", "台海军事"),
    ("China", "Taiwan", "geopolitics", "A", "中国-台湾"),
    ("North Korea", "missile", "geopolitics", "A", "朝鲜导弹"),

    # --- 美国政策/关税触发 ---
    ("Trump", "tariff", "macro", "S", "特朗普关税政策"),
    ("Trump", "sanction", "oil", "S", "特朗普制裁"),
    ("Trump", "oil", "oil", "S", "特朗普原油政策"),
    ("Trump", "Iran", "oil", "S", "特朗普-伊朗"),
    ("Trump", "China", "macro", "S", "特朗普-中国"),
    ("Trump", "trade", "macro", "S", "特朗普贸易政策"),
    ("tariff", "China", "macro", "S", "对华关税"),
    ("tariff", "oil", "oil", "A", "关税对原油影响"),
    ("executive order", "energy", "oil", "A", "能源行政令"),
    ("sanction", "Russia", "oil", "S", "对俄制裁"),

    # --- 美联储/利率触发 ---
    ("Fed", "rate cut", "macro", "S", "美联储降息"),
    ("Fed", "rate hike", "macro", "S", "美联储加息"),
    ("Fed", "pause", "macro", "A", "美联储暂停"),
    ("Fed", "dot plot", "macro", "A", "美联储点阵图"),
    ("Fed", "meeting", "macro", "A", "美联储会议"),
    ("interest rate", "decision", "macro", "S", "利率决议"),
    ("inflation", "CPI", "macro", "S", "通胀CPI"),
    ("inflation", "PCE", "macro", "S", "通胀PCE"),
    ("jobs", "report", "macro", "A", "就业报告"),
    ("nonfarm", "payroll", "macro", "S", "非农就业"),
    ("recession", "warning", "macro", "A", "衰退预警"),

    # --- 黄金触发 ---
    ("gold", "record", "gold", "A", "黄金创纪录"),
    ("gold", "surge", "gold", "A", "黄金暴涨"),
    ("gold", "crash", "gold", "A", "黄金暴跌"),
    ("gold", "safe haven", "gold", "A", "黄金避险"),
    ("gold", "central bank", "gold", "A", "央行购金"),
    ("gold", "demand", "gold", "B", "黄金需求"),

    # --- 外汇触发 ---
    ("dollar", "index", "fx", "A", "美元指数"),
    ("dollar", "weak", "fx", "A", "美元走弱"),
    ("dollar", "strong", "fx", "A", "美元走强"),
    ("EUR", "USD", "fx", "B", "欧元/美元"),
    ("USD", "JPY", "fx", "B", "美元/日元"),
    ("yuan", "devalue", "fx", "A", "人民币贬值"),

    # --- 加密触发 ---
    ("Bitcoin", "ETF", "crypto", "A", "比特币ETF"),
    ("Bitcoin", "halving", "crypto", "A", "比特币减半"),
    ("SEC", "crypto", "crypto", "A", "SEC加密监管"),
    ("Bitcoin", "record", "crypto", "A", "比特币创纪录"),
    ("Bitcoin", "crash", "crypto", "A", "比特币暴跌"),

    # --- 突发事件通用触发 ---
    ("BREAKING", "oil", "oil", "S", "原油突发"),
    ("BREAKING", "war", "geopolitics", "S", "战争突发"),
    ("BREAKING", "attack", "geopolitics", "S", "袭击突发"),
    ("BREAKING", "missile", "geopolitics", "S", "导弹突发"),
    ("JUST IN", "sanction", "oil", "S", "制裁突发"),
    ("exclusive", "report", "geopolitics", "A", "独家报道"),
    ("scoop", "diplomatic", "geopolitics", "A", "外交独家"),
]

# --- 单关键词高优先级监控（出现即触发）---
SINGLE_KEYWORD_ALERTS = {
    "oil": ["OPEC+", "Hormuz", "Strait of Hormuz", "WTI", "Brent",
            "crude oil", "inventory draw", "inventory build",
            "supply disruption", "production cut"],
    "geopolitics": ["nuclear strike", "ceasefire violated", "full-scale invasion",
                    "martial law", "mobilization", "Article 5",
                    "ICBM", "ballistic missile"],
    "macro": ["emergency rate", "emergency meeting", "flash crash",
              "circuit breaker", "black swan", "bank run"],
}


# ============================================================
# 4. 抓取频率配置
# ============================================================

CRAWL_FREQUENCY = {
    "S": {
        "interval_seconds": 300,       # 每5分钟
        "description": "S级账号：实时监控，每5分钟抓取一次",
        "max_retries": 3,
        "timeout_seconds": 30,
        "priority": 1,
    },
    "A": {
        "interval_seconds": 900,       # 每15分钟
        "description": "A级账号：高频监控，每15分钟抓取一次",
        "max_retries": 2,
        "timeout_seconds": 30,
        "priority": 2,
    },
    "B": {
        "interval_seconds": 3600,      # 每1小时
        "description": "B级账号：普通监控，每1小时抓取一次",
        "max_retries": 2,
        "timeout_seconds": 30,
        "priority": 3,
    },
    "C": {
        "interval_seconds": 14400,     # 每4小时
        "description": "C级账号：低频备用，每4小时抓取一次",
        "max_retries": 1,
        "timeout_seconds": 30,
        "priority": 4,
    },
}

# 非交易时段降频（美东时间 20:00-06:00，即北京时间 08:00-18:00 以外）
OFF_HOURS_MULTIPLIER = 2  # 非交易时段频率降低倍数

# 周末降频
WEEKEND_MULTIPLIER = 4    # 周末频率降低倍数


# ============================================================
# 5. AI分析优先级规则
# ============================================================

# 哪些内容需要送入AI分析
AI_ANALYSIS_RULES = {
    "must_analyze": {
        "description": "必须AI分析的内容",
        "conditions": [
            "S级账号发布的推文",
            "包含S级关键词对的推文",
            "包含SINGLE_KEYWORD_ALERTS中关键词的推文",
            "领导人账号发布的推文",
            "包含'BREAKING'或'JUST IN'的推文",
        ],
    },
    "should_analyze": {
        "description": "建议AI分析的内容",
        "conditions": [
            "A级账号发布的推文",
            "包含A级关键词对的推文",
            "转发量>100的推文",
            "包含数据图表的推文",
        ],
    },
    "optional_analyze": {
        "description": "可选AI分析的内容",
        "conditions": [
            "B级账号发布的推文",
            "包含B级关键词对的推文",
            "转发量>50的推文",
        ],
    },
}


# ============================================================
# 6. Selenium + Cookie + CSV 项目接入建议
# ============================================================

"""
=== Selenium + Cookie + CSV 接入架构建议 ===

1. Cookie管理方案：
   - 使用 browser-cookie3 或 manual cookie export
   - Cookie存储格式: JSON文件，按账号分组
   - 自动刷新: 检测401/403时触发重新登录
   - Cookie轮换: 多账号轮换避免频率限制

2. Selenium优化策略：
   - 使用 undetected-chromedriver 防检测
   - Headless模式降低资源消耗
   - 页面加载等待: WebDriverWait + expected_conditions
   - 滚动加载: 模拟滚动获取更多推文
   - 代理轮换: 每个S级账号使用独立代理IP

3. CSV数据存储方案：
   - 文件命名: {date}_{level}_{group}.csv
   - 字段: timestamp, username, tweet_id, text, likes, retweets,
           replies, impressions, has_media, keyword_hits, ai_priority
   - 每日归档: 按日期分割CSV文件
   - 增量写入: 使用 'a' 模式追加，避免内存溢出

4. 推荐项目结构：

   x_intel_system/
   ├── config/
   │   ├── accounts.py          # 本文件（账号池+规则）
   │   ├── cookies/             # Cookie JSON文件
   │   └── proxies.txt          # 代理IP列表
   ├── crawler/
   │   ├── selenium_crawler.py  # Selenium抓取引擎
   │   ├── cookie_manager.py    # Cookie管理
   │   ├── rate_limiter.py      # 频率控制
   │   └── proxy_rotator.py     # 代理轮换
   ├── analyzer/
   │   ├── keyword_filter.py    # 关键词匹配
   │   ├── ai_analyzer.py       # AI分析模块
   │   └── sentiment.py         # 情绪分析
   ├── storage/
   │   ├── csv_writer.py        # CSV写入
   │   └── daily_archiver.py    # 每日归档
   ├── main.py                  # 主入口
   └── logs/                    # 日志目录

5. 核心抓取流程伪代码：

   for level in ['S', 'A', 'B', 'C']:
       accounts = get_accounts_by_level(level)
       interval = CRAWL_FREQUENCY[level]['interval_seconds']

       for account in accounts:
           tweets = selenium_scrape(account, cookie=load_cookie(account))

           for tweet in tweets:
               # 关键词匹配
               keyword_hits = match_keywords(tweet.text)
               ai_priority = calculate_ai_priority(account, keyword_hits)

               # 写入CSV
               write_to_csv(tweet, keyword_hits, ai_priority)

               # S级关键词触发即时AI分析
               if ai_priority == 'S':
                   ai_analyze(tweet)

           sleep_with_jitter(interval / len(accounts))

6. 反检测建议：
   - User-Agent轮换
   - 随机延迟: base_interval * random(0.8, 1.2)
   - 模拟人类行为: 随机滚动、停顿
   - 限制每小时请求: S级<60次/小时, A级<30次/小时
   - 使用X Premium API作为补充（如有预算）

7. 关键词匹配优化：
   - 使用正则预编译: re.compile(pattern, re.IGNORECASE)
   - 多关键词AND逻辑: 所有关键词对中的词必须同时出现
   - 模糊匹配: 支持常见变体 (e.g., "rate cut" / "rate-cut" / "ratecut")
   - 中文关键词: 如有中文推文需额外配置
"""


# ============================================================
# 7. 辅助函数
# ============================================================

def get_accounts_by_level(level: str) -> list:
    """根据优先级获取账号列表"""
    level_map = {
        "S": S_LEVEL,
        "A": A_LEVEL,
        "B": B_LEVEL,
        "C": C_LEVEL,
    }
    return level_map.get(level, [])

def get_accounts_by_group(group: str) -> list:
    """根据领域获取账号列表"""
    group_map = {
        "oil": OIL_GROUP,
        "gold": GOLD_GROUP,
        "fx": FX_GROUP,
        "geopolitics": GEOPOLITICS_GROUP,
        "journalist": JOURNALIST_SCOOP_GROUP,
        "leaders": LEADERS_GROUP,
        "crypto": CRYPTO_GROUP,
        "macro": MACRO_GROUP,
    }
    return group_map.get(group, [])

def get_all_accounts() -> list:
    """获取所有去重账号"""
    all_accounts = set()
    for level in ["S", "A", "B", "C"]:
        all_accounts.update(get_accounts_by_level(level))
    return sorted(list(all_accounts))

def get_s_level_keyword_rules() -> list:
    """获取S级关键词规则"""
    return [rule for rule in KEYWORD_RULES if rule[3] == "S"]

def get_keyword_rules_by_domain(domain: str) -> list:
    """按领域获取关键词规则"""
    return [rule for rule in KEYWORD_RULES if rule[2] == domain]

def get_crawl_interval(level: str) -> int:
    """获取抓取间隔（秒）"""
    return CRAWL_FREQUENCY.get(level, {}).get("interval_seconds", 3600)

def calculate_ai_priority(account: str, keyword_hits: list) -> str:
    """
    计算AI分析优先级
    返回: 'S' | 'A' | 'B' | None
    """
    if account in S_LEVEL:
        return "S"
    if any(rule[3] == "S" for rule in keyword_hits):
        return "S"
    if account in A_LEVEL:
        return "A"
    if any(rule[3] == "A" for rule in keyword_hits):
        return "A"
    if account in B_LEVEL and keyword_hits:
        return "B"
    return None


# ============================================================
# 8. 快速验证
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("X 实时情报抓取系统 - 账号池统计")
    print("=" * 60)
    print(f"S级账号（实时监控）: {len(S_LEVEL)} 个")
    print(f"A级账号（高频监控）: {len(A_LEVEL)} 个")
    print(f"B级账号（普通监控）: {len(B_LEVEL)} 个")
    print(f"C级账号（低频备用）: {len(C_LEVEL)} 个")
    print(f"去重后总账号数: {len(get_all_accounts())} 个")
    print("-" * 60)
    print(f"原油领域: {len(OIL_GROUP)} 个")
    print(f"黄金领域: {len(GOLD_GROUP)} 个")
    print(f"外汇领域: {len(FX_GROUP)} 个")
    print(f"地缘政治: {len(GEOPOLITICS_GROUP)} 个")
    print(f"记者爆料: {len(JOURNALIST_SCOOP_GROUP)} 个")
    print(f"国家领导人: {len(LEADERS_GROUP)} 个")
    print(f"加密货币: {len(CRYPTO_GROUP)} 个")
    print(f"全球宏观: {len(MACRO_GROUP)} 个")
    print("-" * 60)
    print(f"关键词规则对: {len(KEYWORD_RULES)} 条")
    print(f"S级关键词规则: {len(get_s_level_keyword_rules())} 条")
    print(f"单关键词告警类别: {len(SINGLE_KEYWORD_ALERTS)} 个")
    print("=" * 60)
