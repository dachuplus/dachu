/**
 * usePermissionRequests.js — 访问权限申请（陌生人 → 管理员审批）
 *
 * 流程：
 *  1. 陌生人登录后在登录墙点「申请权限」，填写真实姓名/手机号/补充信息，
 *     写入 permission_requests 表（status='pending'）。
 *  2. 管理员在「管理中心 → 用户管理 → 权限申请」看到待审批列表，
 *     通过后写入 user_permissions 并标记 approved，驳回标记 rejected。
 *
 * 仅依赖 supabase-js（anon key + 用户 JWT），RLS 控制行级权限：
 *  - 用户只能插入/查看自己的申请（auth.email() = user_email）
 *  - 仅管理员 57502460@qq.com 可读写全部申请
 */
import { ref } from 'vue'
import { supabase } from '../api/supabase'
import { useAuth } from './useAuth'

export function usePermissionRequests() {
  const { isOwner, user } = useAuth()
  const requests = ref([])
  const loading  = ref(false)

  /** 提交权限申请（任意已登录用户，写入自己的登录邮箱） */
  async function submitRequest({ realName, phone, extra }) {
    const email = user.value?.email
    if (!email) throw new Error('请先登录后再申请')
    const { error } = await supabase
      .from('permission_requests')
      .upsert({
        user_email: email,
        real_name:  realName || null,
        phone:      phone || null,
        extra:      extra || null,
        source:     'web',
        status:     'pending',
        created_at: new Date().toISOString(),
      }, { onConflict: 'user_email' })
    if (error) throw error
  }

  /** 管理员加载全部申请（按提交时间倒序） */
  async function loadRequests() {
    if (!isOwner.value) return
    loading.value = true
    try {
      const { data, error } = await supabase
        .from('permission_requests')
        .select('user_email, real_name, phone, extra, status, source, created_at, reviewed_by, reviewed_at')
        .order('created_at', { ascending: false })
      if (error) { requests.value = []; return }
      // 每条申请带一个功能勾选数组（审批通过时随 user_permissions 写入）
      requests.value = (data || []).map(r => ({ ...r, _saving: false, _features: [] }))
    } catch (e) {
      console.error('[perm-req] load error', e)
      requests.value = []
    } finally {
      loading.value = false
    }
  }

  /** 审批通过：写入 user_permissions 并标记申请 approved */
  async function approveRequest(row, features) {
    row._saving = true
    try {
      const { error: e1 } = await supabase
        .from('user_permissions')
        .upsert({
          user_email:       row.user_email,
          is_admin:         false,
          enabled_features: features || [],
          granted_by:       user.value?.email || null,
          updated_at:       new Date().toISOString(),
        }, { onConflict: 'user_email' })
      if (e1) throw e1
      const { error: e2 } = await supabase
        .from('permission_requests')
        .update({
          status:      'approved',
          reviewed_by: user.value?.email || null,
          reviewed_at: new Date().toISOString(),
        })
        .eq('user_email', row.user_email)
      if (e2) throw e2
      await loadRequests()
    } finally {
      row._saving = false
    }
  }

  /** 驳回申请：仅更新状态为 rejected */
  async function rejectRequest(row) {
    row._saving = true
    try {
      const { error } = await supabase
        .from('permission_requests')
        .update({
          status:      'rejected',
          reviewed_by: user.value?.email || null,
          reviewed_at: new Date().toISOString(),
        })
        .eq('user_email', row.user_email)
      if (error) throw error
      await loadRequests()
    } finally {
      row._saving = false
    }
  }

  return { requests, loading, submitRequest, loadRequests, approveRequest, rejectRequest }
}
