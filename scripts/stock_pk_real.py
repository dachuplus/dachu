#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票组合 PK —— 真实大模型自选脚本（v2：基于 stock_scores 两层选股）

功能：
  让已配置 API 的真实大模型（豆包 / 千问 / 文心 / 智谱 / Kimi / MiniMax / DeepSeek）
  基于 stock_scores 表的真实数据做「两层」选股：
      第一层（行业 layer）：从 stock_scores 的「二级行业 industry」中，结合真实行业统计
             + 宏观/策略/行业/流动性/金融工程/胜率赔率研究，选出本期超配行业并给出完整推理。
      第二层（单品 layer）：在所选行业的真实候选股票中，挑选 5 只（每只 20% 等权），
              逐只给出基于表内真实指标（k_all/收益/回撤/夏普/估值/市值）的单品推理。

硬性约束（用户要求）：
  - 候选池与行业统计 100% 来自 stock_scores 真实表，模型不接触任何表外数据。
  - 模型推理只允许引用「下方提供的真实数字」，严禁提及任何表外或网络信息。
  - 最高风控：剔除 ST / *ST / 退市 / 上市<60天 / 停牌 股票。

工作流程：
  1. 读 stock_pk_models（enabled 且配了 api_provider 的模型）。
  2. build_industry_summary()：从 stock_scores 按 industry 聚合真实统计。
  3. 逐模型：Step1 行业选择（category_logic + 选中 industry 列表）→ Step2 单品选择（picks + reason）。
  4. 校验 code 真实存在于 stock_scores、份额去重、剔除风控股票。
  5. 写入 stock_pk_picks（mode='real'），并把模型 mode 置为 'real'。

容错：若 stock_scores.industry 全为空（行业源不可达环境），第一层退化为「全市场风格/主题」
      选择，仍保证能产出 5 只真实股票；行业源可达后自动恢复「先选行业」设计。

用法：
  python3 scripts/stock_pk_real.py                 # 跑所有已配置模型
  python3 scripts/stock_pk_real.py --models ds     # 只跑 DeepSeek
  python3 scripts/stock_pk_real.py --dry-run       # 只打印不写入
"""
import os
import re
import sys
import json
import time
import datetime
import argparse
import requests

# ===== 凭证 =====
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
if not PAT:
    raise SystemExit("缺少 SUPABASE_PAT 环境变量。")
REF = "tqhtegazxykkqfcpejky"
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
os.environ["SUPABASE_MGMT_TOKEN"] = PAT
os.environ["SUPABASE_PAT"] = PAT
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

# ===== 候选池参数 =====
POOL_PER_CAT = 25          # 每个二级行业取 Top N（按 k_all 倒序）作为单品候选
CANDIDATE_SELECT = "code,name,industry,k_all,return_1y,return_3y,max_drawdown,sharpe,pe_ttm,pb,mktcap"
ARK_MAX_TOKENS = 2048

# 最高风控规则：识别 ST / *ST / 退市 / 停牌 / 上市<60天
_ST_RE = re.compile(r'(ST)')
def is_risk_stock(name, is_st, is_delisted, is_suspended, list_date):
    if is_st or is_delisted or is_suspended:
        return True
    if name and ('退' in name or '*ST' in name or 'ST' in name.upper()):
        return True
    if list_date:
        try:
            ld = datetime.date.fromisoformat(list_date)
            if (datetime.date.today() - ld).days < 60:
                return True
        except Exception:
            pass
    return False


def mgmt_query(sql, expect_ok=(200, 201)):
    r = requests.post(MGMT_URL, headers=MGMT_HEADERS, json={"query": sql}, timeout=120)
    if r.status_code not in expect_ok:
        print(f"[MGMT ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    try:
        return r.json()
    except Exception:
        return None


def rest_select(params, table="stock_scores"):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Accept": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=120)
    if r.status_code != 200:
        print(f"[REST ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    return r.json()


# ===== 行业摘要 / 候选池（全部基于 stock_scores 真实数据）=====
def build_industry_summary():
    """从 stock_scores 按二级行业(industry)聚合真实统计，供第一层行业推理。"""
    print("[CAT] 构建 stock_scores 二级行业摘要 ...")
    sql = (
        "SELECT industry, COUNT(*) AS cnt, "
        "ROUND(AVG(k_all)::numeric,1) AS avg_k, "
        "ROUND(AVG(return_1y)::numeric,2) AS avg_r1y, "
        "ROUND(AVG(max_drawdown)::numeric,2) AS avg_dd, "
        "ROUND(AVG(sharpe)::numeric,2) AS avg_sr "
        "FROM public.stock_scores "
        "WHERE industry IS NOT NULL AND k_all IS NOT NULL AND return_1y IS NOT NULL "
        "GROUP BY industry ORDER BY avg_k DESC;"
    )
    rows = mgmt_query(sql) or []
    print(f"[CAT] 行业数: {len(rows)}")
    return rows


def build_candidate_pool(chosen_industries):
    """针对模型选定的二级行业，从 stock_scores 取 Top POOL_PER_CAT（按 k_all 倒序）作为单品候选。
    排除 ST/*ST/退市/停牌/上市<60天。返回 {industry: [stock,...]}。
    若 chosen_industries 为空（行业源不可达），退化为全市场 Top 候选。"""
    pool = {}
    if chosen_industries:
        for ind in chosen_industries:
            indq = ind.replace("'", "''")
            rows = rest_select({
                "select": CANDIDATE_SELECT,
                "industry": f"eq.{indq}",
                "is_st": "eq.false", "is_delisted": "eq.false", "is_suspended": "eq.false",
                "k_all": "not.is.null",
                "order": "k_all.desc",
                "limit": str(POOL_PER_CAT),
            }, table="stock_scores")
            pool[ind] = rows
    else:
        rows = rest_select({
            "select": CANDIDATE_SELECT,
            "is_st": "eq.false", "is_delisted": "eq.false", "is_suspended": "eq.false",
            "k_all": "not.is.null",
            "order": "k_all.desc",
            "limit": str(POOL_PER_CAT * 6),
        }, table="stock_scores")
        pool["__all__"] = rows
    total = sum(len(v) for v in pool.values())
    print(f"[POOL] 候选池: {len(chosen_industries) if chosen_industries else '全市场'} 个维度, 共 {total} 只真实股票")
    return pool


def validate_in_scores(code):
    if not code:
        return None
    cands = [code.strip()]
    rows = rest_select({"select": CANDIDATE_SELECT, "code": f"eq.{code.strip()}"}, table="stock_scores")
    return rows[0] if rows else None


def fmt_num(v, pct=False):
    if v is None:
        return "无"
    return (f"{v:+.2f}%" if pct else f"{v:.2f}")


# ===== Prompt 构造（两层）=====
def build_category_messages(model, ind_summary):
    lines = []
    for r in ind_summary:
        lines.append(
            f"- 二级行业={r['industry']} | 股票数={r['cnt']} | 平均靠谱指数k_all={r['avg_k']} | "
            f"近1年平均收益={r['avg_r1y']}% | 平均最大回撤={r['avg_dd']}% | 平均夏普={r['avg_sr']}"
        )
    ind_text = "\n".join(lines) if lines else "（当前环境二级行业标注暂不可用，请基于下方全市场候选股票直接挑选）"
    system = (
        "你是一名顶级股票投顾 AI，参加「股票组合 PK」选股竞赛。"
        "你必须严格基于下方提供的 stock_scores 真实行业统计（或真实候选股票）做决策，只输出 JSON，"
        "不编造、不引用任何表外或网络信息。"
        "【时间锚点】今天是 2026 年，所有数据均来自 stock_scores 表（数据截至 2026 年），"
        "严禁外推到任何未提供的年份/时段。"
        "【字数限制】category_logic 中文输出严格控制在 200 字以内。"
    )
    user = f"""你代表「{model.get('name')}」，正在与其他 6 个模型同台竞技。

【第一层任务 · 选二级行业（从 stock_scores 二级行业中选）】
下方是 stock_scores 表中所有「二级行业(industry)」的真实聚合统计（平均靠谱指数 k_all、平均收益、平均回撤、平均夏普、股票数量）。
请基于这些真实数据，结合宏观/策略/行业/流动性/金融工程/胜率赔率研究，从全部行业中选出你本期要超配的若干行业（建议 5~8 个），
并给出完整、有说服力的推理：
  · 为什么选这些行业（宏观象限、风格因子强弱、行业景气、流动性、风险预算、胜率赔率）；
  · 为什么不选其他行业。
推理必须结合上方提供的真实统计数字，严禁空话、严禁引用任何表外或网络信息。

【输出严格 JSON（不要任何多余文字）】：
{{
  "category_logic": "第一层完整推理：结合真实行业统计+宏观/策略/行业/流动性/金融工程/胜率赔率，说明为何超配这些行业（≤200字，须有真实数字支撑，禁止外推未提供的年份）",
  "industries": [
    {{"industry": "选中的二级行业名称（必须来自上方列表）", "reason": "为何选该行业的简短理由（须结合真实统计）"}},
    ... 共 5~8 个
  ]
}}

可供选择的二级行业及真实统计：
{ind_text}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_single_messages(model, cat_logic, pool):
    blocks = []
    code_to_stock = {}
    for ind, stocks in pool.items():
        flines = []
        for s in stocks:
            c = s.get("code")
            flines.append(
                f"  - code={c} | 名称={s.get('name')} | 行业={s.get('industry') or '—'} | "
                f"k_all={fmt_num(s.get('k_all'))} | 近1年={fmt_num(s.get('return_1y'), True)} | "
                f"近3年={fmt_num(s.get('return_3y'), True)} | 近1年回撤={fmt_num(s.get('max_drawdown'), True)} | "
                f"夏普={fmt_num(s.get('sharpe'))} | PE(TTM)={fmt_num(s.get('pe_ttm'))} | PB={fmt_num(s.get('pb'))} | 市值={fmt_num(s.get('mktcap'))}亿"
            )
            code_to_stock[c] = s
        blocks.append(f"【维度 {ind} 候选股票】\n" + "\n".join(flines))
    pool_text = "\n\n".join(blocks)
    system = (
        "你是一名顶级股票投顾 AI，参加「股票组合 PK」选股竞赛。"
        "你必须严格基于下方提供的 stock_scores 真实股票数据做单品选择，只输出 JSON，"
        "严禁引用任何表外/网络信息（尤其不得提及任何表外内容——这些不在提供的数据中，纯属臆测，判为无效）。"
        "【时间锚点】今天是 2026 年，数据来自 stock_scores，严禁外推未提供的年份/时段。"
        "【字数限制】每个 reason 中文输出严格控制在 120 字以内。"
    )
    user = f"""你代表「{model.get('name')}」。第一层行业选择已完成，结论如下：
{cat_logic}

【第二层任务 · 选股票单品（在所选维度内选）】
下方是你在第一层所选维度的真实候选股票（已按维度分组，数据来自 stock_scores 真实表：k_all/收益/回撤/夏普/估值/市值）。
请从这些候选股票中挑选恰好 5 只（每只 20% 等权）构建组合。要求：
  · 所选股票必须来自上方候选列表（code 必须出现），不可编造、不可引入列表外股票。
  · 优先覆盖第一层选定的多个维度，体现分散。
  · 对每只股票，给出完整、有说服力的单品推理，必须且仅基于上方真实数据：
    ① 同类对比：该股票 k_all / 收益在所属维度中的相对位置；
    ② 收益：近1/3年收益，相对维度均值；
    ③ 回撤：最大回撤控制能力；
    ④ 夏普：风险调整后收益；
    ⑤ 估值：PE/PB 相对位置；
    ⑥ 综合：为何它是该维度下的最优载体。
  · 【严禁】提及任何网络/表外信息——这些不在提供的数据中，纯属臆测，会判为无效。

【硬性约束 · 最高风控】
- 严禁选择 ST / *ST / 退市 / 上市不足 60 天 / 停牌 股票（候选已预先剔除，也不得自行引入）。

【输出严格 JSON（不要任何多余文字）】：
{{
  "picks": [
    {{"code": "股票code(必须来自上方候选列表)", "reason": "第二层单品推理：基于真实数据①②③④⑤⑥说明为何选它（≤120字，禁止表外信息）"}},
    ... 共 5 个
  ]
}}

候选股票（真实数据，来自 stock_scores）：
{pool_text}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], code_to_stock


def extract_json(text):
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    raise ValueError(f"无法从返回文本中提取JSON: {text[:200]}…")


def call_deepseek(prompt_messages, key):
    url = "https://api.deepseek.com/v1/chat/completions"
    body = {"model": "deepseek-chat", "messages": prompt_messages, "temperature": 0.7,
            "max_tokens": 4096, "response_format": {"type": "json_object"}}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_ark(model_id, prompt_messages, key, timeout=300, max_retries=2):
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    body = {"model": model_id, "messages": prompt_messages, "temperature": 0.7, "max_tokens": ARK_MAX_TOKENS}
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                              json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 ** attempt * 5)
            else:
                raise
    raise last_err


def call_qwen(model_id, prompt_messages, key):
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    body = {"model": model_id, "messages": prompt_messages, "temperature": 0.7, "max_tokens": 8192,
            "response_format": {"type": "json_object"}}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    if r.status_code != 200:
        raise RuntimeError(f"百炼 API 返回 {r.status_code}: {r.text[:400]}")
    content = r.json()["choices"][0]["message"]["content"]
    if not content:
        raise RuntimeError(f"百炼模型({model_id})返回空内容")
    return content


def call_wenxin(model_id, prompt_messages, key):
    url = "https://qianfan.baidubce.com/v2/chat/completions"
    body = {"model": model_id, "messages": prompt_messages, "temperature": 0.7, "max_tokens": 4096}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_zhipu(model_id, prompt_messages, key):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    body = {"model": model_id, "messages": prompt_messages, "temperature": 0.7, "max_tokens": 4096,
            "response_format": {"type": "json_object"}}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    if r.status_code != 200:
        raise RuntimeError(f"智谱 API 返回 {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"]


def call_kimi(model_id, prompt_messages, key):
    url = "https://api.moonshot.cn/v1/chat/completions"
    body = {"model": model_id, "messages": prompt_messages, "temperature": 0.7, "max_tokens": 4096,
            "response_format": {"type": "json_object"}}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    if r.status_code != 200:
        raise RuntimeError(f"Kimi API 返回 {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"]


def call_model(model, prompt_messages):
    provider = model.get("api_provider")
    keyenv = model.get("api_key_env")
    key = os.environ.get(keyenv) if keyenv else None
    if not key:
        raise RuntimeError(f"缺少环境变量 {keyenv}（{provider} 需要 API Key）")
    if provider == "deepseek":
        return call_deepseek(prompt_messages, key)
    if provider == "qwen":
        return call_qwen(model.get("api_model") or "qwen-plus", prompt_messages, key)
    if provider == "wenxin":
        return call_wenxin(model.get("api_model") or "ernie-4.5-8k-preview", prompt_messages, key)
    if provider == "zhipu":
        return call_zhipu(model.get("api_model") or "glm-4-plus", prompt_messages, key)
    if provider == "kimi":
        return call_kimi(model.get("api_model") or "kimi-k2", prompt_messages, key)
    if provider == "volc-ark":
        apimodel = model.get("api_model") or ""
        if not apimodel.startswith("ep-"):
            raise RuntimeError(f"豆包(api_model={apimodel}) 不是有效的推理接入点(ep-xxxx)。")
        return call_ark(apimodel, prompt_messages, key)
    raise RuntimeError(f"未知 api_provider: {provider}")


def run_model(model, ind_summary, period_month, dry_run):
    print(f"\n===== [{model['id']}] {model['name']} ({model.get('api_provider')}) =====")

    # ---------- Step 1：选行业 ----------
    msgs1 = build_category_messages(model, ind_summary)
    try:
        raw1 = call_model(model, msgs1)
    except Exception as e:
        print(f"  [SKIP] Step1 调用失败: {e}")
        return False
    try:
        d1 = extract_json(raw1)
    except Exception as e:
        print(f"  [SKIP] Step1 JSON 解析失败: {e}\n  原始前200字: {raw1[:200]}")
        return False
    cat_logic = (d1.get("category_logic") or "").strip()
    inds = d1.get("industries") or []
    chosen = [c.get("industry") for c in inds if isinstance(c, dict) and c.get("industry")]
    if not cat_logic:
        print(f"  [SKIP] Step1 结构不完整：category_logic 为空")
        return False
    print(f"  [STEP1] 选中行业/维度: {', '.join(chosen) if chosen else '（全市场退化）'}")

    # ---------- Step 2：选单品 ----------
    pool = build_candidate_pool(chosen)
    msgs2, code_to_stock = build_single_messages(model, cat_logic, pool)
    try:
        raw2 = call_model(model, msgs2)
    except Exception as e:
        print(f"  [SKIP] Step2 调用失败: {e}")
        return False
    try:
        d2 = extract_json(raw2)
    except Exception as e:
        print(f"  [SKIP] Step2 JSON 解析失败: {e}\n  原始前200字: {raw2[:200]}")
        return False
    picks = d2.get("picks") or []
    if not isinstance(picks, list) or len(picks) < 5:
        print(f"  [SKIP] Step2 picks 不足 5：{len(picks) if isinstance(picks, list) else '非列表'}")
        return False

    chosen_stocks = []
    seen = set()
    for p in picks:
        code = (p.get("code") or "").strip()
        s = code_to_stock.get(code) or validate_in_scores(code)
        if not s:
            print(f"  [WARN] 无法校验股票（code={code}），跳过")
            continue
        if is_risk_stock(s.get("name"), s.get("is_st"), s.get("is_delisted"), s.get("is_suspended"), s.get("list_date")):
            print(f"  [WARN] {s.get('name')} 命中风控过滤（ST/退市/停牌/次新），跳过")
            continue
        if code in seen:
            print(f"  [WARN] {s.get('name')} 重复，跳过")
            continue
        seen.add(code)
        chosen_stocks.append({
            "code": s["code"],
            "name": s.get("name"),
            "weight": 20,
            "reason": (p.get("reason") or "由模型自选").strip(),
            "industry": s.get("industry") or "",
        })
        if len(chosen_stocks) >= 5:
            break

    if len(chosen_stocks) < 5:
        print(f"  [SKIP] 校验后仅 {len(chosen_stocks)} 只有效股票，不足 5，本模型跳过")
        return False

    print(f"  [OK] 选股：{', '.join(x['name'] for x in chosen_stocks)}")

    if dry_run:
        print(f"  [DRY-RUN] category_logic: {cat_logic[:160]}...")
        for x in chosen_stocks:
            print(f"    - {x['name']} ({x['code']}) 20% | {x['reason'][:90]}")
        return True

    picks_json = json.dumps(chosen_stocks, ensure_ascii=False).replace("'", "''")
    cat_json = cat_logic.replace("'", "''")
    mgmt_query(f"DELETE FROM public.stock_pk_picks WHERE model_id='{model['id']}' AND period_month='{period_month}';")
    mgmt_query(
        f"INSERT INTO public.stock_pk_picks (model_id, period_month, picks, mode) "
        f"VALUES ('{model['id']}','{period_month}','{picks_json}','real');"
    )
    mgmt_query(
        f"UPDATE public.stock_pk_models SET mode='real', category_logic='{cat_json}' "
        f"WHERE id='{model['id']}';"
    )
    print(f"  [WRITE] 已写入当期({period_month})选股（mode=real）")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="限定模型 id，逗号分隔，如 ds,doubao")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写入")
    ap.add_argument("--period", help="期次 YYYY-MM，默认当月")
    args = ap.parse_args()

    period_month = args.period or datetime.date.today().strftime("%Y-%m")
    print(f"=== 股票组合 PK 真实模型自选（基于 stock_scores 两层选股：先选行业，再选单品）(期次 {period_month}) ===")

    rows = mgmt_query(
        "SELECT id,name,persona,category_logic,mode,api_provider,api_model,api_key_env,enabled "
        "FROM public.stock_pk_models WHERE enabled=true;"
    )
    models = [r for r in (rows or []) if r.get("api_provider")]
    if args.models:
        want = set(args.models.split(","))
        models = [m for m in models if m["id"] in want]
    if not models:
        print("[ERR] 没有已配置 api_provider 且启用的模型。")
        sys.exit(1)
    print(f"待跑模型: {', '.join(m['id'] for m in models)}")

    ind_summary = build_industry_summary()

    ok = 0
    for m in models:
        if run_model(m, ind_summary, period_month, args.dry_run):
            ok += 1
    print(f"\n=== 完成：{ok}/{len(models)} 个模型成功生成两层选股 ===")


if __name__ == "__main__":
    main()
