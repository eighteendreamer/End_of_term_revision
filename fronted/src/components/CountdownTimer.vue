<template>
  <div class="countdown-timer" :class="{ 'warning': isWarning, 'danger': isDanger }">
    <n-icon size="18">
      <time-outline />
    </n-icon>
    <span class="time-text">{{ formattedTime }}</span>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { NIcon } from 'naive-ui'
import { TimeOutline } from '@vicons/ionicons5'

const props = defineProps({
  expiresAt: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['expire'])

const remainingSeconds = ref(0)
const timer = ref(null)

const isWarning = computed(() => {
  return remainingSeconds.value > 0 && remainingSeconds.value <= 600  // 10分钟
})

const isDanger = computed(() => {
  return remainingSeconds.value > 0 && remainingSeconds.value <= 300  // 5分钟
})

const formattedTime = computed(() => {
  if (remainingSeconds.value <= 0) {
    return '00:00:00'
  }
  
  const hours = Math.floor(remainingSeconds.value / 3600)
  const minutes = Math.floor((remainingSeconds.value % 3600) / 60)
  const seconds = remainingSeconds.value % 60
  
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})

const calculateRemainingTime = () => {
  const now = new Date().getTime()
  const expires = new Date(props.expiresAt).getTime()
  const diff = Math.floor((expires - now) / 1000)
  return Math.max(0, diff)
}

const startCountdown = () => {
  remainingSeconds.value = calculateRemainingTime()
  
  if (remainingSeconds.value <= 0) {
    emit('expire')
    return
  }
  
  timer.value = setInterval(() => {
    remainingSeconds.value--
    
    if (remainingSeconds.value <= 0) {
      clearInterval(timer.value)
      emit('expire')
    }
  }, 1000)
}

const stopCountdown = () => {
  if (timer.value) {
    clearInterval(timer.value)
    timer.value = null
  }
}

// 监听 expiresAt 变化
watch(() => props.expiresAt, () => {
  stopCountdown()
  startCountdown()
})

onMounted(() => {
  startCountdown()
})

onUnmounted(() => {
  stopCountdown()
})
</script>

<style scoped>
.countdown-timer {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f0f0f0;
  border-radius: 8px;
  transition: all 0.3s;
}

.time-text {
  font-family: 'Courier New', monospace;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.countdown-timer.warning {
  background: #fff7e6;
  color: #f0a020;
}

.countdown-timer.warning .time-text {
  color: #f0a020;
}

.countdown-timer.danger {
  background: #ffe6e6;
  color: #d03050;
  animation: pulse 1s infinite;
}

.countdown-timer.danger .time-text {
  color: #d03050;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}
</style>
