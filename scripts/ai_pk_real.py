#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI大PK —— 真实大模型自选脚本

功能：
  让已配置 API 的大模型（目前 DeepSeek / 豆包）从 ALLFUND.CN 真实基金库（fund_scores 表）
  中「自己」挑选 5 只基金（每只 20% 等权），并产出两层选基逻辑：
      第一层 category_logic：为何选这些品类、为何不选其他品类。
      第二层 picks[].reason：为何选这只而非候选池里同品类的其他基金（基于真实指标）。

约束（用户硬性要求）：
  - 只能在 fund_scores 表内选基金，不编造、不引入表外数据。
  - 不强制按靠谱指数(k_all)排序——模型按自己的风格自由选品类与单基。

工作流程：
  1. 读 ai_pk_models，挑出 enabled 且配置了 api_provider 的模型。
  2. 从 fund_scores 构建「多样化候选池」（各大类 Top，真实指标齐全）。
  3. 逐模型调用真实 API（DeepSeek chat / 火山方舟 Ark）。
  4. 解析模型返回的 JSON（5 个 code + 两层理由），校验 code 真实存在、份额去重。
  5. 写入 ai_pk_picks（mode='real'），并把模型 mode 置为 'real'。

豆包(火山方舟)特别说明：
  - 必须先在火山方舟控制台创建「推理接入点」得到 ep-xxxx，并把 ep-xxxx 写入该模型行的 api_model。
  - 脚本读取 api_key_env（默认 ARK_API_KEY）作为 Bearer Token。
  - api_model 若不是以 'ep-' 开头（即仍是占位），脚本会跳过豆包并提示，不影响其他模型。

用法：
  python3 scripts/ai_pk_real.py                 # 跑所有已配置模型
  python3 scripts/ai_pk_real.py --models ds     # 只跑 DeepSeek
  python3 scripts/ai_pk_real.py --dry-run       # 只打印不写入
"""
import os
import re
import sys
import json
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

# ===== 候选池：各大类 Top，保证模型能自由选择品类 =====
POOL_CATEGORIES = ["混合型", "指数型", "债券型", "股票型", "QDII", "FOF"]
POOL_PER_CAT = 40
SELECT_FIELDS = "c,n,t0,t1_tt,k_all,r1y,r3y,r5y,dd1y,dd3y,sr1y,fund_scale"

# 份额归一化（同 seed_ai_pk.py）
_SHARE_SET = set("ACEFIHBDYRF")
_ACRONYM_SUFFIXES = ("ETF", "LOF", "QDII")


def norm_name(n):
    if not n:
        return ''
    n = n.strip()
    if len(n) >= 2 and n[-1] in _SHARE_SET and not n.endswith(_ACRONYM_SUFFIXES):
        return n[:-1]
    return n


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
    url = f"{SUPABASE_URL}/rest/v1/fund_scores"
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Accept": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=120)
    if r.status_code != 200:
        print(f"[REST ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    return r.json()


def build_candidate_pool():
    """各大类 Top N，份额去重，返回 (list, code->fund)。"""
    collected = []
    for cat in POOL_CATEGORIES:
        params = {
            "select": SELECT_FIELDS,
            "t0": f"eq.{cat}",
            "fund_scale": "gt.2",
            "r1y": "not.is.null",
            "order": "k_all.desc",
            "limit": str(POOL_PER_CAT),
        }
        data = rest_select(params)
        collected.extend(data)
    # 全市场 Top 补强（含跨类，避免漏掉头部）
    top = rest_select({
        "select": SELECT_FIELDS,
        "t0": "neq.货币型",
        "fund_scale": "gt.2",
        "r1y": "not.is.null",
        "order": "k_all.desc",
        "limit": "30",
    })
    collected.extend(top)

    # 份额去重：同基金只留一个主代码（优先 A 份额，否则规模大者）
    groups = {}
    for f in collected:
        groups.setdefault(norm_name(f.get('n')), []).append(f)
    out = []
    for items in groups.values():
        if len(items) == 1:
            out.append(items[0])
            continue
        a_items = [x for x in items if (x.get('n') or '').rstrip().endswith('A')]
        out.append(max(a_items, key=lambda x: (x.get('fund_scale') or 0)) if a_items
                   else max(items, key=lambda x: (x.get('fund_scale') or 0)))
    by_code = {f["c"]: f for f in out}
    print(f"[POOL] 候选池规模: {len(out)} 只（来自 {len(collected)} 原始，已份额去重）")
    return out, by_code


def fmt_num(v, pct=False):
    if v is None:
        return "无"
    return (f"{v:+.2f}%" if pct else f"{v:.2f}")


def pool_to_text(pool):
    lines = []
    for f in pool:
        lines.append(
            f"- code={f['c']} | 名称={f.get('n')} | 大类={f.get('t0')}/{f.get('t1_tt')} | "
            f"k_all={fmt_num(f.get('k_all'))} | 近1年={fmt_num(f.get('r1y'), True)} | "
            f"近3年={fmt_num(f.get('r3y'), True)} | 近1年回撤={fmt_num(f.get('dd1y'), True)} | "
            f"近3年回撤={fmt_num(f.get('dd3y'), True)} | 夏普1y={fmt_num(f.get('sr1y'))} | "
            f"规模={fmt_num(f.get('fund_scale'))}亿"
        )
    return "\n".join(lines)


def build_messages(model, pool_text):
    system = (
        "你是一名资深基金投顾 AI，必须严格基于用户提供的真实基金数据做决策，"
        "绝不编造基金或指标。你只能从用户给出的候选基金池中选择，输出严格 JSON。"
    )
    persona = model.get("persona") or "综合质地优先，全市场选最优质基金"
    clogic = model.get("category_logic") or ""
    user = f"""下面是从 ALLFUND.CN 基金库（fund_scores 表）抽取的真实候选基金池，附真实历史指标。

请你以「{model.get('name')}」的投顾风格来选基：
风格设定：{persona}
选基取向（仅供参考，你可自由发挥）：{clogic}

任务：从候选池中挑选恰好 5 只基金，每只等权 20%，构建一个投资组合。

硬性要求：
1. 只能从下方候选池挑选（code 必须出现在列表中），不可编造基金。
2. 恰好 5 只，权重各 20%。
3. 同一基金的不同份额（A/C/E 等）视为同一标的，不要同时选 A 和 C。
4. 输出严格 JSON（不要任何多余文字/解释），结构如下：
{{
  "category_logic": "第一层逻辑：你为什么选择这些品类、为何不选其他品类（2-4句，用真实指标支撑）",
  "picks": [
    {{"code": "基金code", "reason": "第二层逻辑：为什么选这只而非候选池里同品类的其他基金（基于真实指标，1-2句）"}},
    ... 共 5 个
  ]
}}

候选基金池（JSON）：
{pool_text}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def extract_json(text):
    # 去掉 ```json  fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def call_deepseek(prompt_messages, key):
    url = "https://api.deepseek.com/v1/chat/completions"
    body = {
        "model": "deepseek-chat",
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 1600,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_ark(model_id, prompt_messages, key):
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    body = {
        "model": model_id,
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 1600,
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_qwen(model_id, prompt_messages, key):
    # 阿里云百炼 OpenAI 兼容端点
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    body = {
        "model": model_id,
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 1600,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    r.raise_for_status()
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
    if provider == "volc-ark":
        apimodel = model.get("api_model") or ""
        if not apimodel.startswith("ep-"):
            raise RuntimeError(
                f"豆包(api_model={apimodel}) 不是有效的推理接入点(ep-xxxx)。"
                f"请在火山方舟控制台创建推理接入点并把 ep-xxxx 写入 ai_pk_models.api_model。"
            )
        return call_ark(apimodel, prompt_messages, key)
    raise RuntimeError(f"未知 api_provider: {provider}")


def resolve_names(codes):
    """确认 code 真实存在于 fund_scores，并取规范名称。返回 {code: name}。"""
    if not codes:
        return {}
    placeholders = ",".join(f"'{c}'" for c in codes)
    rows = mgmt_query(
        f"SELECT c, n FROM public.fund_scores WHERE c IN ({placeholders});"
    )
    return {r["c"]: r.get("n") or r["c"] for r in (rows or [])}


def run_model(model, pool, by_code, period_month, dry_run):
    print(f"\n===== [{model['id']}] {model['name']} ({model.get('api_provider')}) =====")
    messages = build_messages(model, pool_to_text(pool))
    try:
        raw = call_model(model, messages)
    except Exception as e:
        print(f"  [SKIP] 调用失败: {e}")
        return False

    try:
        data = extract_json(raw)
    except Exception as e:
        print(f"  [SKIP] JSON 解析失败: {e}\n  原始返回前200字: {raw[:200]}")
        return False

    cat_logic = (data.get("category_logic") or "").strip()
    picks = data.get("picks") or []
    if not cat_logic or len(picks) < 5:
        print(f"  [SKIP] 返回结构不完整：category_logic={'有' if cat_logic else '无'}, picks={len(picks)}")
        return False

    # 校验 code 真实存在 + 份额去重
    chosen_codes = []
    seen_names = set()
    valid_codes = set(by_code.keys())
    for p in picks:
        code = (p.get("code") or "").strip()
        if not code:
            continue
        if code in chosen_codes:
            continue
        # 真实存在性：在候选池中 OR 回库查 fund_scores
        name = by_code.get(code, {}).get("n")
        if code not in valid_codes:
            names = resolve_names([code])
            if code not in names:
                print(f"  [WARN] code={code} 不在 fund_scores，跳过")
                continue
            name = names[code]
        # 份额去重
        nn = norm_name(name)
        if nn in seen_names:
            print(f"  [WARN] {name}({code}) 与已选基金同标的（份额重复），跳过")
            continue
        seen_names.add(nn)
        chosen_codes.append(code)

    if len(chosen_codes) < 5:
        print(f"  [SKIP] 去重/校验后仅 {len(chosen_codes)} 只，不足 5")
        return False

    # 组装 picks（取前 5）
    final = []
    reason_map = {p.get("code"): p.get("reason", "") for p in picks}
    names_map = resolve_names(chosen_codes)
    for code in chosen_codes[:5]:
        final.append({
            "code": code,
            "name": names_map.get(code, by_code.get(code, {}).get("n", code)),
            "weight": 20,
            "reason": (reason_map.get(code) or "由模型自选").strip(),
        })

    print(f"  [OK] 选基：{', '.join(f['name'] for f in final)}")

    if dry_run:
        print(f"  [DRY-RUN] category_logic: {cat_logic[:120]}...")
        for f in final:
            print(f"    - {f['name']} ({f['code']}) 20% | {f['reason'][:80]}")
        return True

    # 写入 ai_pk_picks（mode='real'）
    picks_json = json.dumps(final, ensure_ascii=False).replace("'", "''")
    cat_json = cat_logic.replace("'", "''")
    mgmt_query(f"DELETE FROM public.ai_pk_picks WHERE model_id='{model['id']}' AND period_month='{period_month}';")
    mgmt_query(
        f"INSERT INTO public.ai_pk_picks (model_id, period_month, picks, mode) "
        f"VALUES ('{model['id']}','{period_month}','{picks_json}','real');"
    )
    # 更新模型 mode='real'，并写入本期第一层逻辑（覆盖规则版 category_logic）
    mgmt_query(
        f"UPDATE public.ai_pk_models SET mode='real', category_logic='{cat_json}' "
        f"WHERE id='{model['id']}';"
    )
    print(f"  [WRITE] 已写入当期({period_month})真实选基（mode=real）")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="限定模型 id，逗号分隔，如 ds,doubao")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写入")
    ap.add_argument("--period", help="期次 YYYY-MM，默认当月")
    args = ap.parse_args()

    period_month = args.period or datetime.date.today().strftime("%Y-%m")
    print(f"=== AI大PK 真实模型自选 (期次 {period_month}) ===")

    # 读模型配置
    rows = mgmt_query(
        "SELECT id,name,persona,category_logic,mode,api_provider,api_model,api_key_env,enabled "
        "FROM public.ai_pk_models WHERE enabled=true;"
    )
    models = [r for r in (rows or []) if r.get("api_provider")]
    if args.models:
        want = set(args.models.split(","))
        models = [m for m in models if m["id"] in want]
    if not models:
        print("[ERR] 没有已配置 api_provider 且启用的模型。请先在 ai_pk_models 配置 api_provider/api_model/api_key_env。")
        sys.exit(1)
    print(f"待跑模型: {', '.join(m['id'] for m in models)}")

    pool, by_code = build_candidate_pool()
    if not pool:
        print("[ERR] 候选池为空")
        sys.exit(1)

    ok = 0
    for m in models:
        if run_model(m, pool, by_code, period_month, args.dry_run):
            ok += 1
    print(f"\n=== 完成：{ok}/{len(models)} 个模型成功生成真实选基 ===")


if __name__ == "__main__":
    main()
