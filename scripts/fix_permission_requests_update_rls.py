"""
修复 permission_requests 驳回后无法再次申请的问题。

根因：submitRequest 使用 upsert(onConflict:'user_email')。用户被驳回后再次申请时，
表里已存在同 user_email 的 rejected 行，upsert 走 ON CONFLICT DO UPDATE；
但 permission_requests 只有 admin 的 ALL 策略（USING auth.email()='57502460@qq.com'），
非管理员用户无匹配的 UPDATE 策略，UPDATE 被 admin 策略的 USING 拦截，
报 "new row violates row-level security policy (USING expression)"。

修复：新增一条与现有 insert own / select own 同构的 UPDATE 策略，
允许用户更新(重新提交)自己的申请行。

约束：仅新增策略，不修改/删除任何已有策略；管理员 ALL 策略保持不变。
"""
import os
import requests

REF = 'tqhtegazxykkqfcpejky'

def get_pat():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')
    with open(env_path) as f:
        for line in f:
            if line.startswith('SUPABASE_PAT='):
                return line.strip().split('=', 1)[1].strip()
    raise SystemExit('SUPABASE_PAT not found in .env.local')

def main():
    pat = get_pat()
    headers = {'Authorization': f'Bearer {pat}', 'Content-Type': 'application/json'}
    url = f'https://api.supabase.com/v1/projects/{REF}/database/query'

    # 1) 检查是否已有同名 UPDATE 策略（幂等）
    check = """
    SELECT policyname FROM pg_policies
    WHERE tablename='permission_requests' AND cmd='UPDATE' AND policyname='perm_req update own';
    """
    r = requests.post(url, headers=headers, json={'query': check})
    rows = r.json() if isinstance(r.json(), list) else []
    if any(row.get('policyname') == 'perm_req update own' for row in rows):
        print('[skip] 策略 perm_req update own 已存在，无需重复创建')
        return

    # 2) 创建 UPDATE 策略：用户可更新自己的申请行（与 insert own/select own 同构）
    create = """
    CREATE POLICY "perm_req update own" ON public.permission_requests
      FOR UPDATE TO public
      USING (auth.email() = user_email)
      WITH CHECK (auth.email() = user_email);
    """
    r = requests.post(url, headers=headers, json={'query': create})
    if r.status_code >= 400:
        print('[ERROR] 创建策略失败:', r.status_code, r.text)
        raise SystemExit(1)
    print('[ok] 已创建策略 perm_req update own (FOR UPDATE, USING/WITH CHECK auth.email()=user_email)')

    # 3) 验证
    verify = """
    SELECT policyname, cmd, qual, with_check FROM pg_policies
    WHERE tablename='permission_requests' ORDER BY cmd;
    """
    r = requests.post(url, headers=headers, json={'query': verify})
    print('[verify] 当前 permission_requests 策略:')
    print(r.json())

if __name__ == '__main__':
    main()
