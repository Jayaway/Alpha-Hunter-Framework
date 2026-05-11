# DeepAlpha Project Structure

```text
deepalpha/              核心业务代码与 CLI 实现
deepalpha_runtime/      定时监听、事件 pipeline 等运行编排
scraper/                X/Twitter Selenium 抓取器
tests/                  测试脚本
examples/               示例脚本和快速上手材料
docs/                   架构、数据流、审计和说明文档
web/                    DeepAlpha 静态网页版原型
notebooks/              Notebook
reports/                JSON / Markdown 报告输出
graph_data/             关系图谱和账号运行状态
cookies/                账号与浏览器 Cookie 配置
cookies/browser/        浏览器导出的 X Cookie
obsidian_vault/         Obsidian 图谱输出
test_obsidian_vault/    Obsidian 测试数据
抓取的信息/             抓取 CSV 历史数据
logs/                   运行日志
```

根目录只保留常用兼容入口：

```text
run_v2.py
run.py
main_v2.py
report_formatter.py
graph_viewer.py
test_v2.py
```

旧命令仍可使用，例如：

```bash
python3 run_v2.py "油价会涨吗？"
python3 report_formatter.py reports/test.json
python3 test_v2.py
```

也可以使用包入口：

```bash
python3 -m deepalpha.run_v2 "油价会涨吗？"
```
