/**
 * useFeatureFlags.js — 全局功能开放开关
 *
 * 用途：站长处（57502460@qq.com）在「管理-用户分析-功能开放控制」面板里
 * 逐个切换功能（信号 / 工具 / 组合 / 内容）的开放/关闭，前端据此动态控制
 * 路由可见性与访问权限。未建表或查询失败时回退 DEFAULT_FLAGS（全部开放），
 * 保证站点不崩。
 *
 * 数据来源：Supabase 表 feature_flags（anon 可读，RLS using(true)）；
 * 写入走 SECURITY DEFINER 的 RPC set_feature_flag（仅主管理员可执行）。
 */
import { ref } from 'vue'
import { supabase } from '../api/supabase'

// 默认开关：表不存在时的兜底（全部开放，内容公开可读）
const DEFAULT_FLAGS = {
  'fund-rank': true,
  signal: true,
  portfolio: true,
  content: true,
  'login-wall': true,   // 首页权限墙（默认开启=未登录需登录才能看）
}

// 可在面板中切换的功能清单（核心管理类 admin / data-center 不放入开关，避免把自己锁门外）
export const TOGGLEABLE_FEATURES = [
  { key: 'content', label: '内容（博客）', desc: '独立性研究文章，公开可读（无需登录）' },
  { key: 'signal', label: '信号', desc: '宏观信号、股债性价比、风格因子、行业估值' },
  { key: 'fund-rank', label: '工具', desc: '靠谱指数评分、基金详情、基金对比' },
  { key: 'portfolio', label: '组合', desc: '自建组合、AI 组合、组合回测' },
  { key: 'login-wall', label: '首页权限墙', desc: '开启后未登录用户必须登录才能访问网站；关闭后所有人可直接浏览（无需登录）' },
]

// 模块级单例：所有组件共享同一份 flags
const flags = ref({ ...DEFAULT_FLAGS })
const loaded = ref(false)

export function useFeatureFlags() {
  /** 从 feature_flags 表加载开关（失败回退默认，不抛错） */
  async function loadFeatureFlags() {
    if (!supabase) { loaded.value = true; return }
    try {
      const { data, error } = await supabase
        .from('feature_flags')
        .select('key, open')
        .limit(100)
      if (!error && Array.isArray(data)) {
        const map = { ...DEFAULT_FLAGS }
        for (const row of data) map[row.key] = !!row.open
        flags.value = map
      }
    } catch (e) {
      // 表不存在或网络异常：保留默认（全部开放）
    } finally {
      loaded.value = true
    }
  }

  /** 某功能当前是否全局开放（未配置视为开放） */
  function featureEnabled(key) {
    if (key == null) return true
    const v = flags.value[key]
    return v === undefined ? true : v
  }

  /** 管理员切换开关（走 SECURITY DEFINER RPC，服务端校验 57502460@qq.com） */
  async function setFeatureFlag(key, open) {
    if (!supabase) throw new Error('未连接数据库')
    const { error } = await supabase.rpc('set_feature_flag', { p_key: key, p_open: open })
    if (error) throw error
    flags.value = { ...flags.value, [key]: open }
  }

  return { flags, loaded, loadFeatureFlags, featureEnabled, setFeatureFlag }
}
