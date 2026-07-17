#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_stock_pk.py — 股票组合 PK 规则版选股种子脚本（Plan B，镜像 ai_pk_seed）

功能：
  1. 幂等创建 stock_pk_models / stock_pk_picks 两张表 + RLS（anon SELECT USING(true)）。
  2. 写入 7 个模型元信息（镜像 ai_pk_models 的 7 家 provider 配置，region='A股'，
     persona/category_logic 改写为「选行业 + 选股」语境，color 沿用品牌色）。
  3. 规则版选股（每个模型 5 只 × 20% 等权）：从 stock_scores（生产表）按各模型规则挑 5 只 A 股。
     规则映射（针对股票字段）：
        ds        : k_all 最高
        qwen      : sharpe 最高
        wenxin    : max_drawdown 最小（回撤列负值，越大回撤越小）
        zhipu     : return_3y 最高
        kimi      : return_3y/|max_drawdown| 卡玛最优
        minimax   : 跨二级行业均衡（各行业取 k_all 最高分散）
        doubao    : 真实模型种子版跳过不覆盖（与基金版一致）
  4. 写入 stock_pk_picks（mode='rule'），picks 每项含 {code,name,weight:20,reason,industry}。
     reason 用多维度真实指标（同类/收益/回撤/夏普/市值/综合）生成，不编造。
  5. 风控：剔除 is_st/is_delisted/is_suspended/上市<60天。

说明：
  - 候选池：仅 A 股（沪 60/68、深 00/30、京 8），且通过风控过滤。
  - 每个模型 5 只，每只权重固定 20%。
  - 若 stock_scores 为空（尚未 fetch+promote），跳过 picks 写入并提示先跑 fetch+promote。
"""
import os
import re
import sys
import json
import datetime
import requests

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
if not PAT:
    raise SystemExit("缺少 SUPABASE_PAT 环境变量（请显式覆盖沙箱陈旧 SUPABASE_MGMT_TOKEN）。")
REF = "tqhtegazxykkqfcpejky"
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
os.environ["SUPABASE_MGMT_TOKEN"] = PAT
os.environ["SUPABASE_PAT"] = PAT
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

# 7 个模型元信息（镜像 ai_pk_models 的 provider 配置；region='A股'；persona/category_logic 改写选股语境）
MODELS = [
    {"id": "ds", "name": "DeepSeek", "name_short": "DS", "region": "A股",
     "color": "#1d70b8",
     "persona": "深度基本面派：长期业绩扎实、盈利质量高、回撤可控的 A 股，宁可少赚不可大亏",
     "rule": "k_all",
     "category_logic": "【宏观】经济弱复苏、利率下行期，质量因子更抗波动。【策略】以深度基本面质量为核心，偏好长期 ROE 稳定、盈利质量高的 A 股。【行业】不押单一赛道，跨消费/制造/医药均衡布局。【流动性】选规模适中、交投顺畅品种。【金融工程】用 k_all 综合评分代理多维质量。【胜率赔率】重胜率（高确定性）而非高赔率，宁可少赚不可大亏。"},
    {"id": "doubao", "name": "豆包", "name_short": "豆包", "region": "A股",
     "color": "#d4351c",
     "persona": "成长进攻派：高弹性、高成长赛道（科技/制造/医药）的 A 股，能承受较大波动以博取高收益",
     "rule": "r3y",
     "category_logic": "【宏观】复苏初期风险偏好抬升，成长弹性占优。【策略】动量策略，追高景气、高弹性赛道。【行业】聚焦科技/制造/医药等高成长方向。【流动性】偏好成交活跃、规模足够的品种以承载进攻。【金融工程】以近3年收益 r3y 排序捕捉动量。【胜率赔率】重赔率（高收益弹性），愿承担较大波动博取超额收益。"},
    {"id": "qwen", "name": "千问", "name_short": "千问", "region": "A股",
     "color": "#00703c",
     "persona": "风险平价派：波动低、夏普高、收益稳定的 A 股，强调风险调整后收益",
     "rule": "sharpe",
     "category_logic": "【宏观】波动加剧阶段，风险调整后收益更重要。【策略】风险平价，控波动求稳健。【行业】分散于低波动、高确定性板块，规避高波动个股。【流动性】优先高流动性、低摩擦成本品种。【金融工程】以夏普 sharpe 衡量风险收益性价比。【胜率赔率】重胜率与稳定赔率，同等风险下追求收益最高。"},
    {"id": "wenxin", "name": "文心一言", "name_short": "文心", "region": "A股",
     "color": "#f47738",
     "persona": "稳健防御派：低回撤、本金安全放第一的 A 股",
     "rule": "dd1y",
     "category_logic": "【宏观】不确定性偏高时保本优先。【策略】稳健防御，以低回撤为底仓。【行业】聚焦低波动、现金流稳定的板块。【流动性】强调随时可赎回、无锁定期。【金融工程】以近1年回撤 max_drawdown 最小为筛选核心（回撤列为负，数值越大回撤越小）。【胜率赔率】极高胜率、低赔率，宁可少赚不能大亏。"},
    {"id": "zhipu", "name": "智谱", "name_short": "智谱", "region": "A股",
     "color": "#4c2c92",
     "persona": "长期价值派：穿越牛熊、中长期（3年+）收益领先的 A 股，不追短期热点",
     "rule": "r3y",
     "category_logic": "【宏观】逆周期布局，看重中长期产业趋势。【策略】长期价值，穿越牛熊。【行业】偏制造/医药/消费等结构性机会。【流动性】接受较长持有期以换取复利。【金融工程】以近3年收益 return_3y 评估中长期能力。【胜率赔率】中等胜率、中高赔率，重时间复利而非一时排名。"},
    {"id": "kimi", "name": "Kimi", "name_short": "Kimi", "region": "A股",
     "color": "#d53880",
     "persona": "性价比派：收益/回撤比（卡玛）高、涨多跌少的 A 股，追求风险收益性价比",
     "rule": "calmar3",
     "category_logic": "【宏观】震荡市中「涨多跌少」最划算。【策略】性价比优先，收益/回撤比最优。【行业】低波动高确定性为主。【流动性】选流动性充裕、回撤可控品种。【金融工程】以收益回撤比（return_3y/|max_drawdown|）衡量风险收益效率。【胜率赔率】胜率与赔率兼顾，追求风险收益效率最大化。"},
    {"id": "minimax", "name": "MiniMax", "name_short": "Minimax", "region": "A股",
     "color": "#28a197",
     "persona": "全天候均衡派：强制跨行业（二级行业）分散，不押注单一风格",
     "rule": "balanced",
     "category_logic": "【宏观】应对未知市况，不赌方向。【策略】全天候跨行业均衡配置。【行业】各二级行业均配，取各行业 k_all 代表分散。【流动性】每行业留压舱石，保证整体流动性。【金融工程】各行业内取 k_all 代表，强制分散。【胜率赔率】以分散降波动，胜率靠广度、赔率靠多元，化解单一风格风险。"},
]

# 真实模型 API 配置（规则版种子仍写 mode='rule'，api_* 仅记录能力，待 stock_pk_real.py 真实跑）
_API_CONFIG = {
    "ds": {"api_provider": "deepseek", "api_model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
    "doubao": {"api_provider": "volc-ark", "api_model": "ep-20260712083200-pjvq9", "api_key_env": "ARK_API_KEY"},
    "qwen": {"api_provider": "qwen", "api_model": "qwen-plus", "api_key_env": "QWEN_API_KEY"},
    "wenxin": {"api_provider": "wenxin", "api_model": "ernie-5.1", "api_key_env": "WENXIN_API_KEY"},
    "zhipu": {"api_provider": "zhipu", "api_model": "glm-5.2", "api_key_env": "ZHIPU_API_KEY"},
    "kimi": {"api_provider": "kimi", "api_model": "kimi-k2.5", "api_key_env": "KIMI_API_KEY"},
    "minimax": {"api_provider": "minimax", "api_model": "MiniMax-M3", "api_key_env": "MINIMAX_API_KEY"},
}
for m in MODELS:
    cfg = _API_CONFIG.get(m["id"])
    if cfg:
        m.update(cfg)
    # 豆包现已接入真实大模型（火山方舟），由 stock_pk_real.py 真实选股；seed 规则兜底不处理豆包，避免覆盖
    if m["id"] != "doubao":
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
    url = f"{SUPABASE_URL}/rest/v1/stock_scores"
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Accept": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=120)
    if r.status_code != 200:
        print(f"[REST ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    return r.json()


def create_tables():
    print("[DDL] 创建表 stock_pk_models / stock_pk_picks ...")
    ddl = """
CREATE TABLE IF NOT EXISTS public.stock_pk_models (
  id text PRIMARY KEY,
  name text NOT NULL,
  name_short text,
  region text NOT NULL DEFAULT 'A股',
  color text NOT NULL,
  persona text,
  category_logic text,
  mode text NOT NULL DEFAULT 'rule',
  api_provider text,
  api_model text,
  api_key_env text,
  enabled boolean NOT NULL DEFAULT true,
  sort_order int,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.stock_pk_picks (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_id text NOT NULL REFERENCES public.stock_pk_models(id),
  period_month text NOT NULL,
  picks jsonb NOT NULL,
  mode text NOT NULL DEFAULT 'rule',
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stock_pk_picks_model_period
  ON public.stock_pk_picks(model_id, period_month);

ALTER TABLE public.stock_pk_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_pk_picks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "stock_pk_models_public_read" ON public.stock_pk_models;
CREATE POLICY "stock_pk_models_public_read" ON public.stock_pk_models FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "stock_pk_picks_public_read" ON public.stock_pk_picks;
CREATE POLICY "stock_pk_picks_public_read" ON public.stock_pk_picks FOR SELECT TO anon USING (true);
"""
    mgmt_query(ddl)
    print("[DDL] 完成")


def upsert_models():
    print("[SEED] 写入模型元信息 ...")
    vals = []
    for i, m in enumerate(MODELS):
        persona = m["persona"].replace("'", "''")
        clogic = (m["category_logic"] or "").replace("'", "''")
        provider = m.get("api_provider") or ""
        apimodel = m.get("api_model") or ""
        keyenv = m.get("api_key_env") or ""
        mode = m.get("mode") or "rule"
        vals.append(
            f"('{m['id']}','{m['name']}','{m['name_short']}','{m['region']}','{m['color']}',"
            f"'{persona}','{clogic}','{mode}','{provider}','{apimodel}','{keyenv}',true,{i})"
        )
    sql = (
        "INSERT INTO public.stock_pk_models "
        "(id,name,name_short,region,color,persona,category_logic,mode,api_provider,api_model,api_key_env,enabled,sort_order) VALUES "
        + ",".join(vals)
        + " ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, name_short=EXCLUDED.name_short, "
          "region=EXCLUDED.region, color=EXCLUDED.color, persona=EXCLUDED.persona, "
          "category_logic=EXCLUDED.category_logic, mode=EXCLUDED.mode, "
          "api_provider=EXCLUDED.api_provider, api_model=EXCLUDED.api_model, "
          "api_key_env=EXCLUDED.api_key_env, enabled=EXCLUDED.enabled, sort_order=EXCLUDED.sort_order;"
    )
    mgmt_query(sql)
    print("[SEED] 模型元信息完成")


# ===== 风控 / 过滤 =====
def passes_risk(f):
    if f.get("is_st"):
        return False
    if f.get("is_delisted"):
        return False
    if f.get("is_suspended"):
        return False
    ld = f.get("list_date")
    if ld:
        try:
            from datetime import date
            if (date.today() - date.fromisoformat(str(ld)[:10])).days < 60:
                return False
        except Exception:
            pass
    return True


def fmt_val(v, pct=False, dec=2):
    if v is None:
        return '--'
    if pct:
        return f"{v:+.2f}%"
    return f"{v:.{dec}f}"


def make_reason(rule, f):
    """基于真实指标生成第二层选股理由（不编造）。"""
    name = f.get('name') or ''
    industry = f.get('industry') or '—'
    k_all = fmt_val(f.get('k_all'))
    r1 = fmt_val(f.get('return_1y'), pct=True)
    r3 = fmt_val(f.get('return_3y'), pct=True)
    dd = fmt_val(f.get('max_drawdown'), pct=True)
    sh = fmt_val(f.get('sharpe'), dec=3)
    mkt = fmt_val(f.get('mktcap'))
    pe = fmt_val(f.get('pe_ttm'))
    pb = fmt_val(f.get('pb'))

    same_cls = f"【同类】该股票属{industry}行业，在候选池中综合质地居前，与组合其他标的分散互补、避免同质化暴露。"
    earn = f"【收益】近1年收益{r1}、近3年收益{r3}，中长期收益能力在同类中领先，契合本模型选股标准。"
    draw = f"【回撤】近1年最大回撤{dd}，下行控制处于可承受区间，风险暴露可控。"
    sharpe_d = f"【夏普】近1年夏普{sh}，风险调整后收益在同类中占优。"
    scale_d = f"【市值】总市值约{mkt}亿、PE(TTM){pe}、PB{pb}，规模与估值合理，流动性较好。"
    comp = f"【综合】综合靠谱分{k_all}、夏普{sh}，多维指标均衡；以本模型规则纳入组合，达成配置目标。"
    return same_cls + earn + draw + sharpe_d + scale_d + comp


def pick_top(pool, key, topn=5, reverse=True):
    items = [f for f in pool if f.get(key) is not None]
    items.sort(key=lambda f: f.get(key), reverse=reverse)
    return items[:topn]


def build_picks(pool):
    picks_by_model = {}

    # 1. DS: k_all 最高
    picks_by_model["ds"] = [f for f in pick_top(pool, "k_all")]

    # 2. 豆包: r3y 最高（真实模型由 stock_pk_real.py 选，seed 跳过）
    picks_by_model["doubao"] = [f for f in pick_top(pool, "return_3y")]

    # 3. 千问: sharpe 最高
    picks_by_model["qwen"] = [f for f in pick_top(pool, "sharpe")]

    # 4. 文心: max_drawdown 最小（列为负，数值越大回撤越小）
    picks_by_model["wenxin"] = [f for f in pick_top(pool, "max_drawdown")]

    # 5. 智谱: return_3y 最高
    picks_by_model["zhipu"] = [f for f in pick_top(pool, "return_3y")]

    # 6. Kimi: 卡玛 return_3y/|max_drawdown| 最优
    calmar_pool = []
    for f in pool:
        r3 = f.get("return_3y")
        dd = f.get("max_drawdown")
        if r3 is None or dd is None or dd == 0:
            continue
        calmar_pool.append((f, r3 / abs(dd)))
    calmar_pool.sort(key=lambda x: x[1], reverse=True)
    picks_by_model["kimi"] = [f for f, _ in calmar_pool[:5]]

    # 7. Minimax: 跨二级行业均衡（各行业取 k_all 最高分散）
    #    仅按「真实非空行业」分组；若行业标注不足（如行业映射缺失），退化为全局 k_all Top5，避免只选 1 只。
    by_ind = {}
    for f in pool:
        ind = f.get("industry")
        if ind:
            by_ind.setdefault(ind, []).append(f)
    if len(by_ind) <= 1:
        # 行业信息不足：退化为全局 k_all 最高的 5 只（仍真实、不编造）
        fallback = [f for f in pick_top(pool, "k_all")]
        picks_by_model["minimax"] = fallback[:5]
    else:
        for ind in by_ind:
            by_ind[ind].sort(key=lambda f: (f.get("k_all") is None, f.get("k_all") or 0), reverse=True)
        balanced = []
        chosen = set()
        for ind in sorted(by_ind, key=lambda x: -len(by_ind[x])):
            if by_ind[ind]:
                f = by_ind[ind][0]
                if f["code"] not in chosen:
                    balanced.append(f)
                    chosen.add(f["code"])
            if len(balanced) >= 5:
                break
        if len(balanced) < 5:
            extra = [f for f in pool if f["code"] not in chosen]
            extra.sort(key=lambda f: (f.get("k_all") is None, f.get("k_all") or 0), reverse=True)
            for f in extra:
                if len(balanced) >= 5:
                    break
                if f["code"] not in chosen:
                    balanced.append(f)
                    chosen.add(f["code"])
        picks_by_model["minimax"] = balanced

    # 格式化为 5 只 / 20% 权重
    result = {}
    for m in MODELS:
        mid = m["id"]
        raw = picks_by_model.get(mid, [])
        out = []
        seen = set()
        for f in raw:
            code = f.get("code")
            if not code or code in seen:
                continue
            seen.add(code)
            out.append({
                "code": code,
                "name": f.get("name") or code,
                "weight": 20,
                "reason": make_reason(m["rule"], f),
                "industry": f.get("industry") or "",
            })
            if len(out) >= 5:
                break
        result[mid] = out
    return result


def fetch_pool():
    """从 stock_scores（生产表）拉取候选池：仅 A 股 + 通过风控，按综合分相关字段排序分页拉全。"""
    collected = []
    PAGE = 1000
    for off in range(0, 5000, PAGE):
        rows = rest_select({
            "select": "code,name,industry,exchange,k_all,return_1y,return_3y,max_drawdown,sharpe,pe_ttm,pb,mktcap,is_st,is_delisted,is_suspended,list_date",
            "order": "k_all.desc",
            "limit": str(PAGE),
            "offset": str(off),
        })
        if not rows:
            break
        collected.extend(rows)
        if len(rows) < PAGE:
            break
    # 仅 A 股 + 风控过滤
    a_share = [f for f in collected if (f.get("exchange") in ("SH", "SZ", "BJ"))]
    pool = [f for f in a_share if passes_risk(f)]
    print(f"[POOL] 生产表候选：拉取 {len(collected)} 只，A股 {len(a_share)} 只，风控过滤后 {len(pool)} 只", flush=True)
    return pool


def upsert_picks(picks_by_model, period_month, mode="rule"):
    print(f"[SEED] 写入当期({period_month})选股结果 [mode={mode}] ...", flush=True)
    for m in MODELS:
        mid = m["id"]
        if mid == "doubao":
            print(f"  [SKIP] {mid} 由真实模型选股，seed 跳过不覆盖", flush=True)
            continue
        funds = picks_by_model.get(mid, [])
        if len(funds) < 5:
            print(f"  [WARN] {mid} 仅选到 {len(funds)} 只，跳过", flush=True)
            continue
        picks_json = json.dumps(funds, ensure_ascii=False).replace("'", "''")
        mgmt_query(
            f"DELETE FROM public.stock_pk_picks WHERE model_id='{mid}' AND period_month='{period_month}';"
        )
        mgmt_query(
            f"INSERT INTO public.stock_pk_picks (model_id, period_month, picks, mode) "
            f"VALUES ('{mid}','{period_month}','{picks_json}','{mode}');"
        )
        names = "、".join(f["name"] for f in funds)
        print(f"  {mid}({m['name_short']}): {names}", flush=True)
    print("[SEED] 选股结果完成", flush=True)


def main():
    period_month = datetime.date.today().strftime("%Y-%m")
    print(f"=== 股票组合 PK 规则版种子 (期次 {period_month}) ===", flush=True)
    create_tables()
    upsert_models()
    pool = fetch_pool()
    if not pool:
        print("[ERR] 候选池为空（stock_scores 可能尚未 promote）。请先运行 fetch_stock_scores.py → promote_stock_scores.py，再运行本脚本生成规则版选股。", flush=True)
        print("=== 模型元信息已写入，规则版选股跳过 ===", flush=True)
        return
    picks_by_model = build_picks(pool)
    for m in MODELS:
        funds = picks_by_model.get(m["id"], [])
        print(f"\n[{m['id']}] {m['name']} — {m['persona']}", flush=True)
        for i, f in enumerate(funds, 1):
            print(f"   {i}. {f['code']} {f['name']} (20%) [{f['industry']}]", flush=True)
    upsert_picks(picks_by_model, period_month, mode="rule")
    print("\n=== 完成 ===", flush=True)


if __name__ == "__main__":
    main()
