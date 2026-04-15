<template>
  <n-card 
    class="exam-paper-card" 
    hoverable 
    @click="$emit('click')"
    :style="{ cursor: 'pointer' }"
  >
    <div class="card-header">
      <div class="title-section">
        <n-text strong style="font-size: 16px;">{{ paper.title }}</n-text>
        <n-tag 
          :type="statusType" 
          size="small" 
          :bordered="false"
          style="margin-left: 8px;"
        >
          {{ statusText }}
        </n-tag>
      </div>
      <n-text depth="3" style="font-size: 13px; margin-top: 4px;">
        {{ paper.subject_name }} · {{ paper.total_questions }} 题
      </n-text>
    </div>

    <n-divider style="margin: 12px 0;" />

    <div class="card-body">
      <!-- 进度条 -->
      <div class="progress-section">
        <div class="progress-label">
          <n-text depth="3" style="font-size: 12px;">答题进度</n-text>
          <n-text strong style="font-size: 13px;">
            {{ paper.answered_questions }}/{{ paper.total_questions }}
          </n-text>
        </div>
        <n-progress 
          type="line" 
          :percentage="paper.progress" 
          :show-indicator="false"
          :height="6"
          :border-radius="3"
          :color="progressColor"
        />
      </div>

      <!-- 时间信息 -->
      <div class="info-section">
        <div class="info-item" v-if="paper.remaining_time > 0">
          <n-icon size="16" color="#f0a020">
            <time-outline />
          </n-icon>
          <n-text style="font-size: 13px; color: #f0a020;">
            剩余 {{ formatTime(paper.remaining_time) }}
          </n-text>
        </div>
        <div class="info-item" v-else-if="paper.status === 'completed'">
          <n-icon size="16" color="#18a058">
            <checkmark-circle-outline />
          </n-icon>
          <n-text style="font-size: 13px; color: #18a058;">
            已完成 · 得分 {{ paper.score }}
          </n-text>
        </div>
        <div class="info-item" v-else-if="paper.status === 'expired'">
          <n-icon size="16" color="#d03050">
            <close-circle-outline />
          </n-icon>
          <n-text style="font-size: 13px; color: #d03050;">
            已过期
          </n-text>
        </div>
        <div class="info-item" v-else>
          <n-icon size="16" color="#666">
            <infinite-outline />
          </n-icon>
          <n-text depth="3" style="font-size: 13px;">
            不限时
          </n-text>
        </div>

        <div class="info-item">
          <n-icon size="16" :color="'#666'">
            <calendar-outline />
          </n-icon>
          <n-text depth="3" style="font-size: 13px;">
            {{ formatDate(paper.created_at) }}
          </n-text>
        </div>
      </div>
    </div>

    <template #footer>
      <n-button 
        type="primary" 
        block 
        :disabled="paper.status === 'expired'"
        @click.stop="$emit('click')"
      >
        {{ buttonText }}
      </n-button>
    </template>
  </n-card>
</template>

<script setup>
import { computed } from 'vue'
import { NCard, NText, NTag, NDivider, NProgress, NIcon, NButton } from 'naive-ui'
import { 
  TimeOutline, 
  CheckmarkCircleOutline, 
  CloseCircleOutline,
  InfiniteOutline,
  CalendarOutline
} from '@vicons/ionicons5'

const props = defineProps({
  paper: {
    type: Object,
    required: true
  }
})

defineEmits(['click'])

const statusType = computed(() => {
  switch (props.paper.status) {
    case 'in_progress':
      return 'info'
    case 'completed':
      return 'success'
    case 'expired':
      return 'error'
    default:
      return 'default'
  }
})

const statusText = computed(() => {
  switch (props.paper.status) {
    case 'in_progress':
      return '进行中'
    case 'completed':
      return '已完成'
    case 'expired':
      return '已过期'
    default:
      return '未知'
  }
})

const progressColor = computed(() => {
  if (props.paper.progress >= 80) return '#18a058'
  if (props.paper.progress >= 50) return '#2080f0'
  return '#f0a020'
})

const buttonText = computed(() => {
  if (props.paper.status === 'completed') return '查看详情'
  if (props.paper.status === 'expired') return '已过期'
  return '继续作答'
})

const formatTime = (seconds) => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  if (hours > 0) {
    return `${hours}小时${minutes}分钟`
  }
  return `${minutes}分钟`
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}
</script>

<style scoped>
.exam-paper-card {
  transition: all 0.3s;
  border-radius: 12px;
}

.exam-paper-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-section {
  display: flex;
  align-items: center;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-section {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
