<template>
  <section class="page" data-module="regulation">
    <header class="page-head">
      <div>
        <h2>法规标准台账</h2>
        <p class="page-desc">
          条款按适用设备类别与生效日期登记，状态只能「征求意见 → 已生效 → 已废止」逐级流转；
          设备按类别带出当前适用条款，同法规两版同时命中时生效日期晚者说了算。
        </p>
      </div>
      <div class="page-actions">
        <label class="filter-item">
          <span>当前操作账号</span>
          <select v-model="operator" @change="reloadAll">
            <option v-for="op in operators" :key="op.name" :value="op.name">
              {{ op.name }}（{{ op.dept }}）
            </option>
          </select>
        </label>
        <label class="filter-item">
          <span>口径日期</span>
          <input type="date" v-model="asOf" @change="reloadAll" />
        </label>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">已登记法规</span>
        <strong class="stat-value">{{ regulations.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">在册设备</span>
        <strong class="stat-value">{{ equipments.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">当前条款冲突</span>
        <strong class="stat-value">{{ conflicts.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">历史留痕事件</span>
        <strong class="stat-value">{{ history.length }}</strong>
      </article>
    </div>

    <nav class="filter-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="btn"
        :class="{ primary: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <!-- 法规与条款 -->
    <div v-if="activeTab === 'regulations'">
      <form class="filter-bar" @submit.prevent="createRegulation">
        <label class="filter-item"><span>文号</span><input v-model="regForm.code" placeholder="如 TSG 11" /></label>
        <label class="filter-item"><span>法规名称</span><input v-model="regForm.name" /></label>
        <label class="filter-item"><span>归口部门</span><input v-model="regForm.ownerDept" /></label>
        <button class="btn primary" type="submit">登记法规</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>文号</th><th>法规名称</th><th>归口部门</th><th>版本</th>
            <th>适用设备类别</th><th>状态</th><th>生效日期</th><th>废止日期</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="reg in regulations" :key="reg.id">
            <tr v-for="ver in reg.versions" :key="ver.id">
              <td>{{ reg.code }}</td>
              <td>{{ reg.name }}</td>
              <td>{{ reg.owner_dept }}</td>
              <td>{{ ver.version }}</td>
              <td>{{ ver.applicable_categories.join('、') }}</td>
              <td>{{ ver.status }}</td>
              <td>{{ ver.effective_date ?? '—' }}</td>
              <td>{{ ver.repeal_date ?? '—' }}</td>
              <td class="row-actions">
                <button
                  v-if="ver.status === '征求意见'"
                  class="link"
                  type="button"
                  @click="actVersion(ver.id, 'publish')"
                >启用</button>
                <button
                  v-if="ver.status === '已生效'"
                  class="link"
                  type="button"
                  @click="actVersion(ver.id, 'repeal')"
                >废止</button>
                <span v-if="ver.status === '已废止'" class="empty-state">—</span>
              </td>
            </tr>
            <tr class="version-add-row">
              <td colspan="9">
                <form class="filter-bar" @submit.prevent="addVersion(reg.id)">
                  <span>为 {{ reg.code }} 登记新版条款（初始为征求意见）：</span>
                  <label class="filter-item"><span>版本</span><input v-model="versionForms[reg.id].version" placeholder="如 2026版" /></label>
                  <label class="filter-item">
                    <span>适用类别</span>
                    <select v-model="versionForms[reg.id].categories" multiple size="1">
                      <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
                    </select>
                  </label>
                  <label class="filter-item"><span>拟生效日期</span><input type="date" v-model="versionForms[reg.id].effectiveDate" /></label>
                  <label class="filter-item"><span>口径摘要</span><input v-model="versionForms[reg.id].title" /></label>
                  <button class="btn" type="submit">登记版本</button>
                </form>
              </td>
            </tr>
          </template>
          <tr v-if="!regulations.length">
            <td colspan="9" class="empty-state">暂无法规，先在上方登记第一份</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 设备适用清单 -->
    <div v-if="activeTab === 'equipment'">
      <form class="filter-bar" @submit.prevent="createEquipment">
        <label class="filter-item"><span>设备编号</span><input v-model="eqForm.code" placeholder="如 EQ-B003" /></label>
        <label class="filter-item"><span>设备名称</span><input v-model="eqForm.name" /></label>
        <label class="filter-item">
          <span>设备类别</span>
          <select v-model="eqForm.category">
            <option value="" disabled>选择类别</option>
            <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
          </select>
        </label>
        <button class="btn primary" type="submit">登记设备并匹配</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>设备编号</th><th>设备名称</th><th>设备类别</th>
            <th>当前适用法规（文号 / 版本 / 生效日）</th><th>冲突</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in equipments" :key="item.equipment.id">
            <td>{{ item.equipment.code }}</td>
            <td>{{ item.equipment.name }}</td>
            <td>{{ item.equipment.category }}</td>
            <td>
              <div v-for="app in item.applicable" :key="app.regulation.code">
                {{ app.regulation.code }}《{{ app.regulation.name }}》
                按 <strong>{{ app.winner.version }}</strong>
                （生效 {{ app.winner.effective_date }}）
              </div>
              <span v-if="!item.applicable.length" class="empty-state">当前无适用条款</span>
            </td>
            <td>
              <div v-for="conf in item.conflicts" :key="conf.regulation.code" class="error-text">
                {{ conf.regulation.code }}：{{ conf.winner.version }} 与
                {{ conf.others.map((v) => v.version).join('、') }} 同时有效，
                生效日期晚的「{{ conf.winner.version }}」说了算
              </div>
              <span v-if="!item.conflicts.length">—</span>
            </td>
          </tr>
          <tr v-if="!equipments.length">
            <td colspan="5" class="empty-state">暂无设备</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 冲突汇总 -->
    <div v-if="activeTab === 'conflicts'">
      <table class="data-table">
        <thead>
          <tr><th>设备</th><th>设备类别</th><th>法规</th><th>适用版本（生效晚者）</th><th>与之打架的版本</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in conflicts" :key="`${item.equipment.id}-${item.regulation.code}`">
            <td>{{ item.equipment.code }} {{ item.equipment.name }}</td>
            <td>{{ item.equipment.category }}</td>
            <td>{{ item.regulation.code }}《{{ item.regulation.name }}》</td>
            <td>{{ item.winner.version }}（{{ item.winner.effective_date }} 生效）</td>
            <td>
              <span v-for="other in item.others" :key="other.version_id" class="error-text">
                {{ other.version }}（{{ other.effective_date }} 生效）
              </span>
            </td>
          </tr>
          <tr v-if="!conflicts.length">
            <td colspan="5" class="empty-state">该口径日期下没有两版条款打架</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 历史留痕 -->
    <div v-if="activeTab === 'history'">
      <table class="data-table">
        <thead>
          <tr><th>日期</th><th>事件</th><th>对象</th><th>操作账号</th><th>重算后各设备适用版本（快照）</th></tr>
        </thead>
        <tbody>
          <tr v-for="event in history" :key="event.id">
            <td>{{ event.date }}</td>
            <td>{{ event.reason }}</td>
            <td>{{ event.target.regulation_code ?? '全部法规' }} {{ event.target.version ?? '' }}</td>
            <td>{{ event.actor || '—' }}</td>
            <td>
              <div v-for="snap in event.snapshot" :key="snap.equipment_id">
                {{ snap.equipment_code }}（{{ snap.category }}）：
                <template v-if="snap.winners.length">
                  <span v-for="w in snap.winners" :key="w.regulation_code">
                    {{ w.regulation_code }}→{{ w.version }}<template v-if="w.has_conflict">⚠</template>；
                  </span>
                </template>
                <span v-else class="empty-state">无适用条款</span>
              </div>
            </td>
          </tr>
          <tr v-if="!history.length">
            <td colspan="5" class="empty-state">暂无历史事件</td>
          </tr>
        </tbody>
      </table>
    </div>

    <footer class="page-foot">
      <span>条款启用 / 废止仅限该法规的归口管理员持对应权限，越权会被当场驳回。</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

interface OperatorInfo {
  name: string
  dept: string
  permissions: string[]
}

interface RegulationVersion {
  id: number
  version: string
  title: string
  applicable_categories: string[]
  status: string
  effective_date: string | null
  repeal_date: string | null
}

interface RegulationInfo {
  id: number
  code: string
  name: string
  owner_dept: string
  versions: RegulationVersion[]
}

interface MatchItem {
  equipment: { id: number; code: string; name: string; category: string }
  applicable: Array<{
    regulation: { code: string; name: string }
    winner: { version: string; effective_date: string | null }
  }>
  conflicts: Array<{
    regulation: { code: string }
    winner: { version: string; version_id: number; effective_date: string | null }
    others: Array<{ version: string; version_id: number; effective_date: string | null }>
  }>
}

const ENDPOINT = '/api/regulation'
const tabs = [
  { key: 'regulations', label: '法规条款台账' },
  { key: 'equipment', label: '设备适用清单' },
  { key: 'conflicts', label: '冲突看板' },
  { key: 'history', label: '历史匹配留痕' },
]

const activeTab = ref('regulations')
const operators = ref<OperatorInfo[]>([])
const categories = ref<string[]>([])
const operator = ref('')
const asOf = ref('')
const errorMessage = ref('')

const regulations = ref<RegulationInfo[]>([])
const equipments = ref<MatchItem[]>([])
const conflicts = ref<any[]>([])
const history = ref<any[]>([])

const regForm = reactive({ code: '', name: '', ownerDept: '' })
const eqForm = reactive({ code: '', name: '', category: '' })
const versionForms = reactive<Record<number, { version: string; categories: string[]; effectiveDate: string; title: string }>>({})

async function readJson(path: string, init?: RequestInit): Promise<any> {
  const response = await request(path, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail ?? `接口返回 ${response.status}`)
  }
  return payload
}

function ensureVersionForm(regId: number) {
  if (!versionForms[regId]) {
    versionForms[regId] = { version: '', categories: [], effectiveDate: '', title: '' }
  }
}

async function reloadAll() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (asOf.value) params.set('as_of', asOf.value)
  const query = params.toString()
  try {
    const [regRes, eqRes, confRes, histRes] = await Promise.all([
      readJson(`${ENDPOINT}/regulations`),
      readJson(`${ENDPOINT}/equipment${query ? `?${query}` : ''}`),
      readJson(`${ENDPOINT}/conflicts${query ? `?${query}` : ''}`),
      readJson(`${ENDPOINT}/history`),
    ])
    regulations.value = regRes.items
    equipments.value = eqRes.items
    conflicts.value = confRes.items
    history.value = histRes.items
    regulations.value.forEach((reg) => ensureVersionForm(reg.id))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '台账读取失败'
  }
}

async function createRegulation() {
  errorMessage.value = ''
  try {
    await readJson(`${ENDPOINT}/regulations`, {
      method: 'POST',
      body: JSON.stringify({
        code: regForm.code,
        name: regForm.name,
        owner_dept: regForm.ownerDept,
      }),
    })
    regForm.code = ''
    regForm.name = ''
    regForm.ownerDept = ''
    await reloadAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '法规登记失败'
  }
}

async function addVersion(regId: number) {
  errorMessage.value = ''
  const form = versionForms[regId]
  try {
    await readJson(`${ENDPOINT}/regulations/${regId}/versions`, {
      method: 'POST',
      body: JSON.stringify({
        version: form.version,
        title: form.title,
        categories: form.categories,
        effective_date: form.effectiveDate || null,
      }),
    })
    form.version = ''
    form.categories = []
    form.effectiveDate = ''
    form.title = ''
    await reloadAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '版本登记失败'
  }
}

async function createEquipment() {
  errorMessage.value = ''
  try {
    await readJson(`${ENDPOINT}/equipment`, {
      method: 'POST',
      body: JSON.stringify({ code: eqForm.code, name: eqForm.name, category: eqForm.category }),
    })
    eqForm.code = ''
    eqForm.name = ''
    eqForm.category = ''
    await reloadAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '设备登记失败'
  }
}

async function actVersion(versionId: number, action: 'publish' | 'repeal') {
  errorMessage.value = ''
  try {
    const payload = await readJson(`${ENDPOINT}/versions/${versionId}/${action}`, {
      method: 'POST',
      body: JSON.stringify({ operator: operator.value, date: asOf.value || null }),
    })
    errorMessage.value = payload.message
    await reloadAll()
  } catch (error) {
    // 越权 / 跳级：把后端驳回原话（含缺失权限）亮在页脚。
    errorMessage.value = error instanceof Error ? error.message : '条款操作失败'
  }
}

onMounted(async () => {
  const meta = await readJson(`${ENDPOINT}/meta`)
  operators.value = meta.operators
  categories.value = meta.categories
  operator.value = operators.value[0]?.name ?? ''
  await reloadAll()
})
</script>
