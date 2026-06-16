import { createApp } from 'vue'
import { createPinia } from 'pinia'
import naive from 'naive-ui'
import App from './App.vue'
import router from './router'
import { initSecurityMeasures } from './utils/disableDevTools'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(naive)

// 启用前端安全措施
// 注意：开发环境也启用，方便测试效果
console.log('🔒 初始化前端安全措施...')
console.log('环境:', import.meta.env.MODE)

initSecurityMeasures({
  disableRightClick: false,     // 禁用右键菜单
  disableShortcuts: false,      // 禁用开发者工具快捷键（F12等）
  detectDevTools: false,        // 检测开发者工具是否打开
  disableConsole: false,        // 不禁用控制台（方便看日志）
  preventIframe: true,          // 防止iframe嵌入
  disableSelection: false,      // 不禁用文本选择（保持用户体验）
  disableDrag: false,           // 不禁用拖拽（保持用户体验）
  clearDebug: false,            // 不清除调试信息（开发时需要）
})

app.mount('#app')
