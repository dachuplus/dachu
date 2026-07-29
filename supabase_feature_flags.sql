-- ============================================================
-- 功能开放控制：feature_flags 表 + 仅主管理员可写的 RPC
-- 在 Supabase 控制台 → SQL Editor 中执行一次即可。
-- （沙箱无法直连 Supabase，故需手动执行；执行后前端即可在「管理-用户分析」
--   的「功能开放控制」面板中由 57502460@qq.com 切换各功能开放/关闭。）
-- ============================================================

-- 1) 功能开关表（匿名可读；写入仅经 RPC）
create table if not exists public.feature_flags (
  key          text primary key,
  open         boolean not null default true,
  label        text,
  description  text,
  sort_order   int
);

alter table public.feature_flags enable row level security;

-- 匿名 / 已登录 均可读取当前开关（前端据此控制路由可见性与访问权限）
drop policy if exists feature_flags_public_read on public.feature_flags;
create policy feature_flags_public_read
  on public.feature_flags for select
  using (true);

-- 2) 仅主管理员（57502460@qq.com）可切换开关的 RPC（SECURITY DEFINER 绕过 RLS）
create or replace function public.set_feature_flag(p_key text, p_open boolean)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- 硬约束：仅主管理员账户可调用，杜绝其他管理员越权
  if auth.email() <> '57502460@qq.com' then
    raise exception 'permission denied: only the primary admin can toggle feature flags';
  end if;

  insert into public.feature_flags (key, open)
  values (p_key, p_open)
  on conflict (key) do update set open = excluded.open;
end;
$$;

-- 3) 初始数据（全部默认开放；content 即博客，公开可读）
insert into public.feature_flags (key, open, label, description, sort_order) values
  ('content',    true, '内容（博客）', '独立性研究文章，公开可读（无需登录）', 1),
  ('signal',     true, '信号',         '宏观信号、股债性价比、风格因子、行业估值', 2),
  ('fund-rank',  true, '工具',         '靠谱指数评分、基金详情、基金对比', 3),
  ('portfolio',  true, '组合',         '自建组合、AI 组合、组合回测', 4)
on conflict (key) do nothing;
