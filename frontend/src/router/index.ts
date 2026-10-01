import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Register = () => import('@/views/register/index.vue')
const Regulation = () => import('@/views/regulation/index.vue')
const Boiler = () => import('@/views/boiler/index.vue')
const Pressurevessel = () => import('@/views/pressurevessel/index.vue')
const Pipeline = () => import('@/views/pipeline/index.vue')
const Elevator = () => import('@/views/elevator/index.vue')
const Crane = () => import('@/views/crane/index.vue')
const Forklift = () => import('@/views/forklift/index.vue')
const Inspection = () => import('@/views/inspection/index.vue')
const Maintenance = () => import('@/views/maintenance/index.vue')
const Hazard = () => import('@/views/hazard/index.vue')
const Accident = () => import('@/views/accident/index.vue')
const Operator = () => import('@/views/operator/index.vue')
const Training = () => import('@/views/training/index.vue')
const Safetyvalve = () => import('@/views/safetyvalve/index.vue')
const Gauge = () => import('@/views/gauge/index.vue')
const Sparepart = () => import('@/views/sparepart/index.vue')
const Emergency = () => import('@/views/emergency/index.vue')
const Energyeff = () => import('@/views/energyeff/index.vue')
const Archive = () => import('@/views/archive/index.vue')
const Contract = () => import('@/views/contract/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/regulation', name: 'regulation', component: Regulation },
    { path: '/register', name: 'register', component: Register },
    { path: '/boiler', name: 'boiler', component: Boiler },
    { path: '/pressurevessel', name: 'pressurevessel', component: Pressurevessel },
    { path: '/pipeline', name: 'pipeline', component: Pipeline },
    { path: '/elevator', name: 'elevator', component: Elevator },
    { path: '/crane', name: 'crane', component: Crane },
    { path: '/forklift', name: 'forklift', component: Forklift },
    { path: '/inspection', name: 'inspection', component: Inspection },
    { path: '/maintenance', name: 'maintenance', component: Maintenance },
    { path: '/hazard', name: 'hazard', component: Hazard },
    { path: '/accident', name: 'accident', component: Accident },
    { path: '/operator', name: 'operator', component: Operator },
    { path: '/training', name: 'training', component: Training },
    { path: '/safetyvalve', name: 'safetyvalve', component: Safetyvalve },
    { path: '/gauge', name: 'gauge', component: Gauge },
    { path: '/sparepart', name: 'sparepart', component: Sparepart },
    { path: '/emergency', name: 'emergency', component: Emergency },
    { path: '/energyeff', name: 'energyeff', component: Energyeff },
    { path: '/archive', name: 'archive', component: Archive },
    { path: '/contract', name: 'contract', component: Contract },
  ],
})

export default router
