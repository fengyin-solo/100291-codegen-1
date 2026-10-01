<template>
  <section class="page regulation-page">
    <header class="page-head">
      <div>
        <h2>法规标准台账</h2>
        <p class="page-desc">
          按适用设备类别和生效日期登记条款；条款只能顺向流转，设备自动按当前版本重算并保留历史匹配快照。
        </p>
      </div>
      <div class="page-actions">
        <span class="role-badge" :class="{ restricted: !store.hasPermission('regulation:activate') }">
          当前：{{ store.currentRole.label }}
        </span>
        <button class="btn" type="button" @click="activeTab = 'matches'">查看设备适用清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        type="button"
        :class="['tab-button', { active: activeTab === tab.value }]"
        @click="activeTab = tab.value"
      >
        {{ tab.label }}
      </button>
    </nav>

    <section v-if="activeTab === 'clauses'" class="panel">
      <form class="entry-form" @submit.prevent="createRegulation">
        <label v-for="field in formFields" :key="field.name" class="form-item" :class="{ wide: field.wide }">
          <span>{{ field.label }}</span>
          <input v-model="form[field.name]" :placeholder="field.placeholder" required />
        </label>
        <button class="btn primary" type="submit">登记征求意见稿</button>
      </form>

      <form class="filter-bar" @submit.prevent="reloadClauses">
        <label class="filter-item">
          <span>关键词</span>
          <input v-model="clauseFilters.keyword" placeholder="法规编号、名称、版本或公告号" />
        </label>
        <label class="filter-item">
          <span>状态</span>
          <select v-model="clauseFilters.status">
            <option value="">全部</option>
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>设备类别</span>
          <select v-model="clauseFilters.device_category">
            <option value="">全部</option>
            <option v-for="category in categories" :key="category" :value="category">{{ category }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>法规编号</th>
            <th>法规名称</th>
            <th>版本</th>
            <th>设备类别</th>
            <th>公告</th>
            <th>生效日期</th>
            <th>状态</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in clauses" :key="String(row.id)">
            <td>{{ row.regulation_code }}</td>
            <td>{{ row.regulation_name }}</td>
            <td>{{ row.version }}</td>
            <td>{{ row.device_category }}</td>
            <td>{{ row.announcement_no || '—' }}</td>
            <td>{{ row.effective_date }}</td>
            <td><span :class="['status-pill', statusClass(row.status)]">{{ row.status }}</span></td>
            <td class="row-actions">
              <button
                v-if="nextAction(row.status)"
                class="link"
                type="button"
                @click="runAction(nextAction(row.status)!, row)"
              >
                {{ nextAction(row.status) }}
              </button>
              <span v-else class="muted-text">终态</span>
            </td>
          </tr>
          <tr v-if="!clauses.length">
            <td colspan="8" class="empty-state">暂无符合条件的法规条款</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-else-if="activeTab === 'matches'" class="panel">
      <form class="filter-bar" @submit.prevent="reloadMatches">
        <label class="filter-item">
          <span>设备</span>
          <input v-model="matchFilters.device_keyword" placeholder="设备编号或名称" />
        </label>
        <label class="filter-item">
          <span>设备类别</span>
          <select v-model="matchFilters.device_category">
            <option value="">全部</option>
            <option v-for="category in categories" :key="category" :value="category">{{ category }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>判定日期</span>
          <input v-model="matchFilters.as_of" type="date" />
        </label>
        <label class="check-item">
          <input v-model="matchFilters.conflict_only" type="checkbox" />
          只看冲突
        </label>
        <button class="btn" type="submit">查询</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>设备编号</th>
            <th>设备名称</th>
            <th>类别</th>
            <th>当前适用法规</th>
            <th>冲突版本</th>
            <th>判定日期</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in matches" :key="String(row.device_id)" :class="{ conflict: row.has_conflict }">
            <td>{{ row['设备编号'] }}</td>
            <td>{{ row['设备名称'] }}</td>
            <td>{{ row['设备种类'] }}</td>
            <td>{{ row.applied_text }}</td>
            <td>
              <div v-if="row.has_conflict" class="conflict-list">
                <p v-for="conflict in row.conflicts" :key="conflict">{{ conflict }}</p>
              </div>
              <span v-else class="muted-text">无</span>
            </td>
            <td>{{ row.as_of_date }}</td>
          </tr>
          <tr v-if="!matches.length">
            <td colspan="6" class="empty-state">暂无匹配设备</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-else class="panel">
      <form class="filter-bar" @submit.prevent="reloadHistory">
        <label class="filter-item">
          <span>设备</span>
          <input v-model="historyFilters.device_keyword" placeholder="设备编号或名称" />
        </label>
        <button class="btn" type="submit">查询历史</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>快照时间</th>
            <th>设备</th>
            <th>类别</th>
            <th>触发原因</th>
            <th>当时适用</th>
            <th>冲突情况</th>
            <th>操作人</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in histories" :key="String(row.id)">
            <td>{{ row.calculated_at }}</td>
            <td>{{ row.device_code }} / {{ row.device_name }}</td>
            <td>{{ row.device_category }}</td>
            <td>{{ row.event_reason }}</td>
            <td>
              <p v-for="match in row.matches" :key="match.regulation_id">{{ match.applied_text }}</p>
              <span v-if="!row.matches.length" class="muted-text">无适用法规</span>
            </td>
            <td :class="{ 'conflict-text': row.has_conflict }">{{ row.conflict_summary }}</td>
            <td>{{ row.operator }}</td>
          </tr>
          <tr v-if="!histories.length">
            <td colspan="7" class="empty-state">暂无历史匹配快照</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>共 {{ clauseTotal }} 条条款，{{ matchTotal }} 台设备，{{ historyTotal }} 条历史快照</span>
      <span v-if="message" class="success-text">{{ message }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type PagePayload<T> = { items: T[]; total: number }
type RegulationRow = Record<string, string | number>
type MatchItem = { regulation_id: number; applied_text: string }
type DeviceMatch = {
  device_id: number
  '设备编号': string
  '设备名称': string
  '设备种类': string
  applied_text: string
  conflicts: string[]
  has_conflict: boolean
  as_of_date: string
}
type HistoryRow = {
  id: number
  calculated_at: string
  device_code: string
  device_name: string
  device_category: string
  event_reason: string
  matches: MatchItem[]
  has_conflict: boolean
  conflict_summary: string
  operator: string
}

const store = useSessionStore()
const statuses = ['征求意见', '已生效', '已废止']
const tabs = [
  { value: 'clauses', label: '法规条款' },
  { value: 'matches', label: '设备适用清单' },
  { value: 'history', label: '历史匹配快照' },
] as const

const activeTab = ref<(typeof tabs)[number]['value']>('clauses')
const clauses = ref<RegulationRow[]>([])
const matches = ref<DeviceMatch[]>([])
const histories = ref<HistoryRow[]>([])
const categories = ref<string[]>([])
const clauseTotal = ref(0)
const matchTotal = ref(0)
const historyTotal = ref(0)
const errorMessage = ref('')
const message = ref('')

const emptyForm = {
  regulation_code: '',
  regulation_name: '',
  version: '',
  device_category: '',
  effective_date: '',
  announcement_no: '',
  remark: '',
}
const form = reactive({ ...emptyForm })
const clauseFilters = reactive({ keyword: '', status: '', device_category: '' })
const matchFilters = reactive({
  device_keyword: '',
  device_category: '',
  as_of: '',
  conflict_only: false,
})
const historyFilters = reactive({ device_keyword: '' })

const formFields = [
  { name: 'regulation_code', label: '法规编号', placeholder: '如 TSG 11', wide: false },
  { name: 'regulation_name', label: '法规名称', placeholder: '如 锅炉安全技术规程', wide: true },
  { name: 'version', label: '条款版本', placeholder: '如 2026征求意见稿', wide: false },
  { name: 'device_category', label: '适用设备类别', placeholder: '锅炉 / 压力容器 / 电梯', wide: false },
  { name: 'effective_date', label: '生效日期', placeholder: 'YYYY-MM-DD', wide: false },
  { name: 'announcement_no', label: '公告号', placeholder: '来源公告，可选', wide: false },
  { name: 'remark', label: '备注', placeholder: '口径说明，可选', wide: true },
] as const

const stats = computed(() => [
  { label: '法规条款', value: clauseTotal.value },
  { label: '已登记设备', value: matchTotal.value },
  { label: '当前冲突', value: matches.value.filter((row) => row.has_conflict).length },
  { label: '历史快照', value: historyTotal.value },
])

function nextAction(status: unknown) {
  if (status === '征求意见') return '启用条款'
  if (status === '已生效') return '废止条款'
  return null
}

function statusClass(status: unknown) {
  return {
    征求意见: 'draft',
    已生效: 'active',
    已废止: 'repealed',
  }[String(status)] ?? ''
}

async function getJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) throw new Error(`接口返回 ${response.status}`)
  return (await response.json()) as T
}

async function readError(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? fallback
  } catch {
    return fallback
  }
}

async function reloadCategories() {
  const payload = await getJson<{ items: string[] }>('/api/regulations/categories')
  categories.value = payload.items
}

async function reloadClauses() {
  const params = new URLSearchParams()
  Object.entries(clauseFilters).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  const payload = await getJson<PagePayload<RegulationRow>>(`/api/regulations?${params.toString()}`)
  clauses.value = payload.items
  clauseTotal.value = payload.total
}

async function reloadMatches() {
  const params = new URLSearchParams()
  Object.entries(matchFilters).forEach(([key, value]) => {
    if (key === 'conflict_only') params.set(key, value ? 'true' : '')
    else if (value) params.set(key, String(value))
  })
  const payload = await getJson<PagePayload<DeviceMatch>>(`/api/regulations/matches?${params.toString()}`)
  matches.value = payload.items
  matchTotal.value = payload.total
}

async function reloadHistory() {
  const params = new URLSearchParams()
  if (historyFilters.device_keyword) params.set('device_keyword', historyFilters.device_keyword)
  const payload = await getJson<PagePayload<HistoryRow>>(`/api/regulations/history?${params.toString()}`)
  histories.value = payload.items
  historyTotal.value = payload.total
}

async function createRegulation() {
  errorMessage.value = ''
  message.value = ''
  try {
    const response = await request('/api/regulations', {
      method: 'POST',
      body: JSON.stringify(form),
    })
    if (!response.ok) {
      throw new Error(await readError(response, '法规条款登记失败'))
    }
    Object.assign(form, emptyForm)
    message.value = '征求意见稿已登记'
    await Promise.all([reloadCategories(), reloadClauses()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '法规条款登记失败'
  }
}

async function runAction(action: string, row: RegulationRow) {
  errorMessage.value = ''
  message.value = ''
  try {
    const response = await request(`/api/regulations/${row.id}/actions`, {
      method: 'POST',
      headers: store.authHeaders(),
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error(await readError(response, '法规条款动作未生效'))
    }
    message.value = `${action}成功，存量设备已按新版条款重算`
    await Promise.all([reloadClauses(), reloadMatches(), reloadHistory()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '法规条款动作未生效'
  }
}

onMounted(async () => {
  try {
    await Promise.all([reloadCategories(), reloadClauses(), reloadMatches(), reloadHistory()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '法规台账加载失败'
  }
})
</script>
