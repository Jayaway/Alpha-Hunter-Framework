import pandas as pd

df = pd.read_csv("./抓取的信息/2026-04-20_18-07-55_tweets_1-100.csv")
print(f"总推文数: {len(df)}")
print(f"总博主数: {df['Handle'].nunique()}")
print("\n各博主出现次数:")
print(df['Handle'].value_counts().head(20))