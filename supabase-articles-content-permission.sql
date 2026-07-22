-- ============================================================
-- 「内容」功能权限迁移
-- 目标：让被管理员授予 content 权限的普通用户也能发布/管理文章，
--       不再局限于 article_authors 白名单中的站长本人。
-- 幂等：所有对象均 CREATE OR REPLACE / DROP POLICY IF EXISTS / DROP CONSTRAINT IF EXISTS。
-- 依赖：supabase-articles-schema.sql 已先行应用（articles / article_authors / article_images 已存在）。
-- ============================================================

-- 1. has_content_permission() - SECURITY DEFINER 判定当前用户是否拥有「内容」权限
--    条件：user_permissions 中 is_admin=true 或 enabled_features 含 'content'，或主管理员邮箱。
CREATE OR REPLACE FUNCTION public.has_content_permission()
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_permissions u
    WHERE u.user_email = auth.email()
      AND (u.is_admin = true OR u.enabled_features::text ILIKE '%content%')
  ) OR (auth.email() = '57502460@qq.com')
$$;

-- 2. 放宽 articles.author_email 外键约束：允许被授权但不在 article_authors 白名单的用户发文
--    移除 REFERENCES，仅保留非空约束（作者仍须以本人邮箱署名）。已存在数据均为站长邮箱，安全。
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
      AND table_schema = 'public'
      AND table_name = 'articles'
      AND constraint_name = 'articles_author_email_fkey'
  ) THEN
    ALTER TABLE public.articles DROP CONSTRAINT articles_author_email_fkey;
  END IF;
END $$;

-- 3. 扩展 articles RLS 策略：作者 或 具 content 权限者 可写/删；content 权限者可读自己草稿
DROP POLICY IF EXISTS "articles_author_read" ON public.articles;
CREATE POLICY "articles_author_read"
  ON public.articles FOR SELECT TO authenticated
  USING (author_email = auth.email() OR public.is_article_author() OR public.has_content_permission());

DROP POLICY IF EXISTS "articles_author_insert" ON public.articles;
CREATE POLICY "articles_author_insert"
  ON public.articles FOR INSERT TO authenticated
  WITH CHECK (
    author_email = auth.email()
    AND (public.is_article_author() OR public.has_content_permission())
  );

DROP POLICY IF EXISTS "articles_author_update" ON public.articles;
CREATE POLICY "articles_author_update"
  ON public.articles FOR UPDATE TO authenticated
  USING (author_email = auth.email() OR public.is_article_author() OR public.has_content_permission())
  WITH CHECK (author_email = auth.email() OR public.is_article_author() OR public.has_content_permission());

DROP POLICY IF EXISTS "articles_author_delete" ON public.articles;
CREATE POLICY "articles_author_delete"
  ON public.articles FOR DELETE TO authenticated
  USING (author_email = auth.email() OR public.is_article_author() OR public.has_content_permission());

-- 4. 扩展 article_images RLS 策略：作者 或 具 content 权限者 可写/删
DROP POLICY IF EXISTS "article_images_author_insert" ON storage.objects;
CREATE POLICY "article_images_author_insert"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'article-images' AND (public.is_article_author() OR public.has_content_permission()));

DROP POLICY IF EXISTS "article_images_author_delete" ON storage.objects;
CREATE POLICY "article_images_author_delete"
  ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'article-images' AND (public.is_article_author() OR public.has_content_permission()));
