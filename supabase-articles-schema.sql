-- ============================================================
-- 我的内容（类公众号）模块 Schema
-- 定位：工具 + 独立性研究；合规护栏（后端），不违反《金融产品网络营销管理办法》
-- 作者：仅站长账号（article_authors 表中存在的邮箱）
-- 幂等：所有对象均 CREATE OR REPLACE / IF NOT EXISTS / DROP ... IF EXISTS，可重复执行
-- ============================================================

-- 0. 通用 updated_at 触发器函数（若已存在则替换，幂等）
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ============================================================
-- 1. article_authors - 作者白名单（仅表中存在的邮箱可发文）
-- ============================================================
CREATE TABLE IF NOT EXISTS public.article_authors (
  email       text PRIMARY KEY,
  author_name text NOT NULL,
  bio         text,
  created_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now()
);

ALTER TABLE public.article_authors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "article_authors_public_read" ON public.article_authors;
CREATE POLICY "article_authors_public_read"
  ON public.article_authors FOR SELECT
  USING (true);

DROP POLICY IF EXISTS "article_authors_self_write" ON public.article_authors;
CREATE POLICY "article_authors_self_write"
  ON public.article_authors FOR INSERT TO authenticated
  WITH CHECK (email = auth.email());

DROP POLICY IF EXISTS "article_authors_self_update" ON public.article_authors;
CREATE POLICY "article_authors_self_update"
  ON public.article_authors FOR UPDATE TO authenticated
  USING (email = auth.email())
  WITH CHECK (email = auth.email());

-- 2. is_article_author() - SECURITY DEFINER 判定当前用户是否为作者
--    用 SECURITY DEFINER 规避 RLS 递归（内部 SELECT 走函数持有者权限，不触发 article_authors 的 RLS）
CREATE OR REPLACE FUNCTION public.is_article_author()
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.article_authors a
    WHERE a.email = auth.email()
  );
$$;

-- ============================================================
-- 3. articles - 文章主表
-- ============================================================
CREATE TABLE IF NOT EXISTS public.articles (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  author_email text NOT NULL REFERENCES public.article_authors(email),
  title        text NOT NULL CHECK (char_length(title) <= 200),
  summary      text,
  content      text NOT NULL,
  cover_image  text,
  tags         text[] DEFAULT '{}',
  status       text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
  views        integer NOT NULL DEFAULT 0,
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now(),
  published_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_articles_author ON public.articles(author_email);
CREATE INDEX IF NOT EXISTS idx_articles_published
  ON public.articles(published_at DESC) WHERE status = 'published';
CREATE INDEX IF NOT EXISTS idx_articles_tags ON public.articles USING gin(tags);

ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;

-- 公开可读：仅已发布文章（anon + authenticated 均适用）
DROP POLICY IF EXISTS "articles_public_read" ON public.articles;
CREATE POLICY "articles_public_read"
  ON public.articles FOR SELECT
  USING (status = 'published');

-- 作者可读：自己全部（含草稿）
DROP POLICY IF EXISTS "articles_author_read" ON public.articles;
CREATE POLICY "articles_author_read"
  ON public.articles FOR SELECT TO authenticated
  USING (author_email = auth.email() OR public.is_article_author());

-- 仅作者可插入，且 author_email 必须绑定当前登录邮箱
DROP POLICY IF EXISTS "articles_author_insert" ON public.articles;
CREATE POLICY "articles_author_insert"
  ON public.articles FOR INSERT TO authenticated
  WITH CHECK (public.is_article_author() AND author_email = auth.email());

-- 仅作者可更新自己的文章
DROP POLICY IF EXISTS "articles_author_update" ON public.articles;
CREATE POLICY "articles_author_update"
  ON public.articles FOR UPDATE TO authenticated
  USING (author_email = auth.email() OR public.is_article_author())
  WITH CHECK (author_email = auth.email() OR public.is_article_author());

-- 仅作者可删除自己的文章
DROP POLICY IF EXISTS "articles_author_delete" ON public.articles;
CREATE POLICY "articles_author_delete"
  ON public.articles FOR DELETE TO authenticated
  USING (author_email = auth.email() OR public.is_article_author());

-- updated_at 自动维护
DROP TRIGGER IF EXISTS trg_articles_set_updated_at ON public.articles;
CREATE TRIGGER trg_articles_set_updated_at
  BEFORE UPDATE ON public.articles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- 4. 合规护栏触发器（后端拦截：《金融产品网络营销管理办法》相关禁语）
--    命中即拒绝写入，与前端拦截形成双重保险
-- ============================================================
CREATE OR REPLACE FUNCTION public.guard_article_compliance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_text      text;
  v_forbidden text[] := ARRAY[
    '保本','稳赚','必涨','保证收益','承诺收益','推荐买入','跟单',
    '代客理财','零风险','稳赚不赔','高收益无风险','内部消息','包赚',
    ' guaranteed','保证盈利','保底'
  ];
  i           int;
BEGIN
  v_text := coalesce(NEW.title,'') || ' ' || coalesce(NEW.summary,'') || ' ' || coalesce(NEW.content,'');
  FOR i IN 1..array_length(v_forbidden, 1) LOOP
    IF v_text ILIKE '%' || v_forbidden[i] || '%' THEN
      RAISE EXCEPTION 'COMPLIANCE_VIOLATION: 内容包含不合规表述「%」，请修改后重试', v_forbidden[i];
    END IF;
  END LOOP;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_articles_compliance ON public.articles;
CREATE TRIGGER trg_articles_compliance
  BEFORE INSERT OR UPDATE ON public.articles
  FOR EACH ROW EXECUTE FUNCTION public.guard_article_compliance();

-- ============================================================
-- 5. increment_article_views(p_article_id) - 阅读量自增（公开可调用，仅统计已发布）
-- ============================================================
CREATE OR REPLACE FUNCTION public.increment_article_views(p_article_id bigint)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.articles
     SET views = views + 1
   WHERE id = p_article_id AND status = 'published';
END;
$$;

GRANT EXECUTE ON FUNCTION public.increment_article_views(bigint) TO anon, authenticated;

-- ============================================================
-- 6. article_images - 图片存储桶（公开读，仅作者可写/删）
-- ============================================================
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('article-images', 'article-images', true, 5242880,
        ARRAY['image/png','image/jpeg','image/webp','image/gif'])
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "article_images_public_read" ON storage.objects;
CREATE POLICY "article_images_public_read"
  ON storage.objects FOR SELECT TO anon, authenticated
  USING (bucket_id = 'article-images');

DROP POLICY IF EXISTS "article_images_author_insert" ON storage.objects;
CREATE POLICY "article_images_author_insert"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'article-images' AND public.is_article_author());

DROP POLICY IF EXISTS "article_images_author_delete" ON storage.objects;
CREATE POLICY "article_images_author_delete"
  ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'article-images' AND public.is_article_author());

-- ============================================================
-- 7. 种子数据：站长作者（email 固定为管理员邮箱）
--    通过 SUPABASE_PAT（service role）写入，绕过 RLS
-- ============================================================
INSERT INTO public.article_authors (email, author_name, bio)
VALUES ('57502460@qq.com', '独立研究', '独立性研究栏目。所有内容仅代表个人研究观点，不构成任何投资建议，亦不构成金融产品营销。')
ON CONFLICT (email) DO UPDATE
  SET author_name = EXCLUDED.author_name,
      bio = EXCLUDED.bio,
      updated_at = now();
