<template>
  <div class="exam-countdown" @click="showDialog = true" :title="tooltipText">
    <!-- 有即将到来的考试 -->
    <template v-if="upcoming">
      <n-icon :size="15" class="countdown-icon"><alarm-outline /></n-icon>
      <span class="countdown-subject">{{ upcoming.subject_name }}</span>
      <span class="countdown-sep">·</span>
      <span class="countdown-time" :class="urgentClass">{{ display }}</span>
    </template>
    <!-- 无考试 -->
    <template v-else-if="loaded">
      <n-icon :size="15" class="countdown-icon countdown-empty"><calendar-outline /></n-icon>
      <span class="countdown-empty-text">暂无考试</span>
    </template>
  </div>

  <ExamScheduleDialog v-model:show="showDialog" @changed="refresh" />
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { AlarmOutline, CalendarOutline } from '@vicons/ionicons5'
import { examScheduleApi, semesterApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import ExamScheduleDialog from './ExamScheduleDialog.vue'

const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const upcoming = ref(null)
const loaded = ref(false)
const showDialog = ref(false)
const nowTs = ref(Date.now())
const currentSemesterId = ref(null)   // 当前学期 ID，null 表示不筛选

// 每秒刷新一次 nowTs
let ticker = null
onMounted(() => {
  ticker = setInterval(() => {
    nowTs.value = Date.now()
    if (upcoming.value && new Date(upcoming.value.exam_time).getTime() <= nowTs.value) {
      fetchUpcoming()
    }
  }, 1000)
  loadCurrentSemester()
})
onBeforeUnmount(() => clearInterval(ticker))

const loadCurrentSemester = async () => {
  if (!userId.value) return
  try {
    const res = await semesterApi.current(userId.value)
    currentSemesterId.value = res?.data?.id || null
  } catch (_) {}
  fetchUpcoming()
}

const fetchUpcoming = async () => {
  if (!userId.value) return
  try {
    const res = await examScheduleApi.upcoming(userId.value, currentSemesterId.value)
    upcoming.value = res?.data || null
  } catch (_) {
    upcoming.value = null
  } finally {
    loaded.value = true
  }
}

const refresh = () => {
  loadCurrentSemester()
}

// ─── 倒计时显示 ──────────────────────────────────────
const display = computed(() => {
  if (!upcoming.value) return ''
  const diff = new Date(upcoming.value.exam_time).getTime() - nowTs.value
  if (diff <= 0) return '考试开始！'
  const d = Math.floor(diff / 86400000)
  const h = Math.floor((diff % 86400000) / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  if (d > 0) return `${d}天 ${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
})

// 紧急：1天内变红色
const urgentClass = computed(() => {
  if (!upcoming.value) return ''
  const diff = new Date(upcoming.value.exam_time).getTime() - nowTs.value
  if (diff <= 86400000) return 'urgent'
  if (diff <= 3 * 86400000) return 'warning'
  return ''
})

const tooltipText = computed(() => {
  if (!upcoming.value) return '点击管理考试日程'
  const loc = upcoming.value.exam_location ? ` · ${upcoming.value.exam_location}` : ''
  const from = (!upcoming.value.is_owner && upcoming.value.owner_username)
    ? ` (来自 ${upcoming.value.owner_username})` : ''
  const t = new Date(upcoming.value.exam_time).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })
  return `${upcoming.value.subject_name}${from}  ${t}${loc}\n点击管理考试日程`
})
</script>

<style scoped>
.exam-countdown {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.04);
  cursor: pointer;
  transition: background 0.2s;
  max-width: 280px;
  white-space: nowrap;
  overflow: hidden;
  font-size: 13px;
}
.exam-countdown:hover {
  background: rgba(0, 0, 0, 0.08);
}
.countdown-icon {
  color: #2080f0;
  flex-shrink: 0;
}
.countdown-icon.countdown-empty {
  color: #9ca3af;
}
.countdown-subject {
  color: #374151;
  font-weight: 500;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.countdown-sep {
  color: #d1d5db;
}
.countdown-time {
  font-family: 'Rajdhani', 'Courier New', monospace;
  font-weight: 700;
  color: #2080f0;
  letter-spacing: 0.5px;
}
.countdown-time.warning {
  color: #f0a020;
}
.countdown-time.urgent {
  color: #d03050;
  animation: blink 1s ease-in-out infinite alternate;
}
.countdown-empty-text {
  color: #9ca3af;
  font-size: 12px;
}

@keyframes blink {
  from { opacity: 1; }
  to   { opacity: 0.5; }
}

/* 移动端：仅显示图标，隐藏文字，减少顶栏占用 */
@media (max-width: 768px) {
  .countdown-subject,
  .countdown-sep,
  .countdown-empty-text {
    display: none;
  }
  .exam-countdown {
    padding: 0 8px;
    max-width: none;
  }
}
</style>
