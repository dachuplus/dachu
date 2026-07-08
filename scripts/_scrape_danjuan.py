import json, urllib.request, datetime, sys, os

DANJUAN = "https://danjuanfunds.com/djapi/index_eva/dj"
REF = "tqhtegazxykkqfcpejky"
# 从环境变量读取 PAT（避免明文写入仓库触发 GitHub secret scanning）
PAT = os.environ.get("SUPABASE_PAT", "")
if not PAT:
    print("❌ 缺少 SUPABASE_PAT 环境变量，请先 export SUPABASE_PAT=sbpxxxx 再运行")
    sys.exit(1)
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"

def num(x):
    try:
        if x in (None, "", 0):
            return None
        return float(x)
    except Exception:
        return None

# 1) 抓取蛋卷估值
req = urllib.request.Request(DANJUAN, headers={
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://danjuanfunds.com/djmodule/value-center?channel=1300100141"
})
with urllib.request.urlopen(req, timeout=30) as r:
    raw = json.load(r)

items = (raw.get("data") or {}).get("items") or []
# 蛋卷 ttype 数字编码 → 归一化分类（与前端行业估值筛选器对应）
CAT_MAP = { '1': 'broad', '2': 'strategy', '3': 'sector' }
out = []
for it in items:
    pe = num(it.get("pe"))
    pb = num(it.get("pb"))
    pep = num(it.get("pe_percentile"))
    pbp = num(it.get("pb_percentile"))
    roe = num(it.get("roe"))
    dy = num(it.get("yeild"))
    out.append({
        "name": it.get("name"),
        "code": it.get("index_code"),
        "ttype": it.get("ttype"),
        "cat": CAT_MAP.get(str(it.get("ttype")), "other"),
        "pe": pe,
        "pe_percentile": round(pep * 100, 2) if pep is not None else None,
        "pb": pb,
        "pb_percentile": round(pbp * 100, 2) if pbp is not None else None,
        "dividend_yield": round(dy * 100, 2) if dy is not None else None,
        "roe": round(roe * 100, 2) if roe is not None else None,
        "eva_type": it.get("eva_type"),
        "date": it.get("date"),
    })

payload = {
    "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source": "danjuanfunds.com",
    "count": len(out),
    "items": out,
}
v_text = json.dumps(payload, ensure_ascii=False)

# SQL 转义
def esc(s):
    return s.replace("\\", "\\\\").replace("'", "''")

# 2) upsert 到 config 表（service role 经 Management API 绕过 RLS）
sql = (
    "INSERT INTO config (type, v, meta, tsq) VALUES ("
    f"'industry_valuation', '{esc(v_text)}', '{esc(v_text)}'::jsonb, now()) "
    "ON CONFLICT (type) DO UPDATE SET v = EXCLUDED.v, meta = EXCLUDED.meta, tsq = now()"
)

import requests
resp = requests.post(API, headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}, json={"query": sql}, timeout=120)
print("HTTP", resp.status_code)
print(resp.text[:300])
if resp.status_code >= 300:
    sys.exit(1)
print(f"OK: stored {len(out)} industry valuation rows")
