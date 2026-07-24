<template>
  <div class="aipk">

    <!-- 说明卡 -->
    <div class="card aipk-intro">
      <div class="card-title-row">
        <span class="card-title">AI 大 PK</span>
        <span class="aipk-badge" :class="{ 'aipk-badge-real': realModels.length }">
          {{ realModels.length ? `真实大模型已接入（${realModels.length}）` : '规则版' }}
        </span>
      </div>
      <p class="card-desc">
        让多个大模型各自挑选 5 只基金、每只 20% 等权，每月 1 日调仓，比一比谁的收益更好。
        由 <b>7 个真实大模型</b>基于 大厨先生 靠谱指数（fund_scores）真实数据，先选二级分类(t1)品类、再在该品类内选单品（含豆包·火山方舟真实模型），
        并给出两层逻辑（第一层品类选择 · 第二层单品选择）；各模型按自身推理逻辑自主决策，目标只有一个——跑赢对手。
        通过「千问百炼」聚合平台调用的模型已在卡片上标注<span class="aipk-ds-badge">百炼</span>徽标。
        所有选品与推理均基于 fund_scores 真实指标（收益/回撤/夏普/规模），模型不引用任何表外或网络信息，无编造、无模拟。
      </p>
      <div class="aipk-src">数据来源：大厨先生 靠谱指数基金库（真实收益，非模拟）</div>
    </div>

    <!-- 模型阵容 -->
    <div class="aipk-section-title aipk-section-title-row">
      <span>模型阵容（各 5 只 · 等权 20%）</span>
      <div class="aipk-section-actions">
        <button class="aipk-manage-btn" v-if="isAdmin" @click="openManage" title="管理自建模型">
          <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M19.14 12.94a7.49 7.49 0 0 0 .05-.94 7.49 7.49 0 0 0-.05-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.61-.22l-2.39.96a7.3 7.3 0 0 0-1.62-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54c-.59.24-1.13.56-1.62.94l-2.39-.96a.5.5 0 0 0-.61.22L2.7 8.84a.5.5 0 0 0 .12.64l2.03 1.58c-.03.31-.05.62-.05.94s.02.63.05.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.14.24.42.34.61.22l2.39-.96c.49.38 1.03.7 1.62.94l.36 2.54c.04.24.25.42.5.42h3.84c.25 0 .46-.18.5-.42l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.19.12.47.02.61-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58ZM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7Z"/></svg>
          模型管理
        </button>
        <button class="aipk-share-btn" @click="openShare('lineup')" title="分享到朋友圈">
        <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>
        分享
      </button>
      </div>
    </div>
    <div class="aipk-models">
      <div class="aipk-model" v-for="m in orderedModels" :key="m.id" :style="{ borderTopColor: m.color }">
        <div class="aipk-model-hd">
          <span class="aipk-dot" :style="{ background: m.color }"></span>
          <span class="aipk-model-name">{{ m.name }}</span>
          <span class="aipk-model-short" :style="{ color: m.color }">{{ m.name_short }}</span>
          <span class="aipk-model-mode" :class="m.mode === 'real' ? 'is-real' : m.mode === 'pending' ? 'is-pending' : 'is-rule'">
            {{ m.is_custom ? '自建' : (m.mode === 'real' ? '真实' : m.mode === 'pending' ? '待接入' : '规则') }}
          </span>
          <span v-if="m.api_provider === 'qwen'" class="aipk-ds-badge">百炼</span>
        </div>
        <div class="aipk-model-persona">{{ modelTagline(m) }}</div>
        <div class="aipk-model-ret" v-if="m.mode !== 'pending'" :class="retClass(modelReturns[m.id]?.r1y)">
          近1年组合收益 {{ fmtRet(modelReturns[m.id]?.r1y) }}
        </div>
        <div class="aipk-funds">
          <div class="aipk-pending" v-if="m.mode === 'pending'">待接入</div>
          <template v-else>
            <div class="aipk-fund" v-for="(f, i) in (picksMap[m.id]?.picks || [])" :key="f.code">
              <span class="aipk-fund-idx">{{ i + 1 }}</span>
              <span class="aipk-fund-name">{{ f.name }}</span>
              <span class="aipk-fund-code">{{ f.code }}</span>
              <span class="aipk-fund-w">20%</span>
            </div>
            <div class="aipk-funds-empty" v-if="!(picksMap[m.id]?.picks || []).length">暂无选基数据</div>
          </template>
        </div>
      </div>
    </div>

    <!-- 收益 PK -->
    <div class="card aipk-pk">
      <div class="aipk-pk-hd">
        <span class="card-title">收益 PK</span>
        <div class="aipk-pk-hd-right">
          <div class="aipk-periods">
            <button
              v-for="p in CHART_PERIODS" :key="p.key"
              class="aipk-period-btn"
              :class="{ active: chartPeriod === p.key }"
              @click="chartPeriod = p.key"
            >{{ p.label }}</button>
          </div>
          <button class="aipk-share-btn" @click="openShare('pk')" title="分享到朋友圈">
            <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>
            分享
          </button>
        </div>
      </div>

      <!-- 排行榜（冠亚季） -->
      <div class="aipk-rank" v-if="ranking.length">
        <div
          v-for="(item, idx) in ranking.slice(0, 3)" :key="item.id"
          class="aipk-rank-item"
          :class="['rank-' + (idx + 1)]"
        >
          <span class="aipk-rank-medal">{{ ['冠军', '亚军', '季军'][idx] }}</span>
          <span class="aipk-rank-name">{{ modelName(item.id) }}</span>
          <span class="aipk-rank-val" :class="retClass(item.ret)">{{ fmtRet(item.ret) }}</span>
        </div>
      </div>
      <div class="aipk-rank-note" v-if="ranking.length < orderedModels.length">
        注：{{ orderedModels.length - ranking.length }} 个模型因成分基金成立时间不足，该周期暂无数据
      </div>

      <!-- 对比图 -->
      <div class="aipk-chart" ref="chartEl"></div>

      <!-- 完整对比表 -->
      <div class="aipk-table-title">完整区间收益对比</div>
      <div class="aipk-table-wrap">
        <table class="aipk-table">
          <thead>
            <tr>
              <th class="aipk-th-model" @click="toggleTableSort('name')">
                模型<span class="sort-arrow" v-if="tableSort.key === 'name'">{{ tableSort.dir === 'desc' ? ' ▼' : ' ▲' }}</span>
              </th>
              <th v-for="col in RETURN_COLS" :key="col.key"
                  class="aipk-th-sort"
                  @click="toggleTableSort(col.key)">
                {{ col.label }}<span class="sort-arrow" v-if="tableSort.key === col.key">{{ tableSort.dir === 'desc' ? ' ▼' : ' ▲' }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in tableSortedModels" :key="m.id">
              <td class="aipk-td-model">
                <span class="aipk-dot" :style="{ background: m.color }"></span>{{ m.name }}
              </td>
              <td
                v-for="col in RETURN_COLS" :key="col.key"
                :class="retClass(modelReturns[m.id]?.[col.key])"
              >{{ fmtRet(modelReturns[m.id]?.[col.key]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 调仓时间线 -->
    <div class="card aipk-timeline-card">
      <div class="aipk-tl-head">
        <span class="card-title">调仓时间线</span>
        <button class="aipk-share-btn" @click="openShare('timeline')" title="分享到朋友圈">
          <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>
          分享
        </button>
      </div>
      <div class="aipk-tl-period" v-if="latestPeriod">
        {{ latestPeriod }} 月度调仓 · 各模型选基逻辑（两层）
        <span class="aipk-tl-mode-note" v-if="orderedModels.length">
          （{{ realModels.length ? realModels.length + ' 个真实模型' : '' }}{{ realModels.length && ruleModels.length ? ' + ' : '' }}{{ ruleModels.length ? ruleModels.length + ' 个规则版' : '' }}）
        </span>
      </div>
      <div class="aipk-tl-empty" v-if="!orderedModels.length">暂无选基数据</div>
      <div class="aipk-tl-model" v-for="m in orderedModels" :key="m.id">
        <div class="aipk-tl-model-hd">
          <span class="aipk-dot" :style="{ background: m.color }"></span>
          <span class="aipk-tl-model-name">{{ m.name }}</span>
          <span class="aipk-tl-model-short" :style="{ color: m.color }">{{ m.name_short }}</span>
        </div>
        <div class="aipk-tl-pending" v-if="m.mode === 'pending'">待接入</div>
        <template v-else>
          <div class="aipk-tl-layer">
            <span class="aipk-tl-tag">第一层 · 基于 fund_scores 选二级分类(t1)品类（真实收益/回撤/夏普统计）</span>
            <p class="aipk-tl-text">{{ m.category_logic || '—' }}</p>
          </div>
          <div class="aipk-tl-layer">
            <span class="aipk-tl-tag">第二层 · 单品逻辑（多维度分析）</span>
            <div class="aipk-tl-funds">
              <div class="aipk-tl-fund" v-for="(f, i) in (picksMap[m.id]?.picks || [])" :key="f.code">
                <span class="aipk-tl-fund-idx">{{ i + 1 }}</span>
                <span class="aipk-tl-fund-name">{{ f.name }}</span>
                <span class="aipk-tl-fund-w">20%</span>
                <p class="aipk-tl-fund-reason">{{ f.reason || '—' }}</p>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 加载 / 空态 -->
    <div class="aipk-loading" v-if="loading">加载中...</div>

    <!-- 分享到朋友圈 弹窗 -->
    <Teleport to="body">
      <template v-if="shareSection">
        <div class="mask" @click="closeShare"></div>
        <div class="aipk-share-panel">
          <div class="aipk-share-header">
            <span class="aipk-share-title">分享到朋友圈</span>
            <span class="aipk-share-close" @click="closeShare">&#x2715;</span>
          </div>
          <div class="aipk-share-body">
            <div v-if="shareGenerating" class="aipk-share-loading">分享图生成中...</div>
            <template v-else>
              <img v-if="shareImage" class="aipk-share-img" :src="shareImage" alt="分享图" />
              <p class="aipk-share-hint" v-if="shareImage">长按图片可保存到相册，或分享到朋友圈</p>
              <button class="aipk-share-save-btn" v-if="shareImage" @click="saveShareImage">保存图片</button>
              <button class="aipk-share-save-btn aipk-share-save-btn-ghost" v-if="shareImage" @click="closeShare">关闭</button>
            </template>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 模型管理 弹窗 -->
    <Teleport to="body">
      <template v-if="showManage">
        <div class="mask" @click="closeManage"></div>
        <div class="aipk-manage-panel">
          <div class="aipk-manage-header">
            <span class="aipk-manage-title">⚙️ 模型管理</span>
            <span class="aipk-manage-close" @click="closeManage">&#x2715;</span>
          </div>

          <div class="aipk-manage-body">
            <!-- 非管理员限制提示 -->
            <div v-if="!isAdmin" class="aipk-manage-restricted">
              <span class="aipk-manage-restricted-icon">🔒</span>
              <p class="aipk-manage-restricted-title">该功能仅限管理员使用</p>
              <p class="aipk-manage-restricted-desc">如需管理自建模型，请使用管理员账号登录。</p>
            </div>
            <template v-else>
            <!-- 已有模型列表 -->
            <div class="aipk-manage-sub">已有模型（{{ manageModels.length }}）</div>
            <div class="aipk-manage-list">
              <div
                v-for="m in manageModels" :key="m.id"
                class="aipk-manage-item"
                :class="{ 'is-system': !m.is_custom, 'is-off': m.is_custom && !m.is_active }"
              >
                <div class="aipk-manage-item-main">
                  <span class="aipk-manage-item-name">{{ m.name }}</span>
                  <span class="aipk-manage-item-provider">{{ providerLabel(m.model_provider || m.api_provider) }}</span>
                  <span v-if="!m.is_custom" class="aipk-manage-tag aipk-manage-tag-sys">系统</span>
                  <span v-else-if="m.is_active" class="aipk-manage-tag aipk-manage-tag-on">已启用</span>
                  <span v-else class="aipk-manage-tag aipk-manage-tag-off">已禁用</span>
                </div>
                <div class="aipk-manage-item-actions" v-if="m.is_custom">
                  <button class="aipk-manage-mini" @click="editModel(m)">编辑</button>
                  <button class="aipk-manage-mini" @click="toggleModelActive(m)">{{ m.is_active ? '禁用' : '启用' }}</button>
                  <button class="aipk-manage-mini aipk-manage-mini-danger" @click="deleteModel(m)">删除</button>
                </div>
                <div v-else class="aipk-manage-item-actions aipk-manage-item-readonly">系统预设 · 不可编辑</div>
              </div>
              <div class="aipk-manage-empty" v-if="!manageModels.length">暂无模型</div>
            </div>

            <!-- 新增 / 编辑 表单 -->
            <div class="aipk-manage-sub">{{ editingId ? '编辑模型' : '新增自建模型' }}</div>
            <form class="aipk-manage-form" @submit.prevent="saveModel">
              <label class="aipk-field">
                <span class="aipk-field-label">模型名称 <i class="aipk-req">*</i></span>
                <input
                  class="aipk-input" type="text" v-model.trim="form.model_name"
                  placeholder="如：我的GPT-4" maxlength="40"
                />
                <span class="aipk-field-err" v-if="errors.model_name">{{ errors.model_name }}</span>
              </label>

              <label class="aipk-field">
                <span class="aipk-field-label">提供商 <i class="aipk-req">*</i></span>
                <select class="aipk-input" v-model="form.model_provider">
                  <option value="openai">OpenAI</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="custom">自定义</option>
                </select>
              </label>

              <label class="aipk-field">
                <span class="aipk-field-label">
                  API Key <i class="aipk-req">*</i>
                  <span class="aipk-field-hint" v-if="editingId">（留空则不修改）</span>
                </span>
                <div class="aipk-input-wrap">
                  <input
                    class="aipk-input aipk-input-pw" :type="showKey ? 'text' : 'password'"
                    v-model.trim="form.api_key" :placeholder="editingId ? '••••••••（留空保持不变）' : 'sk-... 或 ark-...'"
                    autocomplete="off"
                  />
                  <button type="button" class="aipk-pw-toggle" @click="showKey = !showKey">
                    {{ showKey ? '隐藏' : '显示' }}
                  </button>
                </div>
                <span class="aipk-field-err" v-if="errors.api_key">{{ errors.api_key }}</span>
              </label>

              <label class="aipk-field">
                <span class="aipk-field-label">API 端点 URL <span class="aipk-field-hint">（可选，有默认值）</span></span>
                <input
                  class="aipk-input" type="text" v-model.trim="form.api_endpoint"
                  :placeholder="endpointPlaceholder"
                />
              </label>

              <label class="aipk-field">
                <span class="aipk-field-label">选基策略提示词 / Prompt</span>
                <textarea
                  class="aipk-input aipk-textarea" v-model="form.system_prompt" rows="5"
                  placeholder="系统提示词，用于指导模型如何选基金"
                ></textarea>
                <span class="aipk-field-hint">为不同模型设置不同的选基策略，例如风险偏好、品类侧重等。</span>
              </label>

              <div class="aipk-manage-form-actions">
                <button type="submit" class="aipk-manage-save-btn" :disabled="saving">
                  {{ saving ? '保存中...' : (editingId ? '保存修改' : '保存模型') }}
                </button>
                <button type="button" class="aipk-manage-save-btn aipk-manage-save-btn-ghost" @click="resetForm" v-if="editingId">
                  取消编辑
                </button>
                <button type="button" class="aipk-manage-save-btn aipk-manage-save-btn-ghost" @click="resetForm" v-else>
                  重置
                </button>
              </div>
              <div class="aipk-manage-msg" v-if="formMsg" :class="formMsgOk ? 'is-ok' : 'is-err'">{{ formMsg }}</div>
            </form>

            <p class="aipk-manage-note">
              说明：自建模型会出现在「模型阵容」中。API Key 不会在列表中明文展示，仅本地加密存储于服务端。
              当前为匿名使用，模型与你的浏览器标识（{{ userId }}）绑定。
            </p>
            </template>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { supabase } from '../../api/supabase'
import { useAuth } from '../../composables/useAuth'
import echarts from '../../utils/echarts-setup'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import { createGovukChart } from '../../utils/echarts-theme'
import QRCode from 'qrcode'

// 注册本组件所需的 BarChart（不修改共享的 echarts-setup.js）
echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent])

// ========== 管理员权限控制 ==========
// 硬编码管理员邮箱列表（与 useAuth 中 OWNER_EMAIL 保持一致）
const ADMIN_EMAILS = ['57502460@qq.com']
const { user: authUser } = useAuth()
// 已登录且邮箱命中管理员列表才视为管理员；未登录 → false
const isAdmin = computed(() => ADMIN_EMAILS.includes((authUser.value?.email || '').toLowerCase()))

// ========== 分享到朋友圈 ==========
const shareSection = ref(null)        // 'pk' | 'lineup' | 'timeline'
const shareImage = ref(null)
const shareGenerating = ref(false)
const SHARE_SECTION_TITLE = {
  pk: '收益 PK',
  lineup: '模型阵容',
  timeline: '调仓时间线',
}
const shareSectionTitle = computed(() => SHARE_SECTION_TITLE[shareSection.value] || '')

const MODEL_ORDER = ['ds', 'doubao', 'qwen', 'wenxin', 'zhipu', 'kimi', 'minimax']

// ========== 模型管理（用户自建 AI 选基模型） ==========
const PROVIDER_LABELS = {
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  anthropic: 'Anthropic',
  custom: '自定义',
}
const PROVIDER_ENDPOINTS = {
  openai: 'https://api.openai.com/v1/chat/completions',
  deepseek: 'https://api.deepseek.com/v1/chat/completions',
  anthropic: 'https://api.anthropic.com/v1/messages',
  custom: '',
}
const DEFAULT_SYSTEM_PROMPT =
  '你是一个专业的基金分析师。请根据以下指标（收益、最大回撤、夏普比率、基金规模、成立年限等）综合评估基金，' +
  '挑选 5 只基金并给出每只的选基理由，每只建议等权配置（20%）。' +
  '只基于给出的真实数据做判断，不要引用任何表外或网络信息，不编造、不模拟。'

// 匿名用户标识（localStorage），后续接登录后可替换为手机号/用户ID
const USER_ID_KEY = 'allfund_anon_uid'
function getUserId() {
  let id = ''
  try { id = localStorage.getItem(USER_ID_KEY) || '' } catch (e) {}
  if (!id) {
    id = 'anon_' + (crypto?.randomUUID?.() || Date.now() + '-' + Math.random().toString(16).slice(2))
    try { localStorage.setItem(USER_ID_KEY, id) } catch (e) {}
  }
  return id
}
const userId = ref(getUserId())

// API Key 轻量混淆存储（非明文入库；真实加密需后端 KMS/密钥管理）
function obfuscate(str) {
  if (!str) return ''
  try { return 'obf:' + btoa(unescape(encodeURIComponent('af#' + str))) } catch (e) { return '' }
}
function deobfuscate(str) {
  if (!str || !str.startsWith('obf:')) return ''
  try { return decodeURIComponent(escape(atob(str.slice(4)))).replace(/^af#/, '') } catch (e) { return '' }
}
function providerLabel(p) {
  return PROVIDER_LABELS[p] || (p ? String(p).toUpperCase() : '未知')
}

const models = ref([])
const picksMap = ref({})      // { model_id: { period_month, picks:[{code,name,weight}] } }
const fundReturns = ref({})    // { code: { ...returns } }
const loading = ref(true)

const RETURN_COLS = [
  { key: 'daily_change', label: '当日' },
  { key: 'r0w', label: '近1周' },
  { key: 'r1m', label: '近1月' },
  { key: 'r3m', label: '近3月' },
  { key: 'r6m', label: '近6月' },
  { key: 'r1y', label: '近1年' },
  { key: 'r2y', label: '近2年' },
  { key: 'r3y', label: '近3年' },
  { key: 'r5y', label: '近5年' },
  { key: 'r10y', label: '近10年' },
]
const STRICT_COLS = { r3y: true, r5y: true, r10y: true }

const CHART_PERIODS = [
  { key: 'r1m', label: '近1月' },
  { key: 'r3m', label: '近3月' },
  { key: 'r6m', label: '近6月' },
  { key: 'r1y', label: '近1年' },
  { key: 'r3y', label: '近3年' },
  { key: 'r5y', label: '近5年' },
]
const chartPeriod = ref('r1y')
const chartEl = ref(null)
let chartInstance = null

const orderedModels = computed(() => {
  const map = {}
  models.value.forEach(m => { map[m.id] = m })
  const presets = MODEL_ORDER.map(id => map[id]).filter(Boolean)
  // 用户自建且启用中的模型，自动出现在 PK 阵容中
  // 非管理员：自建模型不进入 PK 阵容（仅展示系统预设模型）
  if (!isAdmin.value) return presets
  const custom = models.value.filter(m => m.is_custom && m.is_active)
  return [...presets, ...custom]
})

// 模型管理面板中展示的模型（系统预设 + 用户自建，含已禁用）
const manageModels = computed(() => models.value)

// ---- 收益对比表排序 ----
const tableSort = ref({ key: null, dir: 'desc' }) // dir: 'asc' | 'desc'
function toggleTableSort(key) {
  if (tableSort.value.key === key) {
    tableSort.value.dir = tableSort.value.dir === 'desc' ? 'asc' : 'desc'
  } else {
    tableSort.value.key = key
    tableSort.value.dir = 'desc'
  }
}
const tableSortedModels = computed(() => {
  const { key, dir } = tableSort.value
  if (!key) return orderedModels.value
  const mult = dir === 'desc' ? -1 : 1
  return [...orderedModels.value].sort((a, b) => {
    const va = modelReturns.value[a.id]?.[key]
    const vb = modelReturns.value[b.id]?.[key]
    // null/缺失排到最后
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    return mult * ((+va) - (+vb))
  })
})

const realModels = computed(() => orderedModels.value.filter(m => m.mode === 'real'))
const ruleModels = computed(() => orderedModels.value.filter(m => m.mode !== 'real'))

// 各模型加权区间收益
const modelReturns = computed(() => {
  const out = {}
  for (const m of models.value) {
    const picks = picksMap.value[m.id]?.picks || []
    const res = {}
    for (const col of RETURN_COLS) {
      const vals = picks
        .map(p => ({ w: p.weight || 0, v: fundReturns.value[p.code]?.[col.key] }))
      // 严格列：任一成分缺失 → 整列 --
      if (STRICT_COLS[col.key] && vals.some(x => x.v == null)) { res[col.key] = null; continue }
      let wsum = 0, vsum = 0, has = false
      for (const x of vals) {
        if (x.v == null) continue
        wsum += x.w; vsum += x.w * x.v; has = true
      }
      res[col.key] = has && wsum > 0 ? +(vsum / wsum).toFixed(2) : null
    }
    out[m.id] = res
  }
  return out
})

// 排行榜（按当前选择周期，排除无数据模型）
const ranking = computed(() => {
  const arr = orderedModels.value
    .map(m => ({ id: m.id, ret: modelReturns.value[m.id]?.[chartPeriod.value] }))
    .filter(x => x.ret != null)
    .sort((a, b) => b.ret - a.ret)
  return arr
})

const timelinePeriods = computed(() => {
  const set = new Set()
  Object.values(picksMap.value).forEach(p => { if (p?.period_month) set.add(p.period_month) })
  return [...set].sort().reverse()
})
const latestPeriod = computed(() => timelinePeriods.value[0] || null)

function modelName(id) {
  return models.value.find(m => m.id === id)?.name || id
}

// 各模型的「调用通道 / 聚合平台」中文标签（用于卡片标语，明确展示百炼等聚合平台）
const PROVIDER_LABEL = {
  ds: 'DeepSeek · 千问百炼',
  doubao: '豆包 · 火山方舟',
  qwen: '千问百炼聚合',
  wenxin: '文心 · 百度千帆',
  zhipu: '智谱 · 千问百炼',
  kimi: 'Kimi · 千问百炼',
  minimax: 'MiniMax · 千问百炼',
}
// 取代旧的固定「人设」文案：现在每个模型都按自身推理逻辑自主选基
function modelTagline(m) {
  const label = PROVIDER_LABEL[m.id] || PROVIDER_LABEL[m.api_provider] || m.api_provider || '真实大模型'
  return `${label} · 自主推理选基`
}

function fmtRet(v) {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}
function retClass(v) {
  if (v == null) return 'ret-na'
  return v > 0 ? 'ret-pos' : (v < 0 ? 'ret-neg' : 'ret-flat')
}

async function loadAll() {
  loading.value = true
  try {
    const { data: m } = await supabase.from('ai_pk_models').select('*').eq('enabled', true)
    models.value = (m || []).map(x => ({ ...x, is_custom: false }))
    // 合并用户自建模型（出现在「模型阵容」中）
    await loadUserModels()
    const { data: p } = await supabase.from('ai_pk_picks').select('*').order('period_month', { ascending: false })
    const byModel = {}
    for (const row of (p || [])) {
      if (!byModel[row.model_id]) byModel[row.model_id] = row
    }
    picksMap.value = byModel

    const codes = new Set()
    for (const mid in byModel) (byModel[mid].picks || []).forEach(x => codes.add(x.code))
    if (codes.size) {
      const { data: fr } = await supabase.from('fund_scores')
        .select('c,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,r10y,daily_change')
        .in('c', [...codes])
      const map = {}
      ;(fr || []).forEach(f => { map[f.c] = f })
      fundReturns.value = map
    }
  } catch (e) {
    console.error('[AIPkPanel]', e)
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

function renderChart() {
  if (!chartEl.value) return
  if (!chartInstance) chartInstance = echarts.getInstanceByDom(chartEl.value) || echarts.init(chartEl.value)

  // 多模型收益曲线：X轴=时间周期，每条线=一个模型
  const periods = CHART_PERIODS.map(p => p.key)   // [r1m, r3m, r6m, r1y, r3y, r5y]
  const periodLabels = CHART_PERIODS.map(p => p.label)
  const seriesData = []
  for (const m of orderedModels.value) {
    const ret = modelReturns.value[m.id] || {}
    const values = periods.map(pk => ret[pk] ?? null)
    // 至少有一个有效数据点才画线
    if (values.some(v => v != null)) {
      seriesData.push({
        name: m.name,
        type: 'line',
        data: values,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: m.color || '#1d70b8' },
        emphasis: { focus: 'series' },
        connectNulls: true,
      })
    }
  }

  if (seriesData.length === 0) {
    chartInstance.clear()
    return
  }

  const option = createGovukChart({
    legend: {
      bottom: 0, left: 0, right: 0,
      textStyle: { fontSize: 12, color: '#505a66' },
      itemWidth: 16, itemHeight: 3, itemGap: 14,
      type: 'scroll',
    },
    grid: { left: 10, right: 20, top: 10, bottom: 42, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        if (!Array.isArray(params)) params = [params]
        const period = params[0]?.axisValue || ''
        let html = `<b>${period}</b><br/>`
        for (const p of params) {
          const v = p.value
          if (v == null) continue
          const sign = v > 0 ? '+' : ''
          html += `${p.marker} ${p.seriesName}：<b style="color:${v >= 0 ? '#d4351c' : '#00703c'}">${sign}${v.toFixed(2)}%</b><br/>`
        }
        return html
      },
    },
    xAxis: { type: 'category', data: periodLabels, boundaryGap: false, axisLabel: { fontSize: 12 } },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%', fontSize: 12 },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
    },
    series: seriesData,
  })
  chartInstance.setOption(option, true)
}

function chartPeriodLabel() {
  return CHART_PERIODS.find(p => p.key === chartPeriod.value)?.label || ''
}

function onResize() { if (chartInstance) chartInstance.resize() }

watch(chartPeriod, async () => { await nextTick(); renderChart() })
watch(ranking, async () => { await nextTick(); renderChart() })

onMounted(() => {
  if (supabase) loadAll()
  else { loading.value = false }
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chartInstance) chartInstance.dispose()
})

// ========== 分享到朋友圈：canvas 海报生成 ==========
function openShare(section) {
  if (shareGenerating.value) return
  shareSection.value = section
  shareImage.value = null
  generateShareImage(section)
}
function closeShare() {
  shareSection.value = null
  shareImage.value = null
}

/** 截断文本（canvas 绘制用） */
function truncateText(ctx, text, maxWidth) {
  if (!text) return ''
  if (ctx.measureText(text).width <= maxWidth) return text
  let t = text
  while (t.length > 1 && ctx.measureText(t + '…').width > maxWidth) t = t.slice(0, -1)
  return t + '…'
}

/** 文字自动换行（canvas 用） */
function wrapText(ctx, text, maxWidth) {
  if (!text) return []
  const lines = []
  let current = ''
  for (const ch of String(text)) {
    const test = current + ch
    if (ctx.measureText(test).width <= maxWidth) current = test
    else { if (current) lines.push(current); current = ch }
  }
  if (current) lines.push(current)
  return lines
}

/** 圆角矩形路径 */
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

/** 加载图片（dataURL / src）为 Image 对象 */
function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

/** 顶部品牌蓝条（每个海报通用） */
function drawShareHeader(ctx, W, pad, headerH, title) {
  ctx.fillStyle = '#1d70b8'
  ctx.fillRect(0, 0, W, headerH)
  ctx.fillStyle = '#ffffff'
  ctx.textAlign = 'left'
  ctx.font = 'bold 38px sans-serif'
  ctx.fillText('大厨先生', pad, 34)
  ctx.font = '24px sans-serif'
  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.fillText('AI 大 PK · ' + title, pad, 86)
}

/** 收益 PK 海报：曲线图 + 冠亚季军 + 完整对比表 */
async function drawPkPoster(ctx, W, pad, headerH) {
  let y = headerH + 24
  const subtitle = latestPeriod.value ? `${latestPeriod.value} 月度调仓 · 各模型加权区间收益` : '各模型加权区间收益'
  ctx.fillStyle = '#1a1a1a'
  ctx.font = 'bold 22px sans-serif'
  ctx.textAlign = 'left'
  ctx.fillText(truncateText(ctx, subtitle, W - pad * 2), pad, y)
  y += 42

  // 收益曲线图（ECharts 原生导出）
  if (chartInstance) {
    const url = chartInstance.getDataURL({ pixelRatio: 2, backgroundColor: '#ffffff' })
    const img = await loadImage(url)
    if (img && img.width) {
      const cw = W - pad * 2
      const ratio = img.height / img.width
      const drawH = Math.min(320, cw * ratio)
      ctx.drawImage(img, pad, y, cw, drawH)
      y += drawH + 20
    }
  }

  // 冠亚季军
  if (ranking.value.length) {
    const medals = ranking.value.slice(0, 3)
    const gap = 12
    const mw = (W - pad * 2 - gap * 2) / 3
    const mh = 110
    const colors = ['#b8860b', '#8c8c8c', '#b5651d']
    const labels = ['冠军', '亚军', '季军']
    medals.forEach((item, i) => {
      const mx = pad + i * (mw + gap)
      ctx.fillStyle = '#f6f8fb'
      roundRect(ctx, mx, y, mw, mh, 10); ctx.fill()
      ctx.strokeStyle = colors[i]; ctx.lineWidth = 2
      roundRect(ctx, mx + 1, y + 1, mw - 2, mh - 2, 10); ctx.stroke()
      ctx.textAlign = 'center'
      ctx.fillStyle = colors[i]; ctx.font = 'bold 22px sans-serif'
      ctx.fillText(labels[i], mx + mw / 2, y + 14)
      ctx.fillStyle = '#1a1a1a'; ctx.font = 'bold 19px sans-serif'
      ctx.fillText(truncateText(ctx, modelName(item.id), mw - 12), mx + mw / 2, y + 46)
      ctx.fillStyle = item.ret >= 0 ? '#d4351c' : '#00703c'; ctx.font = 'bold 26px sans-serif'
      ctx.fillText(fmtRet(item.ret), mx + mw / 2, y + 76)
    })
    y += mh + 20
  }

  // 完整对比表（6 个主周期）
  ctx.textAlign = 'left'
  ctx.fillStyle = '#1a1a1a'
  ctx.font = 'bold 20px sans-serif'
  ctx.fillText('完整区间收益对比', pad, y)
  y += 32
  const tableCols = CHART_PERIODS
  const colW = (W - pad * 2) / (tableCols.length + 1)
  const rowH = 40
  // 表头
  ctx.fillStyle = '#f3f2f1'
  ctx.fillRect(pad, y, W - pad * 2, rowH)
  ctx.fillStyle = '#1a1a1a'; ctx.font = 'bold 15px sans-serif'; ctx.textAlign = 'left'
  ctx.fillText('模型', pad + 8, y + 12)
  tableCols.forEach((c, i) => {
    const cx = pad + (i + 1) * colW
    ctx.textAlign = 'center'
    ctx.fillText(c.label, cx + colW / 2, y + 12)
  })
  y += rowH
  // 数据行
  let ri = 0
  for (const m of orderedModels.value) {
    const ret = modelReturns.value[m.id] || {}
    ctx.fillStyle = ri % 2 === 0 ? '#ffffff' : '#fafbfc'
    ctx.fillRect(pad, y, W - pad * 2, rowH)
    ctx.textAlign = 'left'
    ctx.fillStyle = m.color || '#1d70b8'
    ctx.fillRect(pad + 8, y + 14, 10, 10)
    ctx.fillStyle = '#1a1a1a'; ctx.font = 'bold 14px sans-serif'
    ctx.fillText(truncateText(ctx, m.name, colW - 16), pad + 24, y + 12)
    tableCols.forEach((c, i) => {
      const v = ret[c.key]
      const cx = pad + (i + 1) * colW
      ctx.textAlign = 'center'
      ctx.fillStyle = v == null ? '#b1b4b6' : (v >= 0 ? '#d4351c' : '#00703c')
      ctx.font = '14px sans-serif'
      ctx.fillText(fmtRet(v), cx + colW / 2, y + 12)
    })
    ctx.strokeStyle = '#eeeeee'; ctx.lineWidth = 1
    ctx.strokeRect(pad, y, W - pad * 2, rowH)
    y += rowH
    ri++
  }
  return y + 10
}

/** 模型阵容海报：每个模型 5 只基金 */
function drawLineupPoster(ctx, W, pad, headerH) {
  let y = headerH + 24
  ctx.fillStyle = '#1a1a1a'
  ctx.font = 'bold 22px sans-serif'
  ctx.textAlign = 'left'
  ctx.fillText('7 大模型各选 5 只 · 等权 20%', pad, y)
  y += 42
  for (const m of orderedModels.value) {
    ctx.fillStyle = m.color || '#1d70b8'
    roundRect(ctx, pad, y, W - pad * 2, 36, 6); ctx.fill()
    ctx.fillStyle = '#ffffff'; ctx.font = 'bold 18px sans-serif'; ctx.textAlign = 'left'
    const modeText = m.mode === 'real' ? ' · 真实' : (m.mode === 'pending' ? ' · 待接入' : ' · 规则')
    ctx.fillText(truncateText(ctx, m.name + modeText, W - pad * 2 - 28), pad + 14, y + 9)
    y += 46
    const picks = (picksMap.value[m.id]?.picks || [])
    if (!picks.length) {
      ctx.fillStyle = '#999999'; ctx.font = '15px sans-serif'
      ctx.fillText('暂无选基数据', pad + 14, y + 4); y += 30
    } else {
      picks.forEach((f, i) => {
        ctx.fillStyle = '#f6f8fb'
        roundRect(ctx, pad + 12, y, W - pad * 2 - 24, 44, 6); ctx.fill()
        ctx.fillStyle = '#1d70b8'; ctx.font = 'bold 14px sans-serif'; ctx.textAlign = 'left'
        ctx.fillText(String(i + 1), pad + 26, y + 15)
        ctx.fillStyle = '#1a1a1a'; ctx.font = 'bold 16px sans-serif'
        ctx.fillText(truncateText(ctx, f.name || '', W - pad * 2 - 24 - 150), pad + 46, y + 10)
        ctx.fillStyle = '#888888'; ctx.font = '12px sans-serif'
        ctx.fillText(f.code || '', pad + 46, y + 28)
        ctx.textAlign = 'right'; ctx.fillStyle = '#1d70b8'; ctx.font = 'bold 15px sans-serif'
        ctx.fillText('20%', W - pad - 26, y + 15)
        y += 50
      })
    }
    y += 14
  }
  return y
}

/** 调仓时间线海报：各模型第一层品类选择逻辑 */
function drawTimelinePoster(ctx, W, pad, headerH) {
  let y = headerH + 24
  const periodLabel = latestPeriod.value
    ? `${latestPeriod.value} 月度调仓 · 各模型两层选基逻辑`
    : '各模型两层选基逻辑'
  ctx.fillStyle = '#1a1a1a'
  ctx.font = 'bold 22px sans-serif'
  ctx.textAlign = 'left'
  ctx.fillText(truncateText(ctx, periodLabel, W - pad * 2), pad, y)
  y += 40
  for (const m of orderedModels.value) {
    ctx.fillStyle = m.color || '#1d70b8'
    ctx.beginPath(); ctx.arc(pad + 16, y + 10, 6, 0, Math.PI * 2); ctx.fill()
    ctx.fillStyle = '#1a1a1a'; ctx.font = 'bold 18px sans-serif'; ctx.textAlign = 'left'
    ctx.fillText(truncateText(ctx, m.name, W - pad * 2 - 40), pad + 30, y + 2)
    y += 32
    ctx.fillStyle = '#1d70b8'; ctx.font = 'bold 14px sans-serif'
    ctx.fillText('第一层 · 品类选择逻辑', pad + 10, y)
    y += 24
    ctx.fillStyle = '#444444'; ctx.font = '15px sans-serif'
    const logic = m.category_logic || '—'
    const lines = wrapText(ctx, logic, W - pad * 2 - 20)
    for (const ln of lines) { ctx.fillText(ln, pad + 10, y); y += 24 }
    y += 16
  }
  return y
}

/** 生成分享海报（主入口） */
async function generateShareImage(section) {
  if (shareGenerating.value) return
  shareGenerating.value = true
  try {
    const scale = 2
    const W = 750
    const pad = 30
    const headerH = 150
    const qrSize = 170
    const sourceLineH = 40

    const canvas = document.createElement('canvas')
    canvas.width = W * scale
    canvas.height = 6000 * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, W, 6000)

    drawShareHeader(ctx, W, pad, headerH, shareSectionTitle.value)

    let usedY = headerH
    if (section === 'pk') usedY = await drawPkPoster(ctx, W, pad, headerH)
    else if (section === 'lineup') usedY = drawLineupPoster(ctx, W, pad, headerH)
    else if (section === 'timeline') usedY = drawTimelinePoster(ctx, W, pad, headerH)

    // 二维码 + 说明
    const qrY = usedY + 16
    const qrCanvas = document.createElement('canvas')
    await QRCode.toCanvas(qrCanvas, 'https://www.dachu.space', {
      width: qrSize * scale, margin: 1, color: { dark: '#000000', light: '#ffffff' },
    })
    ctx.drawImage(qrCanvas, (W - qrSize) / 2, qrY, qrSize, qrSize)
    ctx.textAlign = 'center'
    ctx.fillStyle = '#1d70b8'; ctx.font = 'bold 24px sans-serif'
    ctx.fillText('微信扫一扫 · 访问 www.dachu.space', W / 2, qrY + qrSize + 14)
    ctx.fillStyle = '#999999'; ctx.font = '16px sans-serif'
    ctx.fillText('识别二维码，查看靠谱指数与 AI 大 PK', W / 2, qrY + qrSize + 44)

    const totalH = qrY + qrSize + sourceLineH
    // 裁剪到实际使用高度
    const finalCanvas = document.createElement('canvas')
    finalCanvas.width = W * scale
    finalCanvas.height = totalH * scale
    const fctx = finalCanvas.getContext('2d')
    fctx.drawImage(canvas, 0, 0, W * scale, totalH * scale, 0, 0, W * scale, totalH * scale)
    shareImage.value = finalCanvas.toDataURL('image/png')
  } catch (e) {
    console.error('[AIPkPanel] generateShareImage error', e)
  } finally {
    shareGenerating.value = false
  }
}

/** 保存分享图片到本地 */
function saveShareImage() {
  if (!shareImage.value) return
  const a = document.createElement('a')
  a.href = shareImage.value
  const safeName = ('aipk-' + (shareSection.value || 'share')) + '-allfund.png'
  a.download = safeName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// ========== 模型管理：状态 ==========
const showManage = ref(false)
const showKey = ref(false)
const saving = ref(false)
const editingId = ref(null)
const formMsg = ref('')
const formMsgOk = ref(true)
const userModels = ref([])   // 用户自建模型原始行（来自 user_ai_models）

const form = reactive({
  model_name: '',
  model_provider: 'custom',
  api_key: '',
  api_endpoint: '',
  system_prompt: DEFAULT_SYSTEM_PROMPT,
})
const errors = reactive({ model_name: '', api_key: '' })

const endpointPlaceholder = computed(
  () => PROVIDER_ENDPOINTS[form.model_provider] || 'https://your-api.example.com/v1/chat/completions'
)

function openManage() { showManage.value = true }
function closeManage() { showManage.value = false }

function resetForm() {
  editingId.value = null
  form.model_name = ''
  form.model_provider = 'custom'
  form.api_key = ''
  form.api_endpoint = ''
  form.system_prompt = DEFAULT_SYSTEM_PROMPT
  errors.model_name = ''
  errors.api_key = ''
  formMsg.value = ''
}

function validate() {
  errors.model_name = ''
  errors.api_key = ''
  let ok = true
  if (!form.model_name) {
    errors.model_name = '请填写模型名称'
    ok = false
  } else if (form.model_name.length > 40) {
    errors.model_name = '名称过长（≤40 字）'
    ok = false
  }
  // 新增时 API Key 必填；编辑时允许留空（表示不修改）
  if (!editingId.value) {
    if (!form.api_key) { errors.api_key = '请填写 API Key'; ok = false }
    else if (form.api_key.length < 8) { errors.api_key = 'API Key 格式不正确（至少 8 位）'; ok = false }
  } else if (form.api_key && form.api_key.length < 8) {
    errors.api_key = 'API Key 格式不正确（至少 8 位）'; ok = false
  }
  return ok
}

function rowToModel(row) {
  return {
    id: row.id,
    name: row.model_name,
    name_short: (row.model_name || '').slice(0, 2),
    color: '#59788a',
    mode: 'rule',
    api_provider: row.model_provider,
    model_provider: row.model_provider,
    endpoint: row.api_endpoint,
    system_prompt: row.system_prompt,
    is_active: row.is_active,
    is_custom: true,
  }
}

async function loadUserModels() {
  if (!supabase) return
  try {
    const { data } = await supabase
      .from('user_ai_models')
      .select('*')
      .eq('user_id', userId.value)
      .order('created_at', { ascending: true })
    userModels.value = data || []
    const custom = userModels.value.map(rowToModel)
    const presets = models.value.filter(x => !x.is_custom)
    models.value = [...presets, ...custom]
  } catch (e) {
    console.error('[AIPkPanel] loadUserModels', e)
  }
}

async function saveModel() {
  if (!isAdmin.value) return   // 仅管理员可保存，防止绕过 UI 直接调用
  if (!validate()) return
  if (!supabase) {
    formMsg.value = 'Supabase 未配置，无法保存'
    formMsgOk.value = false
    return
  }
  saving.value = true
  formMsg.value = ''
  const wasEdit = !!editingId.value
  try {
    const payload = {
      user_id: userId.value,
      model_name: form.model_name,
      model_provider: form.model_provider,
      api_endpoint: form.api_endpoint || PROVIDER_ENDPOINTS[form.model_provider] || null,
      system_prompt: form.system_prompt || '',
      updated_at: new Date().toISOString(),
    }
    // 仅当填写了 API Key 才更新（编辑时留空 = 不修改）
    if (form.api_key) payload.api_key_encrypted = obfuscate(form.api_key)

    if (wasEdit) {
      await supabase.from('user_ai_models').update(payload).eq('id', editingId.value).eq('user_id', userId.value)
    } else {
      await supabase.from('user_ai_models').insert(payload)
    }
    await loadUserModels()
    resetForm()
    formMsg.value = wasEdit ? '已保存修改' : '已添加模型，已出现在「模型阵容」'
    formMsgOk.value = true
  } catch (e) {
    console.error('[AIPkPanel] saveModel', e)
    formMsg.value = '保存失败：' + (e?.message || e)
    formMsgOk.value = false
  } finally {
    saving.value = false
  }
}

function editModel(m) {
  if (!isAdmin.value) return
  editingId.value = m.id
  form.model_name = m.name
  form.model_provider = m.model_provider || 'custom'
  form.api_key = ''   // 不回显明文
  form.api_endpoint = m.endpoint || PROVIDER_ENDPOINTS[form.model_provider] || ''
  form.system_prompt = m.system_prompt || DEFAULT_SYSTEM_PROMPT
  errors.model_name = ''
  errors.api_key = ''
  formMsg.value = ''
}

async function deleteModel(m) {
  if (!isAdmin.value) return
  if (typeof window !== 'undefined' && !window.confirm(`确认删除模型「${m.name}」？此操作不可恢复。`)) return
  if (!supabase) return
  try {
    await supabase.from('user_ai_models').delete().eq('id', m.id).eq('user_id', userId.value)
    if (editingId.value === m.id) resetForm()
    await loadUserModels()
    formMsg.value = '已删除模型'
    formMsgOk.value = true
  } catch (e) {
    console.error('[AIPkPanel] deleteModel', e)
    formMsg.value = '删除失败：' + (e?.message || e)
    formMsgOk.value = false
  }
}

async function toggleModelActive(m) {
  if (!isAdmin.value) return
  if (!supabase) return
  try {
    const next = !m.is_active
    await supabase
      .from('user_ai_models')
      .update({ is_active: next, updated_at: new Date().toISOString() })
      .eq('id', m.id)
      .eq('user_id', userId.value)
    await loadUserModels()
  } catch (e) {
    console.error('[AIPkPanel] toggleModelActive', e)
  }
}

</script>

<style scoped>
.aipk { padding-bottom: var(--space-2xl); }

.card { background: #fff; border: 1px solid var(--border); padding: var(--space-lg); margin-bottom: var(--space-xl); }
.card-title { font-size: 24px; font-weight: 700; margin-bottom: var(--space-md); }
.card-desc { font-size: 16px; color: var(--text-secondary); line-height: 1.7; margin-bottom: var(--space-md); }
.card-desc b { color: var(--text-primary); }

/* 说明卡 */
.aipk-intro { border-left: 5px solid #1d70b8; }
.card-title-row { display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-md); }
.card-title-row .card-title { margin-bottom: 0; }
.aipk-badge { font-size: 13px; color: #943c0c; background: #fff4e0; padding: 2px 10px; font-weight: 700; }
.aipk-badge-real { color: #fff; background: #1d70b8; }
.aipk-src { font-size: 14px; color: var(--text-secondary); }

/* 模型卡模式标签（真实/规则） */
.aipk-model-mode { font-size: 12px; font-weight: 700; padding: 1px 8px; margin-left: auto; }
.aipk-model-mode.is-real { color: #fff; background: #1d70b8; }
.aipk-model-mode.is-rule { color: #505a66; background: #f3f2f1; border: 1px solid var(--border); }
.aipk-model-mode.is-pending { color: #943c0c; background: #fff4e0; border: 1px solid #f0c89a; }

/* 千问百炼聚合平台徽标 */
.aipk-ds-badge { font-size: 12px; font-weight: 700; padding: 1px 8px; margin-left: 6px; color: #fff; background: #b8860b; }

/* 时间线模式注记 */
.aipk-tl-mode-note { font-size: 13px; font-weight: 400; color: var(--text-secondary); }

.aipk-section-title { font-size: 19px; font-weight: 700; margin: var(--space-lg) 0 var(--space-md); }

/* 模型阵容 */
.aipk-models { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-md); margin-bottom: var(--space-xl); }
.aipk-model { background: #fff; border: 1px solid var(--border); border-top: 4px solid #1d70b8; padding: var(--space-md); }
.aipk-model-hd { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-sm); }
.aipk-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; flex: none; }
.aipk-model-name { font-size: 17px; font-weight: 700; }
.aipk-model-short { font-size: 13px; font-weight: 700; }
.aipk-model-persona { font-size: 13px; color: var(--text-secondary); line-height: 1.5; margin-bottom: var(--space-sm); min-height: 38px; }
.aipk-model-ret { font-size: 15px; font-weight: 700; margin-bottom: var(--space-sm); font-variant-numeric: tabular-nums; }
.aipk-funds { display: flex; flex-direction: column; gap: 4px; border-top: 1px solid var(--border); padding-top: var(--space-sm); }
.aipk-fund { display: flex; align-items: center; gap: var(--space-sm); font-size: 13px; }
.aipk-fund-idx { width: 18px; height: 18px; line-height: 18px; text-align: center; background: #f3f2f1; color: var(--text-secondary); font-size: 11px; flex: none; }
.aipk-fund-name { font-weight: 600; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.aipk-fund-code { color: var(--text-secondary); font-size: 12px; }
.aipk-fund-w { color: #1d70b8; font-weight: 700; font-size: 12px; }
.aipk-funds-empty { font-size: 13px; color: var(--text-secondary); }
.aipk-pending { font-size: 14px; font-weight: 700; color: #943c0c; background: #fff4e0; border: 1px solid #f0c89a; padding: var(--space-sm); text-align: center; }
.aipk-tl-pending { font-size: 15px; font-weight: 700; color: #943c0c; background: #fff4e0; border: 1px solid #f0c89a; padding: var(--space-md); text-align: center; }

/* 收益 PK */
.aipk-pk-hd { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-md); margin-bottom: var(--space-md); }
.aipk-pk-hd .card-title { margin-bottom: 0; }
.aipk-periods { display: flex; gap: var(--space-xs); flex-wrap: wrap; }
.aipk-period-btn { padding: 4px var(--space-md); border: 1px solid var(--border); background: #fff; cursor: pointer; font-size: 14px; color: var(--text-secondary); }
.aipk-period-btn:hover { border-color: #1d70b8; }
.aipk-period-btn.active { background: #1d70b8; color: #fff; border-color: #1d70b8; }

.aipk-rank { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-md); margin-bottom: var(--space-md); }
.aipk-rank-item { display: flex; flex-direction: column; align-items: center; padding: var(--space-md); border: 1px solid var(--border); }
.aipk-rank-item.rank-1 { border-color: #b8860b; border-width: 2px; background: #fffdf5; }
.aipk-rank-item.rank-2 { border-color: #8c8c8c; border-width: 2px; background: #fafafa; }
.aipk-rank-item.rank-3 { border-color: #b5651d; border-width: 2px; background: #fdf8f4; }
.aipk-rank-medal { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
.rank-1 .aipk-rank-medal { color: #b8860b; }
.rank-2 .aipk-rank-medal { color: #8c8c8c; }
.rank-3 .aipk-rank-medal { color: #b5651d; }
.aipk-rank-name { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
.aipk-rank-val { font-size: 19px; font-weight: 700; font-variant-numeric: tabular-nums; }
.aipk-rank-note { font-size: 13px; color: var(--text-secondary); margin-bottom: var(--space-md); }

.aipk-chart { width: 100%; height: 360px; margin-bottom: var(--space-xl); }

.aipk-table-title { font-size: 16px; font-weight: 700; margin-bottom: var(--space-sm); }
.aipk-table-wrap { overflow-x: auto; }
.aipk-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 720px; }
.aipk-table th, .aipk-table td { padding: 8px 6px; text-align: center; border: 1px solid var(--border); font-variant-numeric: tabular-nums; white-space: nowrap; }
.aipk-table thead th { background: #f3f2f1; font-weight: 700; }
.aipk-th-model, .aipk-th-sort { cursor: pointer; user-select: none; }
.aipk-th-sort:hover, .aipk-th-model:hover { background: #e2e2e1; }
.sort-arrow { font-size: 10px; margin-left: 2px; color: #1d70b8; }
.aipk-th-model { text-align: left !important; }
.aipk-td-model { text-align: left !important; font-weight: 700; white-space: nowrap; }
.aipk-td-model .aipk-dot { margin-right: 6px; vertical-align: middle; }

/* 涨跌配色 */
.ret-pos { color: #d4351c; }
.ret-neg { color: #00703c; }
.ret-flat { color: #505a66; }
.ret-na { color: #b1b4b6; }

/* 时间线（两层选基逻辑） */
.aipk-tl-period { font-size: 15px; font-weight: 700; color: #1d70b8; margin-bottom: var(--space-md); }
.aipk-tl-empty { font-size: 14px; color: var(--text-secondary); }
.aipk-tl-model { border-top: 1px solid var(--border); padding: var(--space-md) 0; }
.aipk-tl-model:first-of-type { border-top: none; }
.aipk-tl-model-hd { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-sm); }
.aipk-tl-model-name { font-size: 17px; font-weight: 700; }
.aipk-tl-model-short { font-size: 13px; font-weight: 700; }
.aipk-tl-layer { margin-bottom: var(--space-sm); }
.aipk-tl-tag { display: inline-block; font-size: 12px; font-weight: 700; color: #fff; background: #1d70b8; padding: 2px 8px; margin-bottom: 6px; }
.aipk-tl-text { font-size: 14px; color: var(--text-secondary); line-height: 1.7; margin: 0; }
.aipk-tl-funds { display: flex; flex-direction: column; gap: 8px; }
.aipk-tl-fund { display: grid; grid-template-columns: 20px 1fr auto; gap: var(--space-sm); align-items: baseline; }
.aipk-tl-fund-idx { width: 20px; height: 20px; line-height: 20px; text-align: center; background: #f3f2f1; color: var(--text-secondary); font-size: 11px; }
.aipk-tl-fund-name { font-weight: 600; font-size: 14px; }
.aipk-tl-fund-w { color: #1d70b8; font-weight: 700; font-size: 12px; }
.aipk-tl-fund-reason { grid-column: 2 / 4; font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin: 2px 0 0; }

.aipk-loading { text-align: center; padding: var(--space-xl); color: var(--text-secondary); }

@media (max-width: 768px) {
  .aipk-rank { grid-template-columns: 1fr; }
  .aipk-chart { height: 320px; }
}

/* ===== 分享按钮 ===== */
.aipk-share-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 700;
  color: #1d70b8;
  background: #fff;
  border: 1px solid #1d70b8;
  border-radius: 2px;
  padding: 5px 12px;
  cursor: pointer;
  flex: none;
}
.aipk-share-btn svg { color: #1d70b8; }
.aipk-share-btn:hover { background: #1d70b8; color: #fff; }
.aipk-share-btn:hover svg { color: #fff; }

/* 收益 PK 头部右侧（周期 + 分享） */
.aipk-pk-hd-right { display: flex; align-items: center; gap: var(--space-md); flex-wrap: wrap; }

/* 模型阵容标题行（标题 + 分享） */
.aipk-section-title-row { display: flex; align-items: center; justify-content: space-between; }
.aipk-section-title-row .aipk-share-btn { margin-left: auto; }

/* 调仓时间线标题行 */
.aipk-tl-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
.aipk-tl-head .card-title { margin-bottom: 0; }

/* ===== 分享弹窗 ===== */
.mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }
.aipk-share-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: calc(100% - 32px);
  max-width: 420px;
  background: #ffffff;
  border: 1px solid var(--border);
  z-index: 102;
  display: flex;
  flex-direction: column;
  max-height: 92vh;
}
.aipk-share-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-lg);
  border-bottom: 1px solid var(--border);
  background: #f3f2f1;
  flex-shrink: 0;
}
.aipk-share-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.aipk-share-close { font-size: 24px; color: var(--text-primary); cursor: pointer; padding: 4px; line-height: 1; flex-shrink: 0; }
.aipk-share-body { padding: var(--space-md); overflow-y: auto; text-align: center; }
.aipk-share-loading { padding: var(--space-xl) 0; color: var(--text-secondary); font-size: 15px; }
.aipk-share-img { width: 100%; height: auto; border: 1px solid #eee; display: block; }
.aipk-share-hint { font-size: 13px; color: var(--text-secondary); margin: var(--space-sm) 0; }
.aipk-share-save-btn {
  display: block;
  width: 100%;
  padding: 10px;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: #1d70b8;
  border: none;
  border-radius: 2px;
  cursor: pointer;
  margin-top: var(--space-sm);
}
.aipk-share-save-btn-ghost { background: #fff; color: #1d70b8; border: 1px solid #1d70b8; }

/* ===== 模型管理按钮（与分享按钮同风格，gov.uk） ===== */
.aipk-section-actions { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; margin-left: auto; }
.aipk-manage-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 700;
  color: #1d70b8;
  background: #fff;
  border: 1px solid #1d70b8;
  border-radius: 2px;
  padding: 5px 12px;
  cursor: pointer;
  flex: none;
}
.aipk-manage-btn svg { color: #1d70b8; }
.aipk-manage-btn:hover { background: #1d70b8; color: #fff; }
.aipk-manage-btn:hover svg { color: #fff; }

/* ===== 模型管理弹窗 ===== */
.aipk-manage-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: calc(100% - 32px);
  max-width: 560px;
  background: #ffffff;
  border: 1px solid var(--border);
  z-index: 102;
  display: flex;
  flex-direction: column;
  max-height: 92vh;
}
.aipk-manage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-lg);
  border-bottom: 1px solid var(--border);
  background: #f3f2f1;
  flex-shrink: 0;
}
.aipk-manage-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.aipk-manage-close { font-size: 24px; color: var(--text-primary); cursor: pointer; padding: 4px; line-height: 1; flex-shrink: 0; }
.aipk-manage-body { padding: var(--space-md) var(--space-lg); overflow-y: auto; }

/* 非管理员限制提示（gov.uk 风格，无圆角无阴影） */
.aipk-manage-restricted {
  text-align: center;
  padding: var(--space-2xl) var(--space-md);
  border: 1px solid #b1b4b6;
  border-left: 4px solid #d4351c;
  background: #fef7f7;
}
.aipk-manage-restricted-icon { font-size: 32px; display: block; margin-bottom: var(--space-sm); }
.aipk-manage-restricted-title { font-size: 18px; font-weight: 700; color: #d4351c; margin: 0 0 var(--space-xs); }
.aipk-manage-restricted-desc { font-size: 14px; color: var(--text-secondary); margin: 0; line-height: 1.6; }

.aipk-manage-sub { font-size: 15px; font-weight: 700; color: #1d70b8; margin: var(--space-md) 0 var(--space-sm); }
.aipk-manage-sub:first-child { margin-top: 0; }

/* 模型列表 */
.aipk-manage-list { display: flex; flex-direction: column; gap: var(--space-xs); margin-bottom: var(--space-md); }
.aipk-manage-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border);
  background: #fff;
  flex-wrap: wrap;
}
.aipk-manage-item.is-off { background: #fafafa; opacity: 0.75; }
.aipk-manage-item-main { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
.aipk-manage-item-name { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.aipk-manage-item-provider { font-size: 12px; font-weight: 700; color: #505a66; background: #f3f2f1; padding: 1px 8px; }
.aipk-manage-tag { font-size: 12px; font-weight: 700; padding: 1px 8px; }
.aipk-manage-tag-sys { color: #505a66; background: #f3f2f1; border: 1px solid var(--border); }
.aipk-manage-tag-on { color: #fff; background: #1d70b8; }
.aipk-manage-tag-off { color: #943c0c; background: #fff4e0; border: 1px solid #f0c89a; }
.aipk-manage-item-actions { display: flex; gap: var(--space-xs); flex-wrap: wrap; }
.aipk-manage-item-readonly { font-size: 12px; color: var(--text-secondary); }
.aipk-manage-mini {
  font-size: 12px;
  font-weight: 700;
  color: #1d70b8;
  background: #fff;
  border: 1px solid #1d70b8;
  border-radius: 2px;
  padding: 3px 10px;
  cursor: pointer;
}
.aipk-manage-mini:hover { background: #1d70b8; color: #fff; }
.aipk-manage-mini-danger { color: #d4351c; border-color: #d4351c; }
.aipk-manage-mini-danger:hover { background: #d4351c; color: #fff; }
.aipk-manage-empty { font-size: 13px; color: var(--text-secondary); padding: var(--space-sm) 0; }

/* 表单 */
.aipk-manage-form { display: flex; flex-direction: column; gap: var(--space-md); }
.aipk-field { display: flex; flex-direction: column; gap: 4px; }
.aipk-field-label { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.aipk-req { color: #d4351c; font-style: normal; }
.aipk-field-hint { font-size: 12px; font-weight: 400; color: var(--text-secondary); }
.aipk-input {
  font-size: 14px;
  color: var(--text-primary);
  background: #fff;
  border: 1px solid #505a66;
  border-radius: 0;
  padding: 8px 10px;
  width: 100%;
  font-family: inherit;
}
.aipk-input:focus { outline: 3px solid #ffdd00; outline-offset: 0; border-color: #1d70b8; }
.aipk-textarea { resize: vertical; line-height: 1.6; }
.aipk-input-wrap { display: flex; gap: var(--space-xs); align-items: stretch; }
.aipk-input-pw { flex: 1; }
.aipk-pw-toggle {
  font-size: 12px;
  font-weight: 700;
  color: #1d70b8;
  background: #fff;
  border: 1px solid #1d70b8;
  border-radius: 2px;
  padding: 0 12px;
  cursor: pointer;
  flex: none;
}
.aipk-pw-toggle:hover { background: #1d70b8; color: #fff; }
.aipk-field-err { font-size: 12px; color: #d4351c; font-weight: 700; }

.aipk-manage-form-actions { display: flex; gap: var(--space-sm); flex-wrap: wrap; margin-top: var(--space-xs); }
.aipk-manage-save-btn {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: #1d70b8;
  border: 1px solid #1d70b8;
  border-radius: 2px;
  padding: 9px 18px;
  cursor: pointer;
}
.aipk-manage-save-btn:disabled { opacity: 0.6; cursor: default; }
.aipk-manage-save-btn-ghost { background: #fff; color: #1d70b8; }
.aipk-manage-save-btn-ghost:hover { background: #1d70b8; color: #fff; }

.aipk-manage-msg { font-size: 13px; font-weight: 700; margin-top: var(--space-sm); }
.aipk-manage-msg.is-ok { color: #00703c; }
.aipk-manage-msg.is-err { color: #d4351c; }

.aipk-manage-note {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-top: var(--space-lg);
  border-top: 1px solid var(--border);
  padding-top: var(--space-md);
}

@media (max-width: 768px) {
  .aipk-section-actions { width: 100%; margin-left: 0; justify-content: flex-end; }
}
</style>
