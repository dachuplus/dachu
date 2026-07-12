#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI大PK —— 规则版选基种子脚本 (Plan B)

功能：
  1. 在 Supabase 创建 ai_pk_models / ai_pk_picks 两张表（幂等 DDL）并配置 RLS 公开读。
  2. 按 7 个国内大模型各自的「规则」从 fund_scores 真实数据中各选 5 只基金，每只 20% 等权。
  3. 将模型元信息与当期选基结果写入数据库（Management API 直连，绕过 RLS 写入）。

规则映射（基于 fund_scores 真实字段，绝不使用编造基金）：
  ds(DeepSeek)   : 综合靠谱分 k_all 最高
  doubao(豆包)   : 近1年收益 r1y 最高
  qwen(千问)     : 近1年夏普 sr1y 最高（风险调整后收益）
  wenxin(文心)   : 近1年最大回撤 dd1y 最小（dd 列为负，数值越大回撤越小）
  zhipu(智谱)    : 近3年收益 r3y 最高
  kimi(Kimi)     : 近3年卡玛 r3y/|dd3y| 最优
  minimax(Minimax): 跨一级分类均衡（各一级分类内 k_all 最高，分散配置）

重要规则：
  - 同一基金的不同份额（A/C/E 等）视为同一标的，候选池先按基金名归一化去重，
    每个基金只保留一个主代码（优先 A 份额，否则取规模更大者），杜绝同基金既买 A 又买 C。
  - 选基逻辑分两层写入数据库，供前端「调仓时间线」展示：
      第一层 category_logic：该模型选择基金品类的理由（为何选某品类、为何不选另一品类）。
      第二层 picks[].reason：该模型选择这 5 只具体基金的理由（基于真实指标值，可验证）。

说明：
  - 候选池：t0 != 货币型、fund_scale > 2 亿、r1y 非空（保证收益可比）。
  - 每个模型 5 只基金，每只权重固定 20%。
  - 接入真实模型 API 后，只需替换「选基」环节（每月 1 日重跑），表结构不变。
"""
import os
import re
import sys
import json
import datetime
import requests

# ===== 凭证 =====
# PAT 为 Supabase Management API 管理密钥（特权，切勿硬编码/提交到仓库）。
# 运行时从环境变量读取：本地 `SUPABASE_PAT=xxx python3 scripts/seed_ai_pk.py`；
# CI 中由 GitHub Secrets 注入。沙箱陈旧 SUPABASE_MGMT_TOKEN 会污染，故显式覆盖。
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
if not PAT:
    raise SystemExit("缺少 SUPABASE_PAT 环境变量，请在 .env.local 或 CI Secrets 中配置后重试。")
REF = "tqhtegazxykkqfcpejky"
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
# anon/publishable key，设计上可公开，前端与只读脚本均使用，可安全提交。
ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"

os.environ["SUPABASE_MGMT_TOKEN"] = PAT
os.environ["SUPABASE_PAT"] = PAT

MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

# 每个模型的「第一层 · 品类逻辑」：说明其选品类的理由与为何排除其他品类（与 rule 一致，真实可解释）
MODELS = [
    {"id": "ds", "name": "DeepSeek", "name_short": "DS", "region": "cn",
     "color": "#1d70b8", "persona": "深度基本面派：长期业绩扎实、基金经理任职稳定、回撤可控的主动管理型基金，宁可少赚不可大亏", "rule": "k_all",
     "category_logic": "以深度基本面为核心：在全市场寻找长期业绩扎实、波动可控、基金经理任职稳定的主动管理型基金。综合评分(k_all)是其代理指标，故入选基金天然跨股票/混合多品类，不押注单一赛道，用多维质量而非单一年度爆发来控风险。"},
    {"id": "doubao", "name": "豆包", "name_short": "豆包", "region": "cn",
     "color": "#d4351c", "persona": "成长进攻派：高弹性、高成长赛道（科技/制造/医药）的基金，能承受较大波动以博取高收益", "rule": "r1y",
     "category_logic": "进攻型成长策略：聚焦高弹性、高成长赛道（科技/制造/医药/部分 QDII），主动规避低弹性的纯债与货币——它们收益弹性不足、会拉低组合进攻性。愿意用较大波动换取更高的收益弹性，故入选多为高波动高收益品类。"},
    {"id": "qwen", "name": "千问", "name_short": "千问", "region": "cn",
     "color": "#00703c", "persona": "风险平价派：波动低、夏普高、收益稳定的基金，强调风险调整后收益", "rule": "sr1y",
     "category_logic": "风险平价优先：偏好波动可控且收益稳定的品类（偏债混合、量化、中短债），规避高波动股票基金——其收益虽高但夏普被剧烈波动稀释。目标是同等风险下收益最高，用夏普比率(sr1y)衡量风险调整后的真实性价比。"},
    {"id": "wenxin", "name": "文心一言", "name_short": "文心", "region": "cn",
     "color": "#f47738", "persona": "稳健防御派：债券型、偏债混合等低回撤品种，本金安全放第一位", "rule": "dd1y",
     "category_logic": "极致防御：只选低回撤品类（短债、纯债、货币增强、偏债混合），明确规避股票型与偏股混合——这些品类在下跌市回撤可达 20%+，远超防守目标。用低回撤换下行保护，宁可少赚不能大亏。"},
    {"id": "zhipu", "name": "智谱", "name_short": "智谱", "region": "cn",
     "color": "#4c2c92", "persona": "长期价值派：穿越牛熊、中长期（3年+）收益领先的基金，不追短期热点", "rule": "r3y",
     "category_logic": "中长期价值视角：偏好能穿越牛熊的品类（偏股混合、平衡型、部分 QDII），对短期波动容忍度高。近3年收益(r3y)更能反映基金经理中长期管理能力，故不追短期热点、不配纯债，看重的是时间复利而非一时排名。"},
    {"id": "kimi", "name": "Kimi", "name_short": "Kimi", "region": "cn",
     "color": "#d53880", "persona": "性价比派：收益/回撤比（卡玛）高、涨多跌少的基金，追求风险收益性价比", "rule": "calmar3",
     "category_logic": "收益/回撤比最优：偏好高卡玛品类（二级债基、偏债混合、量化），规避单边上行的纯股基金——其回撤大、会拖累卡玛比率。要的是「涨得多、跌得少」的性价比，用近3年卡玛(r3y/|dd3y|)筛选真正的风险收益效率。"},
    {"id": "minimax", "name": "MiniMax", "name_short": "Minimax", "region": "cn",
     "color": "#28a197", "persona": "全天候均衡派：强制跨大类（股/债/QDII/指数）分散，不押注单一风格", "rule": "balanced",
     "category_logic": "强制跨一级分类均衡：在混合型/指数型/债券型/股票型/QDII 各大类各取代表基，避免风格漂移与单一风险暴露。即便某品类短期更强也不超配，确保组合在任何市况都有压舱石，用分散化解未知风险。"},
]


# 真实模型 API 配置（规则版种子仍写 mode='rule'，api_* 仅记录能力，待 ai_pk_real.py 真实跑）
_API_CONFIG = {
    "ds": {"api_provider": "deepseek", "api_model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
    "doubao": {"api_provider": "volc-ark", "api_model": "ep-20260712083200-pjvq9", "api_key_env": "ARK_API_KEY"},
    "qwen": {"api_provider": "qwen", "api_model": "qwen-plus", "api_key_env": "QWEN_API_KEY"},
}
for m in MODELS:
    cfg = _API_CONFIG.get(m["id"])
    if cfg:
        m.update(cfg)
    m["mode"] = "rule"


def mgmt_query(sql, expect_ok=(200, 201)):
    r = requests.post(MGMT_URL, headers=MGMT_HEADERS, json={"query": sql}, timeout=120)
    if r.status_code not in expect_ok:
        print(f"[MGMT ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    try:
        return r.json()
    except Exception:
        return None


def rest_select(params):
    """用 anon key 只读拉取候选池（anon 有 SELECT 权限）"""
    url = f"{SUPABASE_URL}/rest/v1/fund_scores"
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Accept": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=120)
    if r.status_code != 200:
        print(f"[REST ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    return r.json()


# ===== 份额去重 =====
# 同一基金的不同份额（A/C/E/I/B/H/R/Y/D/F）名称仅在末尾份额字母不同，视为同一标的。
# 归一化：去掉末尾单个份额字母，如「易方达蓝筹精选混合A」→「易方达蓝筹精选混合」。
# 例外：名字以 ETF/LOF/QDII 整体结尾时，尾字母是缩写一部分（如「沪深300ETF」的 F），不可削。
_SHARE_SET = set("ACEFIHBDYRF")
_ACRONYM_SUFFIXES = ("ETF", "LOF", "QDII")


def norm_name(n):
    if not n:
        return ''
    n = n.strip()
    if len(n) >= 2 and n[-1] in _SHARE_SET:
        if n.endswith(_ACRONYM_SUFFIXES):
            return n
        return n[:-1]
    return n


def dedupe_pool(pool):
    """同一基金只保留一个主代码：优先 A 份额，否则取规模更大者。"""
    groups = {}
    for f in pool:
        key = norm_name(f.get('n'))
        groups.setdefault(key, []).append(f)
    out = []
    for items in groups.values():
        if len(items) == 1:
            out.append(items[0])
            continue
        # 优先 A 份额（名称以 A 结尾）
        a_items = [x for x in items if (x.get('n') or '').rstrip().endswith('A')]
        if a_items:
            pick = max(a_items, key=lambda x: (x.get('fund_scale') or 0))
        else:
            pick = max(items, key=lambda x: (x.get('fund_scale') or 0, 0)) or items[0]
        out.append(pick)
    return out


def fetch_pool():
    params = {
        "select": "c,n,t0,t1_tt,k_all,k1,r1y,r3y,r5y,dd1y,dd3y,sr1y,fund_scale",
        "t0": "neq.货币型",
        "fund_scale": "gt.2",
        "r1y": "not.is.null",
        "order": "k_all.desc",
        "limit": "1500",
    }
    data = rest_select(params)
    print(f"[POOL] 原始候选基金数: {len(data)}")
    deduped = dedupe_pool(data)
    print(f"[POOL] 份额去重后候选基金数: {len(deduped)}（已屏蔽同基金其他份额）")
    return deduped


def fmt_val(v, pct=False, dec=2):
    if v is None:
        return '--'
    if pct:
        return f"{v:+.2f}%"
    return f"{v:.{dec}f}"


def make_reason(rule, f):
    """第二层逻辑：基于真实指标值生成「为何选这只而非其他」的理由（可验证，不编造）。"""
    if rule == 'k_all':
        return f"综合评分 k_all={fmt_val(f.get('k_all'))} 在候选池中综合质地最高（收益/回撤/夏普三维均衡最优），故入选。"
    if rule == 'r1y':
        return f"近1年收益 r1y={fmt_val(f.get('r1y'), pct=True)} 在候选池中最高，进攻弹性最强，故入选。"
    if rule == 'sr1y':
        return f"近1年夏普 sr1y={fmt_val(f.get('sr1y'), dec=3)} 在候选池中最高，风险调整后收益最优，故入选。"
    if rule == 'dd1y':
        return f"近1年最大回撤 dd1y={fmt_val(f.get('dd1y'), pct=True)} 在候选池中最小（回撤越小越好），下行保护最强，故入选。"
    if rule == 'r3y':
        return f"近3年收益 r3y={fmt_val(f.get('r3y'), pct=True)} 在候选池中最高，中长期穿越牛熊能力最强，故入选。"
    if rule == 'calmar3':
        r3, dd3 = f.get('r3y'), f.get('dd3y')
        cal = (r3 / abs(dd3)) if (r3 is not None and dd3) else None
        return f"近3年卡玛比率={fmt_val(cal, dec=3)} 在候选池中最高（收益/回撤比最优），故入选。"
    if rule == 'balanced':
        cat = f.get('t1_tt') or f.get('t0') or ''
        return f"为「{cat}」品类代表，k_all={fmt_val(f.get('k_all'))} 为该一级分类（{f.get('t0')}）内最高，实现跨品类均衡配置。"
    return "按本模型规则入选。"


def pick_top(pool, key, topn=5, reverse=True, require_notnull=True):
    items = [f for f in pool if not require_notnull or f.get(key) is not None]
    items.sort(key=lambda f: (f.get(key) is None, f.get(key) if f.get(key) is not None else 0),
               reverse=reverse)
    return items[:topn]


def build_picks(pool):
    picks_by_model = {}

    # 1. DS: k_all 最高
    picks_by_model["ds"] = [f for f in pick_top(pool, "k_all")]

    # 2. 豆包: r1y 最高
    picks_by_model["doubao"] = [f for f in pick_top(pool, "r1y")]

    # 3. 千问: sr1y 最高
    picks_by_model["qwen"] = [f for f in pick_top(pool, "sr1y")]

    # 4. 文心: dd1y 最小(列为负，数值越大回撤越小)
    picks_by_model["wenxin"] = [f for f in pick_top(pool, "dd1y")]

    # 5. 智谱: r3y 最高
    picks_by_model["zhipu"] = [f for f in pick_top(pool, "r3y")]

    # 6. Kimi: 近3年卡玛 r3y/|dd3y| 最优
    calmar_pool = []
    for f in pool:
        r3 = f.get("r3y")
        dd3 = f.get("dd3y")
        if r3 is None or dd3 is None or dd3 == 0:
            continue
        calmar_pool.append((f, r3 / abs(dd3)))
    calmar_pool.sort(key=lambda x: x[1], reverse=True)
    picks_by_model["kimi"] = [f for f, _ in calmar_pool[:5]]

    # 7. Minimax: 跨一级分类均衡
    priority = ["混合型", "指数型", "债券型", "股票型", "QDII"]
    by_cat = {c: [] for c in priority}
    for f in pool:
        t0 = f.get("t0")
        if t0 in by_cat:
            by_cat[t0].append(f)
    for c in by_cat:
        by_cat[c].sort(key=lambda f: (f.get("k_all") is None, f.get("k_all") or 0), reverse=True)
    balanced = []
    chosen = set()
    for c in priority:
        if by_cat[c]:
            f = by_cat[c][0]
            balanced.append(f)
            chosen.add(f["c"])
    # 若不足 5 类，按 k_all 补满
    if len(balanced) < 5:
        extra = [f for f in pool if f["c"] not in chosen]
        extra.sort(key=lambda f: (f.get("k_all") is None, f.get("k_all") or 0), reverse=True)
        for f in extra:
            if len(balanced) >= 5:
                break
            if f["c"] not in chosen:
                balanced.append(f)
                chosen.add(f["c"])
    picks_by_model["minimax"] = balanced

    # 格式化为 5 只 / 20% 权重，去重 + 生成两层逻辑 reason
    result = {}
    for m in MODELS:
        mid = m["id"]
        raw = picks_by_model.get(mid, [])
        out = []
        seen = set()
        for f in raw:
            code = f.get("c")
            if not code or code in seen:
                continue
            seen.add(code)
            out.append({
                "code": code,
                "name": f.get("n") or code,
                "weight": 20,
                "reason": make_reason(m["rule"], f),
            })
            if len(out) >= 5:
                break
        result[mid] = out
    return result


def create_tables():
    print("[DDL] 创建表 ai_pk_models / ai_pk_picks ...")
    ddl = """
CREATE TABLE IF NOT EXISTS public.ai_pk_models (
  id text PRIMARY KEY,
  name text NOT NULL,
  name_short text,
  region text NOT NULL DEFAULT 'cn',
  color text NOT NULL,
  persona text,
  category_logic text,
  mode text NOT NULL DEFAULT 'rule',
  api_provider text,
  api_model text,
  api_key_env text,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.ai_pk_picks (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_id text NOT NULL REFERENCES public.ai_pk_models(id),
  period_month text NOT NULL,
  picks jsonb NOT NULL,
  mode text NOT NULL DEFAULT 'rule',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_pk_picks_model_period
  ON public.ai_pk_picks(model_id, period_month);

ALTER TABLE public.ai_pk_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_pk_picks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ai_pk_models_public_read" ON public.ai_pk_models;
CREATE POLICY "ai_pk_models_public_read" ON public.ai_pk_models FOR SELECT USING (true);

DROP POLICY IF EXISTS "ai_pk_picks_public_read" ON public.ai_pk_picks;
CREATE POLICY "ai_pk_picks_public_read" ON public.ai_pk_picks FOR SELECT USING (true);
"""
    mgmt_query(ddl)
    # 旧表兜底补列
    for col, typ in [
        ("category_logic", "text"),
        ("mode", "text NOT NULL DEFAULT 'rule'"),
        ("api_provider", "text"),
        ("api_model", "text"),
        ("api_key_env", "text"),
    ]:
        mgmt_query(f"ALTER TABLE public.ai_pk_models ADD COLUMN IF NOT EXISTS {col} {typ};")
    mgmt_query("ALTER TABLE public.ai_pk_picks ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'rule';")
    print("[DDL] 完成")


def upsert_models():
    print("[SEED] 写入模型元信息 ...")
    vals = []
    for m in MODELS:
        persona = m["persona"].replace("'", "''")
        clogic = m["category_logic"].replace("'", "''")
        provider = m.get("api_provider") or ""
        apimodel = m.get("api_model") or ""
        keyenv = m.get("api_key_env") or ""
        mode = m.get("mode") or "rule"
        vals.append(
            f"('{m['id']}','{m['name']}','{m['name_short']}','{m['region']}','{m['color']}',"
            f"'{persona}','{clogic}','{mode}','{provider}','{apimodel}','{keyenv}',true)"
        )
    sql = (
        "INSERT INTO public.ai_pk_models "
        "(id,name,name_short,region,color,persona,category_logic,mode,api_provider,api_model,api_key_env,enabled) VALUES "
        + ",".join(vals)
        + " ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, name_short=EXCLUDED.name_short, "
          "region=EXCLUDED.region, color=EXCLUDED.color, persona=EXCLUDED.persona, "
          "category_logic=EXCLUDED.category_logic, mode=EXCLUDED.mode, "
          "api_provider=EXCLUDED.api_provider, api_model=EXCLUDED.api_model, "
          "api_key_env=EXCLUDED.api_key_env, enabled=EXCLUDED.enabled;"
    )
    mgmt_query(sql)
    print("[SEED] 模型元信息完成")


def upsert_picks(picks_by_model, period_month, mode="rule"):
    print(f"[SEED] 写入当期({period_month})选基结果 [mode={mode}] ...")
    for m in MODELS:
        mid = m["id"]
        funds = picks_by_model.get(mid, [])
        if len(funds) < 5:
            print(f"  [WARN] {mid} 仅选到 {len(funds)} 只，跳过")
            continue
        picks_json = json.dumps(funds, ensure_ascii=False).replace("'", "''")
        # 先删后插，保证重跑幂等
        mgmt_query(
            f"DELETE FROM public.ai_pk_picks WHERE model_id='{mid}' AND period_month='{period_month}';"
        )
        mgmt_query(
            f"INSERT INTO public.ai_pk_picks (model_id, period_month, picks, mode) "
            f"VALUES ('{mid}','{period_month}','{picks_json}','{mode}');"
        )
        names = "、".join(f["name"] for f in funds)
        print(f"  {mid}({m['name_short']}): {names}")
    print("[SEED] 选基结果完成")


def main():
    period_month = datetime.date.today().strftime("%Y-%m")
    print(f"=== AI大PK 规则版种子 (期次 {period_month}) ===")
    create_tables()
    pool = fetch_pool()
    if not pool:
        print("[ERR] 候选池为空，无法选基")
        sys.exit(1)
    picks_by_model = build_picks(pool)
    # 打印预览
    for m in MODELS:
        funds = picks_by_model.get(m["id"], [])
        print(f"\n[{m['id']}] {m['name']} — {m['persona']}")
        print(f"  [品类逻辑] {m['category_logic']}")
        for i, f in enumerate(funds, 1):
            print(f"   {i}. {f['code']} {f['name']} (20%)")
            print(f"      └ {f['reason']}")
    upsert_models()
    upsert_picks(picks_by_model, period_month, mode="rule")
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
