# -*- coding: utf-8 -*-
"""
第一级过滤规则 - 规则与特征初筛（物理除杂）

过滤维度：
1. 账号权重：蓝V认证、高互动量
2. 互动率异常：无实质互动的刷量内容、评论区高度同质化
3. 关键词矩阵：地缘实体 + 动作 + 大宗商品 组合匹配

输出：序列号命名的CSV文件
"""

import os
import re
import csv
import glob
from pathlib import Path
from datetime import datetime
from collections import Counter
from tqdm import tqdm

# ============ 配置 ============
INPUT_DIR = "./抓取的信息"
OUTPUT_DIR = "./filter_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============ 工具函数 ============

def parse_number(val):
    """解析带中文单位(万/亿)的数字"""
    val = str(val).strip().replace(",", "")
    if not val:
        return 0
    try:
        if "万" in val:
            return int(float(val.replace("万", "")) * 10000)
        if "亿" in val:
            return int(float(val.replace("亿", "")) * 100000000)
        return int(val)
    except:
        return 0


# ============ 规则1: 关键词矩阵 ============
# 组合: [地缘实体] + [动作] + [大宗商品/事件]
# 宽松策略：实体+(动作或商品)  或者 (动作+商品) 即命中

GEO_ENTITIES = [
    # 霍尔木兹海峡
    "霍尔木兹", "Hormuz", "Strait of Hormuz",
    # 伊朗
    "伊朗", "Iran", "Iranian",
    # 沙特
    "沙特", "Saudi", "KSA",
    # 俄罗斯
    "俄罗斯", "Russia", "Russian", "Putin", "莫斯科",
    # 美国
    "美国", "United States", "Washington", "Pentagon", "五角大楼",
    # 乌克兰
    "乌克兰", "Ukraine", "Ukrainian", "基辅", "Kyiv", "Kiev",
    # 以色列
    "以色列", "Israel", "Israeli", "特拉维夫", "Tel Aviv",
    # 土耳其
    "土耳其", "Turkey", "Turkish", "埃尔多安",
    # 印度
    "印度", "India", "Indian", "莫迪",
    # 中国
    "中国", "China", "Chinese", "北京", "Beijing",
    # 委内瑞拉
    "委内瑞拉", "Venezuela", "PDVSA",
    # 利比亚
    "利比亚", "Libya", "NOC",
    # 尼日利亚
    "尼日利亚", "Nigeria", "Nigerian",
    # 伊拉克
    "伊拉克", "Iraq", "Iraqi", "巴格达",
    # 也门
    "也门", "Yemen", "Houthi", "胡塞",
    # 波罗的海
    "波罗的海", "Baltic",
    # 红海
    "红海", "Red Sea",
    # 马六甲
    "马六甲", "Malacca",
    # 澳大利亚
    "澳大利亚", "Australia", "Australian",
    # 印尼
    "印尼", "Indonesia", "Indonesian",
    # 巴西
    "巴西", "Brazil", "Brazilian",
    # 加拿大
    "加拿大", "Canada", "Canadian",
    # 哈萨克斯坦
    "哈萨克斯坦", "Kazakhstan",
    # 阿曼
    "阿曼", "Oman",
    # 阿联酋
    "阿联酋", "UAE", "United Arab Emirates",
    # 厄瓜多尔
    "厄瓜多尔", "Ecuador",
    # 哥伦比亚
    "哥伦比亚", "Colombia",
]

ACTIONS = [
    # 封锁/冲突
    "封锁", "blockade", "blocked", "military",
    "军队", "army", "navy", "warship", "军舰", "航母", "aircraft carrier",
    "drone", "无人机", "UAV", "missile", "导弹", "火箭弹",
    "攻击", "attack", "attacked", "袭击", "raid", "打击",
    "冲突", "conflict", "clash", "交火", "开火",
    "制裁", "sanction", "sanctioned",
    "扣押", "seize", "seized", "扣留", "captured",
    "征用", "confiscate", "国有化", "nationalize",
    "戒严", "martial law", "emergency",
    # 石油相关动作
    "减产", "cut production", "reduce output", "output cut",
    "增产", "increase production", "ramp up", "output increase",
    "禁运", "embargo", "export ban",
    "出口", "export", "import", "进口",
    "供应", "supply", "供应链", "supply chain",
    "库存", "inventory", "stockpile", "reserve", "储备",
    "运输", "shipment", "tanker", "油轮", "vessel", "ship",
    "港口", "port", "terminal", "harbor",
    # 金融动作
    "抛售", "sell off", "dump", "抛空",
    "买入", "buy", "purchase", "抄底",
    "做空", "short", "short selling",
    "大涨", "surge", "rocket", "spike", "暴涨",
    "暴跌", "crash", "plunge", "tumble", "崩盘",
    "波动", "volatility", "volatile", "剧烈",
    # 战争/紧急
    "战争", "war", "开战", "宣战",
    "停火", "ceasefire", "停战",
    "撤退", "withdraw", "evacuate", "撤离",
    "增兵", "troops", "reinforce", "部署",
    "警戒", "alert", "warning", "警告",
    # 市场关键事件
    "涨停", "跌停", "停盘", "休市",
    "ETF", "上市", "批准", "否决",
    "罢工", "抗议", "封锁", "起义",
]

COMMODITIES = [
    # 石油
    "oil", "petroleum", "原油", "石油", "crude",
    "布伦特", "Brent", "WTI", "迪拜", "Dubai",
    "OPEC", "欧佩克",
    "汽油", "gasoline", "petrol",
    "柴油", "diesel",
    "天然气", "natural gas", "LNG", "lng",
    "液化气", "LPG",
    # 金属
    "黄金", "gold", "XAU", "金价",
    "白银", "silver", "XAG",
    "铜", "copper", "铜价",
    "锂", "lithium", "锂矿",
    "钴", "cobalt",
    "镍", "nickel",
    "铝", "aluminum", "aluminium",
    "锌", "zinc",
    "铁矿石", "iron ore", "铁矿石",
    "稀土", "rare earth", "稀土",
    # 农产品
    "小麦", "wheat",
    "玉米", "corn", "maize",
    "大豆", "soybean", "豆类",
    "咖啡", "coffee",
    "糖", "sugar",
    "棉花", "cotton",
    # 加密货币
    "bitcoin", "BTC", "以太坊", "ETH", "ethereum",
    "crypto", "加密货币", "数字货币",
    "狗狗币", "DOGE", "solana", "SOL",
    # 市场指数
    "标普", "S&P", "纳斯达克", "Nasdaq", "道琼斯", "Dow Jones",
    "恐慌指数", "VIX",
]


def keyword_matrix_match(text):
    """
    关键词矩阵匹配（宽松模式）
    策略：地缘实体 + (动作 OR 商品) → 命中
    或者：动作 + 商品（无需实体） → 命中
    """
    text_lower = text.lower()

    entities = sum(1 for kw in GEO_ENTITIES if kw.lower() in text_lower)
    actions = sum(1 for kw in ACTIONS if kw.lower() in text_lower)
    commodities = sum(1 for kw in COMMODITIES if kw.lower() in text_lower)

    # 宽松策略：实体+(动作或商品)  或者 (动作+商品)
    match = (entities >= 1 and (actions >= 1 or commodities >= 1)) or (actions >= 1 and commodities >= 1)

    return match, entities, actions, commodities


# ============ 规则2: 账号权重过滤 ============

def check_account_weight(row):
    """
    账号权重评估
    返回: (是否通过, 原因)
    """
    verified = row.get("Verified", "").strip().lower() == "true"

    likes = parse_number(row.get("Likes", 0))
    retweets = parse_number(row.get("Retweets", 0))
    comments = parse_number(row.get("Comments", 0))
    total_engagement = likes + retweets + comments

    # 蓝V认证直接放行
    if verified:
        return True, "passed_blue_v"

    # 非认证账号：互动量 > 100 才放行
    if total_engagement > 100:
        return True, "passed_high_engagement"

    # 互动量 20-100：降低权重但保留
    if total_engagement >= 20:
        return True, "passed_medium_engagement"

    # 低于20互动的非认证账号 → 过滤
    return False, "failed_low_weight"


# ============ 规则3: 互动率异常检测 ============

def check_engagement_anomaly(row):
    """
    互动率异常检测
    - 只有浏览量没有实质互动 = 刷量嫌疑
    - 评论区高度同质化
    """
    likes = parse_number(row.get("Likes", 0))
    retweets = parse_number(row.get("Retweets", 0))
    comments = parse_number(row.get("Comments", 0))
    total_engagement = likes + retweets + comments

    # 互动全为0 → 过滤（除非是蓝V）
    if total_engagement == 0:
        verified = row.get("Verified", "").strip().lower() == "true"
        if not verified:
            return False, "failed_zero_engagement"

    # 检测评论区同质化（Emojis字段分析）
    emojis = row.get("Emojis", "").strip()
    if emojis:
        try:
            emoji_list = eval(emojis) if emojis.startswith("[") else []
            if len(emoji_list) >= 3:
                counter = Counter(emoji_list)
                most_common_count = counter.most_common(1)[0][1]
                # 如果最常见的emoji出现次数占总emoji数80%以上 → 过滤
                if most_common_count / len(emoji_list) >= 0.8:
                    return False, "failed_bot_like_emojis"
        except:
            pass

    return True, "passed"


# ============ 规则4: 内容质量检测 ============

def check_content_quality(text):
    """
    内容质量检测
    - 过短内容（噪音）
    - 纯emoji/纯符号
    - 机器人生成特征
    """
    if not text or len(text.strip()) < 20:
        return False, "failed_too_short"

    # 检测纯emoji内容
    emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+')
    emoji_only = emoji_pattern.sub('', text).strip()
    if len(emoji_only) < 5 and len(text) > 5:
        return False, "failed_emoji_only"

    # 检测重复字符（机器人特征）
    if re.search(r'(.)\1{5,}', text):
        return False, "failed_repeated_chars"

    # 检测纯链接内容
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    text_without_urls = re.sub(url_pattern, '', text).strip()
    if len(text_without_urls) < 20 and len(urls) > 0:
        return False, "failed_link_only"

    return True, "passed"


# ============ 主过滤流程 ============

def process_all_csv():
    all_files = glob.glob(os.path.join(INPUT_DIR, "*.csv"))
    print(f"找到 {len(all_files)} 个CSV文件")

    passed_tweets = []
    failed_stats = {
        "keyword_matrix": 0,
        "account_weight": 0,
        "engagement_anomaly": 0,
        "content_quality": 0,
    }

    for csv_file in sorted(all_files):
        print(f"\n处理: {os.path.basename(csv_file)}")

        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    content = row.get("Content", "")

                    # 第一关：关键词矩阵
                    kw_match, entities, actions, commodities = keyword_matrix_match(content)

                    # 第二关：账号权重
                    account_pass, account_reason = check_account_weight(row)

                    # 第三关：互动率异常
                    engagement_pass, engagement_reason = check_engagement_anomaly(row)

                    # 第四关：内容质量
                    quality_pass, quality_reason = check_content_quality(content)

                    # 决策：必须同时通过所有关卡
                    if kw_match and account_pass and engagement_pass and quality_pass:
                        row["_entities"] = entities
                        row["_actions"] = actions
                        row["_commodities"] = commodities
                        row["_account_reason"] = account_reason
                        row["_source_file"] = os.path.basename(csv_file)
                        passed_tweets.append(row)
                    else:
                        if not kw_match:
                            failed_stats["keyword_matrix"] += 1
                        if not account_pass:
                            failed_stats["account_weight"] += 1
                        if not engagement_pass:
                            failed_stats["engagement_anomaly"] += 1
                        if not quality_pass:
                            failed_stats["content_quality"] += 1

        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n========== 过滤统计 ==========")
    total_input = len(passed_tweets) + sum(failed_stats.values())
    print(f"总输入: {total_input} 条")
    print(f"通过第一级过滤: {len(passed_tweets)} 条 ({100*len(passed_tweets)/max(total_input,1):.1f}%)")
    print(f"  关键词矩阵过滤: -{failed_stats['keyword_matrix']}")
    print(f"  账号权重过滤: -{failed_stats['account_weight']}")
    print(f"  互动异常过滤: -{failed_stats['engagement_anomaly']}")
    print(f"  内容质量过滤: -{failed_stats['content_quality']}")

    return passed_tweets


def save_output(tweets, batch_size=50):
    """按序列号批量输出文件"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 清理旧输出文件
    for old_file in glob.glob(os.path.join(OUTPUT_DIR, "*.csv")):
        os.remove(old_file)

    for i, tweet in enumerate(tqdm(tweets, desc="保存文件"), 1):
        batch_num = (i - 1) // batch_size + 1
        file_path = os.path.join(OUTPUT_DIR, f"filtered_batch_{batch_num:03d}.csv")

        file_exists = os.path.exists(file_path)
        with open(file_path, "a" if file_exists else "w", encoding="utf-8", newline="") as f:
            fieldnames = list(tweet.keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(tweet)

    # 打印输出文件列表
    output_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.csv")))
    print(f"\n输出 {len(output_files)} 个文件到: {OUTPUT_DIR}/")
    for f in output_files:
        count = sum(1 for _ in open(f)) - 1
        print(f"  {os.path.basename(f)}: {count} 条")

    return output_files


if __name__ == "__main__":
    tweets = process_all_csv()
    save_output(tweets)
