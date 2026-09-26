<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "使用登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "锅炉管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "压力容器", "created": 0, "pending": 0, "abnormal": 0}, {"name": "压力管道", "created": 0, "pending": 0, "abnormal": 0}, {"name": "电梯管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "起重机械", "created": 0, "pending": 0, "abnormal": 0}, {"name": "场车管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "定期检验", "created": 0, "pending": 0, "abnormal": 0}, {"name": "维保记录", "created": 0, "pending": 0, "abnormal": 0}, {"name": "隐患排查", "created": 0, "pending": 0, "abnormal": 0}, {"name": "事故管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "作业人员", "created": 0, "pending": 0, "abnormal": 0}, {"name": "培训考核", "created": 0, "pending": 0, "abnormal": 0}, {"name": "安全阀校验", "created": 0, "pending": 0, "abnormal": 0}, {"name": "压力表检定", "created": 0, "pending": 0, "abnormal": 0}, {"name": "备件管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "应急演练", "created": 0, "pending": 0, "abnormal": 0}, {"name": "能效监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "档案管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "维保合同", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>
