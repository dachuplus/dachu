-- ============================================================================
-- 数据下载中心：私有化 + 管理员门控
-- 目标：服务器上的所有导出文件，必须「注册登录 + 已开通管理员权限」才可下载。
-- 背景：EdgeOne Pages 静态托管会绕过前端路由守卫，dist/downloads/* 任何人都能取。
--       因此把文件移入 Supabase Storage 私有桶，用 RLS 做真正的授权。
-- 作者：2026-09-22
-- ============================================================================

-- 1) 私有桶（public=false ⇒ 走 /object/public/ 直接 400/404，只能换签名 URL）
insert into storage.buckets (id, name, public)
values ('downloads', 'downloads', false)
on conflict (id) do update set public = false;

-- 2) 授权判定函数
--    为什么必须是 SECURITY DEFINER + 属主 postgres：
--      storage.objects 的 RLS 策略里要调用本函数，若本函数再以调用者身份读
--      user_permissions（那张表自己也有 RLS 策略），就会触发 42P17 无限递归。
--      SECURITY DEFINER（属主为超级用户 postgres）让函数体内绕过 RLS，彻底断开递归。
create or replace function public.can_read_downloads()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select
    -- 站点管理员邮箱（与前端 ADMIN_EMAIL 一致）
    coalesce((auth.jwt() ->> 'email') = '57502460@qq.com', false)
    -- 或：注册用户 + 已被授予管理员权限
    or exists (
      select 1
      from public.user_permissions up
      where up.is_admin is true
        and up.user_email = (auth.jwt() ->> 'email')
    );
$$;

-- 收紧执行权：任何人可调（策略里要用），但不给 anon 之外的额外能力
revoke all on function public.can_read_downloads() from public;
grant execute on function public.can_read_downloads() to anon, authenticated;

comment on function public.can_read_downloads() is
  '数据下载中心读取门控：管理员邮箱或 user_permissions.is_admin=true 的登录用户可读私有桶 downloads。';

-- 3) storage.objects 上的 SELECT 策略（只作用于 downloads 桶，不影响 article-images）
drop policy if exists downloads_admin_read on storage.objects;
create policy downloads_admin_read on storage.objects
  for select
  to authenticated
  using (bucket_id = 'downloads' and public.can_read_downloads());

-- 4) 自检
select
  (select public from storage.buckets where id = 'downloads')            as bucket_public,
  (select count(*) from pg_policies
     where schemaname = 'storage' and tablename = 'objects'
       and policyname = 'downloads_admin_read')                          as policy_cnt,
  (select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = 'can_read_downloads')    as func_cnt;
