"""
visitor_logs 隐私收口 + 历史 PII 清洗（去个人化 P0 收尾）。

背景：
- visitor_logs 表此前 **未启用 RLS**（rowsecurity=false，零策略），任何人拿 anon key
  即可拉走全部行（含明文登录邮箱 + IP），是最大的个人信息泄露点。
- 历史数据里含 321 行明文邮箱（含主管理员 57502460@qq.com 等真实邮箱）。

本脚本做三件事（幂等，可重复运行）：
  phase1（不影响线上计数，先跑）：
    1. 确保 is_app_admin() SECURITY DEFINER 函数存在（判定管理员，绕过 RLS 避免递归）。
    2. 创建 get_visitor_count() SECURITY DEFINER 函数，GRANT EXECUTE 给 anon/authenticated
       —— 让前端底部「你是第 N 位访客」在 RLS 收紧后仍能取到累计数（只返回数字，不泄露行）。
    3. 清洗历史 PII：所有含 '@' 的邮箱 → 'authenticated'；'anon_<uuid>' → 'anonymous'。
  phase2（前端改用 RPC 计数并部署后再跑，避免打断线上计数）：
    4. 启用 RLS，只保留两条策略：
       - anon/authenticated 可 INSERT（继续上报访问）；
       - 仅管理员(is_app_admin())可 SELECT（后台数据中心读取）。
  verify：核验 PII=0、RLS 已启用、策略齐全、get_visitor_count() 可用。

用法：
  python3 scripts/secure_visitor_logs.py phase1
  python3 scripts/secure_visitor_logs.py phase2
  python3 scripts/secure_visitor_logs.py verify
"""
import sys
import json
import requests

PAT = None
with open('.env.local') as f:
    for line in f:
        if line.startswith('SUPABASE_PAT='):
            PAT = line.strip().split('=', 1)[1]
            break
if not PAT:
    raise SystemExit('SUPABASE_PAT not found in .env.local')

REF = 'tqhtegazxykkqfcpejky'
URL = f'https://api.supabase.com/v1/projects/{REF}/database/query'
H = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}


def q(sql):
    r = requests.post(URL, headers=H, json={'query': sql})
    try:
        j = r.json()
    except Exception:
        j = {'raw': r.text}
    return r.status_code, j


def run(sql, label):
    sc, j = q(sql)
    ok = sc in (200, 201) and not (isinstance(j, dict) and j.get('error'))
    if ok:
        print(f'[OK]   {label}')
    else:
        msg = j.get('error', {}).get('message', j) if isinstance(j, dict) else j
        print(f'[FAIL] {label}: HTTP {sc} {msg}')
    return ok, j


IS_APP_ADMIN = '''
CREATE OR REPLACE FUNCTION public.is_app_admin()
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT (auth.email() = '57502460@qq.com')
      OR EXISTS (
        SELECT 1 FROM public.user_permissions
        WHERE user_email = auth.email() AND is_admin = true
      );
$$;
'''

GET_COUNT = '''
CREATE OR REPLACE FUNCTION public.get_visitor_count()
RETURNS bigint
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$ SELECT count(*) FROM public.visitor_logs; $$;
'''


def phase1():
    print('=== phase1: 函数 + 历史 PII 清洗（不影响线上计数）===')
    run(IS_APP_ADMIN, 'ensure is_app_admin()')
    run(GET_COUNT, 'create get_visitor_count()')
    run('GRANT EXECUTE ON FUNCTION public.get_visitor_count() TO anon, authenticated;',
        'grant execute get_visitor_count')
    # 清洗：任何含 @ 的邮箱都视为可识别用户 → authenticated
    run("UPDATE public.visitor_logs SET email = 'authenticated' WHERE email LIKE '%@%';",
        "scrub plaintext emails -> authenticated")
    # anon_<uuid> 匿名追踪标识 → anonymous（下划线需转义）
    run(r"UPDATE public.visitor_logs SET email = 'anonymous' WHERE email LIKE 'anon\_%' ESCAPE '\';",
        "scrub anon uid -> anonymous")
    sc, j = q("SELECT count(*) FILTER (WHERE email LIKE '%@%' AND email NOT IN ('anonymous','authenticated')) AS pii_left, count(*) AS total FROM public.visitor_logs;")
    print('  after cleanup:', json.dumps(j, ensure_ascii=False))


def phase2():
    print('=== phase2: 启用 RLS + 策略（前端已改用 RPC 计数后再跑）===')
    run('ALTER TABLE public.visitor_logs ENABLE ROW LEVEL SECURITY;', 'enable RLS')
    # 表级授权（RLS 之上仍需 GRANT）
    run('GRANT SELECT, INSERT ON public.visitor_logs TO anon, authenticated;',
        'grant select/insert')
    run('DROP POLICY IF EXISTS "visitor_logs anon insert" ON public.visitor_logs;', 'drop old insert policy')
    run('DROP POLICY IF EXISTS "visitor_logs admin select" ON public.visitor_logs;', 'drop old select policy')
    run('''CREATE POLICY "visitor_logs anon insert" ON public.visitor_logs
  FOR INSERT TO anon, authenticated
  WITH CHECK (true);''', 'create insert policy (anyone can report)')
    run('''CREATE POLICY "visitor_logs admin select" ON public.visitor_logs
  FOR SELECT TO anon, authenticated
  USING (public.is_app_admin());''', 'create select policy (admin only)')


def verify():
    print('=== verify ===')
    sc, j = q("SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='visitor_logs';")
    print('  RLS enabled:', json.dumps(j, ensure_ascii=False))
    sc, j = q("SELECT policyname, cmd FROM pg_policies WHERE schemaname='public' AND tablename='visitor_logs' ORDER BY policyname;")
    print('  policies:', json.dumps(j, ensure_ascii=False))
    sc, j = q("SELECT count(*) FILTER (WHERE email LIKE '%@%' AND email NOT IN ('anonymous','authenticated')) AS pii_left, count(*) AS total FROM public.visitor_logs;")
    print('  PII left / total:', json.dumps(j, ensure_ascii=False))
    sc, j = q("SELECT public.get_visitor_count() AS cnt;")
    print('  get_visitor_count():', json.dumps(j, ensure_ascii=False))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if mode == 'phase1':
        phase1()
    elif mode == 'phase2':
        phase2()
    elif mode == 'verify':
        verify()
    else:
        raise SystemExit('usage: secure_visitor_logs.py [phase1|phase2|verify]')
