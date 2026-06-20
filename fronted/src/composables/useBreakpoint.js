import { ref, onMounted, onBeforeUnmount, computed } from 'vue'

/**
 * 全局响应式断点
 * mobile:  <= 768px   （手机竖屏 / 横屏小屏）
 * tablet:  769 ~ 1024px（平板）
 * desktop: > 1024px   （桌面）
 *
 * 用法：
 *   const { isMobile, isTablet, isDesktop, width } = useBreakpoint()
 */

const MOBILE_MAX = 768
const TABLET_MAX = 1024

// 模块级单例，避免每个组件都创建一套监听
let initialized = false
const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1280)

const handleResize = () => {
  width.value = window.innerWidth
}

function ensureGlobalListener() {
  if (initialized || typeof window === 'undefined') return
  window.addEventListener('resize', handleResize, { passive: true })
  window.addEventListener('orientationchange', handleResize, { passive: true })
  initialized = true
}

export function useBreakpoint() {
  // 组件内挂载时刷新一次，保证 SSR / 首屏宽度正确
  onMounted(() => {
    ensureGlobalListener()
    handleResize()
  })

  // 注意：监听器为全局单例，这里不在 unmount 时移除，
  // 以便多个组件共享同一份宽度状态。

  const isMobile = computed(() => width.value <= MOBILE_MAX)
  const isTablet = computed(() => width.value > MOBILE_MAX && width.value <= TABLET_MAX)
  const isDesktop = computed(() => width.value > TABLET_MAX)
  // 手机或平板都视为「窄屏」，多数布局切换以此为准
  const isNarrow = computed(() => width.value <= TABLET_MAX)

  return {
    width,
    isMobile,
    isTablet,
    isDesktop,
    isNarrow,
    MOBILE_MAX,
    TABLET_MAX
  }
}

export default useBreakpoint
