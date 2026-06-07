#!/usr/bin/env python3
"""
探索天天基金 fund.eastmoney.com/data 目录下的所有 API 接口
"""
import urllib.request
import json
import re
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://fund.eastmoney.com/data/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

def fetch(url, encoding='utf-8'):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            return data.decode(encoding, errors='replace')
    except Exception as e:
        return f"ERROR: {e}"

def parse_rankhandler_item(item_str):
    """解析 rankhandler.aspx 返回的单个基金数据"""
    # 格式: "code,name,pinyin,date,nav,acc_nav,r0d,r1w,..."
    fields = item_str.split(',')
    return fields

print("=" * 60)
print("探索天天基金 data 目录下 API 接口")
print("=" * 60)

# 1. rankhandler.aspx - 基金排行（已知）
print("\n【1】rankhandler.aspx - 基金排行榜")
print("  URL: https://fund.eastmoney.com/data/rankhandler.aspx")
print("  参数: op=ph&dt=kf&ft=all&sc=1y&st=desc&pi=1&pn=20")
print("  说明: 最常用的基金数据接口，返回 JSONP 格式")
url1 = "https://fund.eastmoney.com/data/rankhandler.aspx?op=ph&dt=kf&ft=all&sc=1y&st=desc&pi=1&pn=3"
r1 = fetch(url1)
if not r1.startswith("ERROR"):
    # 提取 datas 部分
    m = re.search(r'datas:\[(.*?)\]', r1, re.DOTALL)
    if m:
        datas = m.group(1)
        # 取第一个基金的数据
        items = re.findall(r'\"([^\"]+)\"', datas)
        if items:
            fields = parse_rankhandler_item(items[0])
            print(f"  字段数: {len(fields)}")
            LABELS = ['code','name','pinyin','date','nav','acc_nav',
                       'r0d','r1w','r1m','r3m','r6m','r1y','r2y','r3y','r5y','return_all',
                       'found_date','flag1','return_all_raw','buy_fee','manage_fee',
                       'flag2_dingtou','manage_fee2','flag3_shengou','ytd']
            for i, f in enumerate(fields[:min(len(fields), len(LABELS))]):
                print(f"    [{i:2d}] {LABELS[i]:25s} = {f}")
            print(f"  ... 共 {len(fields)} 个字段")
print(f"  响应长度: {len(r1)} 字节")

# 2. fundrating.aspx - 基金评级
print("\n【2】fundrating.aspx - 基金评级")
url2 = "https://fund.eastmoney.com/data/fundrating.aspx?dt=1&pi=1&pn=5"
r2 = fetch(url2)
print(f"  响应长度: {len(r2)} 字节")
print(f"  前200字: {r2[:200]}")

# 3. jcxx_zhishu.aspx - 基础信息/指数
print("\n【3】jcxx_zhishu.aspx - 基础信息")
url3 = "https://fund.eastmoney.com/data/jcxx_zhishu.aspx?dt=kf&ft=all&pi=1&pn=3"
r3 = fetch(url3)
print(f"  响应长度: {len(r3)} 字节")
print(f"  前200字: {r3[:200]}")

# 4. fundfenhong.aspx - 基金分红
print("\n【4】fundfenhong.aspx - 基金分红")
url4 = "https://fund.eastmoney.com/data/fundfenhong.aspx?pi=1&pn=5"
r4 = fetch(url4)
print(f"  响应长度: {len(r4)} 字节")
print(f"  前200字: {r4[:200]}")

# 5. FundDataSource_jzxx.aspx - 净值信息
print("\n【5】FundDataSource_jzxx.aspx - 净值信息")
url5 = "https://fund.eastmoney.com/data/FundDataSource_jzxx.aspx?op=ph&dt=kf&ft=all&pi=1&pn=3"
r5 = fetch(url5)
print(f"  响应长度: {len(r5)} 字节")
print(f"  前200字: {r5[:200]}")

# 6. 尝试获取 fund.eastmoney.com/data/ 目录页所有链接
print("\n【6】扫描 data 目录页所有 API 链接")
r6 = fetch("https://fund.eastmoney.com/data/")
links = re.findall(r'(?:href|src)=["\'](.*?\.aspx[^"\']*)["\']', r6)
links = list(set(links))
print(f"  找到 {len(links)} 个 .aspx 链接:")
for link in sorted(links)[:20]:
    print(f"    {link}")

# 7. 定投排行
print("\n【7】dingtou 定投排行 API")
url7 = "https://fund.eastmoney.com/data/rankhandler.aspx?op=dt&dt=kf&ft=all&sc=1y&st=desc&pi=1&pn=3"
r7 = fetch(url7)
print(f"  响应长度: {len(r7)} 字节")
print(f"  前200字: {r7[:200]}")

# 8. 基金公司数据
print("\n【8】基金公司数据 API")
url8 = "https://fund.eastmoney.com/data/companyranking.aspx?pi=1&pn=5"
r8 = fetch(url8)
print(f"  响应长度: {len(r8)} 字节")
print(f"  前200字: {r8[:200]}")

print("\n" + "=" * 60)
print("探索完成")
print("=" * 60)
