"""
修复 user_permissions RLS 无限递归问题。

根因：之前「管理员可写」策略的 USING/WITH CHECK 里直接写了
  EXISTS (SELECT 1 FROM user_permissions up WHERE up.user_email = auth.email() AND up.is_admin = true)
该子查询引用了 user_permissions 表自身，而该表启用 RLS，导致每次查询都重新触发策略本身
→ Postgres 报 "infinite recursion detected in policy for relation user_permissions"。

修复方式：
1. 删除递归的 ALL 策略。
2. 新建 SECURITY DEFINER 函数 is_app_admin()，以函数所有者(数据库拥有者，具备 BYPASSRLS)身份
   读取 user_permissions 判断管理员，从而不触发策略递归。
3. 用该函数重建写策略（主管理员 OR is_admin 用户可写）。
4. 保留原有 SELECT 策略(USING true)不变。

幂等：DROP IF EXISTS + CREATE OR REPLACE。
"""
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
headers = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}


def run(sql, label):
    r = requests.post(
        f'https://api.supabase.com/v1/projects/{REF}/database/query',
        headers=headers, json={'query': sql})
    j = r.json()
    if isinstance(j, dict) and j.get('error'):
        print(f'[FAIL] {label}: {j["error"].get("message", j)}')
        return False
    print(f'[OK]   {label}')
    return True


# 1. 删除递归策略
run('DROP POLICY IF EXISTS "user_permissions admin write" ON public.user_permissions;',
    'drop recursive ALL policy')

# 2. 创建 SECURITY DEFINER 管理员判断函数（绕过 RLS，避免递归）
run('''
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
''', 'create is_app_admin() SECURITY DEFINER function')

# 3. 用函数重建写策略（不再直接自引用 user_permissions）
run('''
CREATE POLICY "user_permissions admin write" ON public.user_permissions
  FOR ALL TO public
  USING (public.is_app_admin())
  WITH CHECK (public.is_app_admin());
''', 'create non-recursive write policy')

# 4. 验证：模拟前端用 anon 身份查 user_permissions 不应再递归（PAT 有 bypassrls，单独验证函数逻辑）
print('--- 验证 is_app_admin() 函数可被调用（不抛递归）---')
r = requests.post(
    f'https://api.supabase.com/v1/projects/{REF}/database/query',
    headers=headers,
    json={'query': "SELECT public.is_app_admin() AS ok;"})
print(json.dumps(r.json(), ensure_ascii=False))
print('--- 验证 SELECT 策略仍能读（PAT 有 bypassrls，仅确认表可访问）---')
r2 = requests.post(
    f'https://api.supabase.com/v1/projects/{REF}/database/query',
    headers=headers,
    json={'query': "SELECT user_email, is_admin FROM public.user_permissions LIMIT 5;"})
j2 = r2.json()
if isinstance(j2, list) and j2 and 'error' in j2[0]:
    print('[FAIL] SELECT:', j2[0]['error'].get('message'))
else:
    print('[OK]   SELECT ok, rows:', len(j2) if isinstance(j2, list) else j2)
