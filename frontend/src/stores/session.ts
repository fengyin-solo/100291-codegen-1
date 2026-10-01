import { defineStore } from 'pinia'

type RoleOption = {
  value: string
  label: string
  permissions: string[]
}

export const roleOptions: RoleOption[] = [
  {
    value: 'regulation_admin',
    label: '归口管理员',
    permissions: ['regulation:activate', 'regulation:repeal'],
  },
  {
    value: 'device_operator',
    label: '设备管理员',
    permissions: [],
  },
]

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '特种设备安全管理平台',
    roleValue: roleOptions[0].value,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    currentRole: (state) => roleOptions.find((item) => item.value === state.roleValue) ?? roleOptions[0],
    roles(state): string[] {
      const role = roleOptions.find((item) => item.value === state.roleValue) ?? roleOptions[0]
      return [role.value]
    },
    permissions(state): string[] {
      const role = roleOptions.find((item) => item.value === state.roleValue) ?? roleOptions[0]
      return role.permissions
    },
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRole(value: string) {
      this.roleValue = value
    },
    hasPermission(permission: string) {
      return this.permissions.includes(permission)
    },
    authHeaders() {
      return {
        'X-Operator-Id': this.operator,
        'X-Roles': this.roles.join(','),
        'X-Permissions': this.permissions.join(','),
      }
    },
  },
})
