import { useUserStore } from '@/stores/user'

/**
 * 权限指令：
 *   v-role="['sys_admin']"        仅系统管理员可见
 *   v-role="['lab_admin','sys_admin']"
 *   v-role:any="['student','teacher']"
 */
export function setupPermission(app) {
  app.directive('role', {
    mounted(el, binding) {
      const userStore = useUserStore()
      const roles = Array.isArray(binding.value) ? binding.value : [binding.value]
      if (!roles.length) return
      if (!userStore.hasRole(roles)) {
        el.parentNode?.removeChild(el)
      }
    }
  })
}
