<template>
  <div class="leaderboard-page">
    <n-page-header title="排行榜" subtitle="查看综合实力排名">
      <template #extra>
        <n-space :size="12" :wrap="false">
          <!-- 榜单类型切换 -->
          <n-select
            v-model:value="currentTab"
            :options="tabOptions"
            style="width: 140px;"
            @update:value="switchTab"
          />
          
          <!-- 时间筛选 -->
          <n-select
            v-model:value="selectedDays"
            :options="timeOptions"
            style="width: 100px;"
            @update:value="selectDays"
          />
          
          <!-- 搜索框 -->
          <n-input 
            v-model:value="searchKeyword" 
            placeholder="搜索同学 / 学号..." 
            style="width: 200px;" 
            clearable
          >
            <template #prefix>
              <n-icon><search-outline /></n-icon>
            </template>
          </n-input>
        </n-space>
      </template>
    </n-page-header>

    <n-spin :show="loading">
      <div class="content-wrapper">
        <!-- 左侧：排行榜主内容 -->
        <div class="leaderboard-main">
          <n-card>
            <div v-if="currentLeaderboard.length === 0" class="empty-state">
              <n-empty description="暂无排行榜数据">
                <template #icon>
                  <n-icon size="64" color="#d0d0d0"><trophy-outline /></n-icon>
                </template>
                <template #extra>
                  <n-text depth="3">开始练习后即可查看排名</n-text>
                </template>
              </n-empty>
            </div>
            
            <div v-else>
              <!-- 前三名领奖台 -->
              <div v-if="topThree.length > 0" class="podium">
                <!-- 第二名 -->
                <div v-if="topThree[1]" class="podium-item rank-2">
                  <div class="podium-avatar-wrapper silver">
                    <n-avatar 
                      :size="80" 
                      round
                      color="#18a058"
                      class="podium-avatar"
                    >
                      {{ topThree[1].username.charAt(0) }}
                    </n-avatar>
                    <div class="rank-badge silver">NO.2</div>
                  </div>
                  <div class="podium-info">
                    <n-text strong style="font-size: 16px;">{{ topThree[1].username }}</n-text>
                    <n-text depth="3" style="font-size: 12px; color: #2dd4bf;">{{ topThree[1].student_id }}</n-text>
                    <div class="podium-score">{{ topThree[1].score.toFixed(1) }}</div>
                  </div>
                </div>

                <!-- 第一名 (C位) -->
                <div v-if="topThree[0]" class="podium-item rank-1">
                  <!-- 动态光环 -->
                  <div class="glow-ring"></div>
                  
                  <div class="podium-avatar-wrapper gold">
                    <n-avatar 
                      :size="100" 
                      round
                      color="#18a058"
                      class="podium-avatar"
                    >
                      {{ topThree[0].username.charAt(0) }}
                    </n-avatar>
                    <div class="rank-badge gold">
                      <n-icon size="10"><star-outline /></n-icon>
                      NO.1
                    </div>
                  </div>
                  <div class="podium-info">
                    <n-text strong style="font-size: 20px;">{{ topThree[0].username }}</n-text>
                    <n-text depth="3" class="student-id-highlight">{{ topThree[0].student_id }}</n-text>
                    <div class="podium-score champion">{{ topThree[0].score.toFixed(1) }}</div>
                  </div>
                </div>

                <!-- 第三名 -->
                <div v-if="topThree[2]" class="podium-item rank-3">
                  <div class="podium-avatar-wrapper bronze">
                    <n-avatar 
                      :size="80" 
                      round
                      color="#18a058"
                      class="podium-avatar"
                    >
                      {{ topThree[2].username.charAt(0) }}
                    </n-avatar>
                    <div class="rank-badge bronze">NO.3</div>
                  </div>
                  <div class="podium-info">
                    <n-text strong style="font-size: 16px;">{{ topThree[2].username }}</n-text>
                    <n-text depth="3" style="font-size: 12px; color: #2dd4bf;">{{ topThree[2].student_id }}</n-text>
                    <div class="podium-score">{{ topThree[2].score.toFixed(1) }}</div>
                  </div>
                </div>
              </div>

              <!-- 排行榜表格 -->
              <n-data-table
                v-if="restList.length > 0"
                :columns="columns"
                :data="restList"
                :pagination="false"
                :bordered="false"
                striped
                style="margin-top: 32px;"
              />
            </div>
          </n-card>
        </div>

        <!-- 右侧：个人排行榜详情 -->
        <div class="personal-panel" v-if="personalStats">
          <n-card :bordered="false" class="personal-card">
            <!-- 个人头像和基本信息 -->
            <div class="personal-header">
              <div class="avatar-wrapper">
                <n-avatar 
                  :size="80" 
                  round 
                  color="#18a058"
                  class="personal-avatar"
                >
                  {{ personalStats.username.charAt(0) }}
                </n-avatar>
                <div class="level-badge">
                  <n-icon size="10"><star-outline /></n-icon>
                  Lv.{{ userLevel }}
                </div>
              </div>
              <div class="personal-info">
                <n-text strong style="font-size: 18px; color: #333;">{{ personalStats.username }}</n-text>
                <n-text depth="3" style="font-size: 13px;">{{ personalStats.student_id }}</n-text>
              </div>
            </div>

            <n-divider style="margin: 16px 0;" />

            <!-- 综合得分 -->
            <div class="score-display">
              <div class="score-item">
                <n-text depth="3" style="font-size: 12px;">综合得分</n-text>
                <n-text strong style="font-size: 32px; color: #2080f0; font-family: 'Rajdhani', monospace;">
                  {{ personalStats.score.toFixed(2) }}
                </n-text>
              </div>
              <div class="score-item" v-if="personalStats.ranks.comprehensive">
                <n-text depth="3" style="font-size: 12px;">综合排名</n-text>
                <n-tag type="success" size="large" :bordered="false">
                  第 {{ personalStats.ranks.comprehensive }} 名
                </n-tag>
              </div>
            </div>

            <n-divider style="margin: 16px 0;" />

            <!-- 练习数据图表 -->
            <div class="chart-section">
              <div class="section-title">
                <n-icon size="16"><analytics-outline /></n-icon>
                <span>练习数据</span>
              </div>
              <div ref="practiceChartRef" class="chart-container"></div>
            </div>

            <n-divider style="margin: 16px 0;" />

            <!-- 正确率图表 -->
            <div class="chart-section">
              <div class="section-title">
                <n-icon size="16"><pie-chart-outline /></n-icon>
                <span>正确率分析</span>
              </div>
              <div ref="accuracyChartRef" class="chart-container-small"></div>
            </div>

            <n-divider style="margin: 16px 0;" />

            <!-- 各榜单排名雷达图 -->
            <div class="chart-section" v-if="hasRankData">
              <div class="section-title">
                <n-icon size="16"><podium-outline /></n-icon>
                <span>各榜排名</span>
              </div>
              <div ref="rankChartRef" class="chart-container-small"></div>
            </div>

            <!-- 底部按钮 -->
            <n-button 
              type="primary" 
              size="large" 
              block 
              style="margin-top: 16px;"
              @click="() => $router.push('/practice')"
            >
              <template #icon>
                <n-icon><play-outline /></n-icon>
              </template>
              开始学习
            </n-button>
          </n-card>
        </div>
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, h, watch, nextTick } from 'vue'
import { useMessage, NAvatar, NText, NProgress, NIcon } from 'naive-ui'
import { leaderboardApi } from '@/api'
import { 
  TrophyOutline, SearchOutline, StarOutline, BookOutline, 
  CheckmarkCircleOutline, CloseCircleOutline, AnalyticsOutline,
  SchoolOutline, BusinessOutline, RibbonOutline, PeopleOutline,
  PodiumOutline, FlameOutline, CheckmarkOutline, LockClosedOutline,
  PlayOutline, PieChartOutline
} from '@vicons/ionicons5'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import * as echarts from 'echarts'

const message = useMessage()
const loading = ref(false)
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

// ECharts refs
const practiceChartRef = ref(null)
const accuracyChartRef = ref(null)
const rankChartRef = ref(null)

const selectedDays = ref(null)  // 默认为学期（null）
const searchKeyword = ref('')
const currentTab = ref('comprehensive')  // 默认为综合总榜
const leaderboards = ref({ comprehensive: [], school: [], college: [], major: [], class: [] })
const personalStats = ref(null)  // 个人统计数据

// 榜单类型选项
const tabOptions = [
  { label: '综合总榜', value: 'comprehensive' },
  { label: '校级排行', value: 'school' },
  { label: '院级排行', value: 'college' },
  { label: '专业精英', value: 'major' },
  { label: '班级比拼', value: 'class' }
]

// 时间筛选选项
const timeOptions = [
  { label: '本周', value: 7 },
  { label: '本月', value: 30 },
  { label: '学期', value: null }
]

const currentLeaderboard = computed(() => leaderboards.value[currentTab.value] || [])
const topThree = computed(() => {
  const list = currentLeaderboard.value
  if (list.length < 3) return list
  return [list[0], list[1], list[2]]
})
const restList = computed(() => {
  const list = currentLeaderboard.value
  if (list.length <= 3) return []
  return list.slice(3)
})

// 检查是否有排名数据
const hasRankData = computed(() => {
  if (!personalStats.value || !personalStats.value.ranks) return false
  const ranks = personalStats.value.ranks
  return ranks.school || ranks.college || ranks.major || ranks.class
})

// 计算用户等级（基于总题数）
const userLevel = computed(() => {
  if (!personalStats.value) return 1
  const total = personalStats.value.total_count
  
  // 等级规则：每50题升1级
  const level = Math.floor(total / 50) + 1
  return Math.min(level, 99) // 最高99级
})

// 表格列定义
const columns = [
  {
    title: '排名',
    key: 'rank',
    width: 80,
    align: 'center',
    render: (row) => {
      return h('span', { style: { fontWeight: '600', fontSize: '16px' } }, String(row.rank).padStart(2, '0'))
    }
  },
  {
    title: '学生信息',
    key: 'username',
    width: 200,
    render: (row) => {
      const isCurrentUser = row.user_id === userId.value
      return h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px' } }, [
        h(NAvatar, { round: true, size: 'medium' }, { default: () => row.username.charAt(0) }),
        h('div', {}, [
          h(NText, { strong: isCurrentUser, type: isCurrentUser ? 'success' : 'default' }, 
            { default: () => isCurrentUser ? `${row.username} (我)` : row.username }),
          h(NText, { depth: 3, style: { fontSize: '12px', display: 'block' } }, 
            { default: () => row.student_id })
        ])
      ])
    }
  },
  {
    title: '练习数据',
    key: 'stats',
    width: 150,
    align: 'center',
    render: (row) => {
      return h('div', {}, [
        h(NText, { style: { fontSize: '14px' } }, { default: () => `总题数: ${row.total_count}` }),
        h('div', { style: { marginTop: '4px' } }, [
          h(NText, { type: 'success', style: { fontSize: '13px', marginRight: '8px' } }, 
            { default: () => `✓ ${row.correct_count}` }),
          h(NText, { type: 'error', style: { fontSize: '13px' } }, 
            { default: () => `✗ ${row.wrong_count}` })
        ])
      ])
    }
  },
  {
    title: '正确率',
    key: 'accuracy',
    width: 150,
    align: 'center',
    sorter: (a, b) => a.accuracy - b.accuracy,
    render: (row) => {
      return h('div', { style: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' } }, [
        h(NProgress, { 
          type: 'line', 
          percentage: row.accuracy, 
          indicatorPlacement: 'inside',
          processing: row.accuracy < 60,
          status: row.accuracy >= 90 ? 'success' : row.accuracy >= 60 ? 'info' : 'error'
        }),
        h(NText, { strong: true, style: { fontSize: '14px' } }, 
          { default: () => `${row.accuracy}%` })
      ])
    }
  },
  {
    title: '综合得分',
    key: 'score',
    width: 120,
    align: 'center',
    sorter: (a, b) => a.score - b.score,
    render: (row) => {
      return h(NText, { type: 'info', strong: true, style: { fontSize: '18px' } }, 
        { default: () => row.score.toFixed(2) })
    }
  }
]

const switchTab = (value) => { 
  currentTab.value = value
  loadData()
}

const selectDays = (value) => { 
  selectedDays.value = value
  loadData() 
}

const loadData = async () => {
  loading.value = true
  try {
    const params = selectedDays.value ? { days: selectedDays.value, limit: 100 } : { limit: 100 }
    const data = await leaderboardApi.userLeaderboards(userId.value, params)
    
    leaderboards.value = { 
      comprehensive: data.comprehensive || [], 
      school: data.school || [], 
      college: data.college || [], 
      major: data.major || [], 
      class: data.class || [] 
    }
    
    // 保存个人统计数据
    personalStats.value = data.personal || null
    
    if (!data.comprehensive || data.comprehensive.length === 0) {
      message.warning('暂无排行榜数据')
    }
  } catch (error) {
    console.error('Failed to load leaderboard:', error)
    message.error(error.message || '加载排行榜数据失败')
  } finally {
    loading.value = false
  }
}

// 初始化所有图表
const initCharts = async () => {
  await nextTick()
  if (!personalStats.value) return
  
  initPracticeChart()
  initAccuracyChart()
  if (hasRankData.value) {
    initRankChart()
  }
}

// 练习数据柱状图
const initPracticeChart = () => {
  if (!practiceChartRef.value || !personalStats.value) return
  
  const chart = echarts.init(practiceChartRef.value)
  const stats = personalStats.value
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    grid: {
      left: '10%',
      right: '10%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['总题数', '正确', '错误'],
      axisLine: { lineStyle: { color: '#e0e0e0' } },
      axisLabel: { color: '#666', fontSize: 12 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLabel: { color: '#999', fontSize: 11 }
    },
    series: [{
      data: [
        { value: stats.total_count, itemStyle: { color: '#2080f0' } },
        { value: stats.correct_count, itemStyle: { color: '#18a058' } },
        { value: stats.wrong_count, itemStyle: { color: '#d03050' } }
      ],
      type: 'bar',
      barWidth: '50%',
      label: {
        show: true,
        position: 'top',
        color: '#333',
        fontSize: 13,
        fontWeight: 'bold'
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.3)'
        }
      }
    }]
  }
  
  chart.setOption(option)
  
  // 响应式调整
  window.addEventListener('resize', () => chart.resize())
}

// 正确率饼图
const initAccuracyChart = () => {
  if (!accuracyChartRef.value || !personalStats.value) return
  
  const chart = echarts.init(accuracyChartRef.value)
  const stats = personalStats.value
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      bottom: '5%',
      left: 'center',
      textStyle: { fontSize: 12, color: '#666' }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        position: 'outside',
        formatter: '{d}%',
        fontSize: 13,
        fontWeight: 'bold',
        color: '#333'
      },
      emphasis: {
        label: { show: true, fontSize: 15, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.3)' }
      },
      data: [
        { 
          value: stats.correct_count, 
          name: '正确', 
          itemStyle: { color: '#18a058' }
        },
        { 
          value: stats.wrong_count, 
          name: '错误', 
          itemStyle: { color: '#d03050' }
        }
      ]
    }]
  }
  
  chart.setOption(option)
  
  // 响应式调整
  window.addEventListener('resize', () => chart.resize())
}

// 各榜排名雷达图
const initRankChart = () => {
  if (!rankChartRef.value || !personalStats.value || !hasRankData.value) return
  
  const chart = echarts.init(rankChartRef.value)
  const ranks = personalStats.value.ranks
  
  // 找出最大排名值，用于设置雷达图的最大值
  const rankValues = []
  if (ranks.school) rankValues.push(ranks.school)
  if (ranks.college) rankValues.push(ranks.college)
  if (ranks.major) rankValues.push(ranks.major)
  if (ranks.class) rankValues.push(ranks.class)
  
  const maxRank = Math.max(...rankValues, 10) // 至少为10，避免太小
  const maxValue = Math.ceil(maxRank * 1.2) // 最大值设为最大排名的1.2倍
  
  // 构建雷达图数据
  const indicator = []
  const data = []
  const actualRanks = [] // 用于tooltip显示实际排名
  
  if (ranks.school) {
    indicator.push({ name: '校级', max: maxValue })
    data.push(maxValue - ranks.school) // 反转：排名越小，图形越大
    actualRanks.push({ name: '校级', rank: ranks.school })
  }
  if (ranks.college) {
    indicator.push({ name: '院级', max: maxValue })
    data.push(maxValue - ranks.college)
    actualRanks.push({ name: '院级', rank: ranks.college })
  }
  if (ranks.major) {
    indicator.push({ name: '专业', max: maxValue })
    data.push(maxValue - ranks.major)
    actualRanks.push({ name: '专业', rank: ranks.major })
  }
  if (ranks.class) {
    indicator.push({ name: '班级', max: maxValue })
    data.push(maxValue - ranks.class)
    actualRanks.push({ name: '班级', rank: ranks.class })
  }
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        let result = '<div style="padding: 8px;">'
        result += '<div style="font-weight: bold; margin-bottom: 8px;">排名详情</div>'
        actualRanks.forEach((item, index) => {
          result += `<div style="margin: 4px 0;">
            <span style="color: #18a058;">●</span> 
            ${item.name}: 第 <strong>${item.rank}</strong> 名
          </div>`
        })
        result += '</div>'
        return result
      }
    },
    radar: {
      indicator: indicator,
      shape: 'polygon',
      splitNumber: 4,
      name: {
        textStyle: { color: '#666', fontSize: 12 }
      },
      splitLine: {
        lineStyle: { color: '#e0e0e0' }
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(24, 160, 88, 0.05)', 'rgba(24, 160, 88, 0.1)']
        }
      },
      axisLine: {
        lineStyle: { color: '#e0e0e0' }
      }
    },
    series: [{
      type: 'radar',
      data: [{
        value: data,
        name: '排名表现',
        areaStyle: {
          color: 'rgba(24, 160, 88, 0.3)'
        },
        lineStyle: {
          color: '#18a058',
          width: 2
        },
        itemStyle: {
          color: '#18a058',
          borderWidth: 2,
          borderColor: '#fff'
        },
        emphasis: {
          areaStyle: {
            color: 'rgba(24, 160, 88, 0.5)'
          }
        }
      }]
    }]
  }
  
  chart.setOption(option)
  
  // 响应式调整
  window.addEventListener('resize', () => chart.resize())
}

// 监听个人数据变化，重新渲染图表
watch(() => personalStats.value, (newVal) => {
  if (newVal) {
    initCharts()
  }
}, { deep: true })

onMounted(() => { 
  loadData()
})
</script>

<style scoped>
.leaderboard-page {
  min-height: 100%;
}

.content-wrapper {
  display: flex;
  gap: 24px;
  margin-top: 24px;
}

.leaderboard-main {
  flex: 1;
  min-width: 0;
}

.personal-panel {
  width: 340px;
  flex-shrink: 0;
}

.personal-card {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  border-radius: 16px;
}

.personal-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
}

.avatar-wrapper {
  position: relative;
}

.personal-avatar {
  border: 4px solid #18a058 !important;
  box-shadow: 0 4px 16px rgba(24, 160, 88, 0.3);
  color: white !important;
  font-weight: 700;
  font-size: 36px;
}

.level-badge {
  position: absolute;
  bottom: -8px;
  right: -8px;
  background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%);
  color: white;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 12px;
  border: 2px solid white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  gap: 4px;
}

.personal-info {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}

.tags {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

/* 综合得分显示 */
.score-display {
  display: flex;
  justify-content: space-around;
  align-items: center;
  gap: 16px;
  padding: 16px 0;
}

.score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

/* 图表容器 */
.chart-section {
  margin: 16px 0;
}

.chart-container {
  width: 100%;
  height: 200px;
  margin-top: 12px;
}

.chart-container-small {
  width: 100%;
  height: 220px;
  margin-top: 12px;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.stat-card {
  background: #fafafa;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.3s;
  cursor: pointer;
  border: 1px solid #f0f0f0;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #e0e0e0;
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.stat-number {
  font-size: 20px;
  font-weight: 700;
  font-family: 'Rajdhani', 'Courier New', monospace;
  color: #333;
}

/* 章节标题 */
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #333;
}

/* 排名项 */
.rank-section .rank-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #fafafa;
  border-radius: 10px;
  transition: all 0.3s;
}

.rank-section .rank-item:hover {
  background: #f0f0f0;
  transform: translateX(4px);
}

.rank-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #666;
}

/* 挑战项 */
.challenge-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #fafafa;
  border-radius: 10px;
  transition: all 0.3s;
}

.challenge-item:hover {
  background: #f0f0f0;
}

.challenge-item.completed {
  background: linear-gradient(135deg, rgba(24, 160, 88, 0.1) 0%, rgba(24, 160, 88, 0.05) 100%);
  border: 1px solid rgba(24, 160, 88, 0.2);
}

.challenge-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(24, 160, 88, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.challenge-icon.locked {
  background: #f0f0f0;
}

.challenge-content {
  flex: 1;
  min-width: 0;
}

.challenge-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.empty-state {
  padding: 64px 32px;
  text-align: center;
}

/* 领奖台样式 */
.podium {
  display: flex;
  justify-content: center;
  align-items: flex-end;
  gap: 32px;
  margin: 32px 0 48px;
  min-height: 240px;
}

.podium-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
}

.podium-item:hover {
  transform: translateY(-8px);
}

.podium-item.rank-1 {
  margin-top: -32px;
  z-index: 10;
}

.podium-item.rank-2,
.podium-item.rank-3 {
  width: 160px;
}

.podium-item.rank-1 {
  width: 200px;
}

/* 动态光环 - 仅第一名 */
.glow-ring {
  position: absolute;
  inset: -15px;
  border-radius: 50%;
  border: 2px dashed rgba(24, 160, 88, 0.3);
  animation: spin-slow 12s linear infinite;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.5s;
}

.podium-item.rank-1:hover .glow-ring {
  opacity: 1;
}

@keyframes spin-slow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 头像容器 */
.podium-avatar-wrapper {
  position: relative;
  margin-bottom: 20px;
  padding: 4px;
  border-radius: 50%;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.podium-avatar-wrapper.gold {
  background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%);
  box-shadow: 0 0 30px rgba(251, 191, 36, 0.4);
}

.podium-avatar-wrapper.silver {
  background: linear-gradient(135deg, #e2e8f0 0%, #94a3b8 100%);
}

.podium-avatar-wrapper.bronze {
  background: linear-gradient(135deg, #fdba74 0%, #c2410c 100%);
}

/* 头像本身 */
.podium-avatar {
  border: 4px solid white !important;
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.1);
  color: white !important;
  font-weight: 700;
}

/* 排名徽章 */
.rank-badge {
  position: absolute;
  bottom: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: white;
  color: #333;
  font-size: 12px;
  font-weight: 900;
  padding: 4px 12px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  border: 2px solid white;
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.rank-badge.gold {
  background: #fbbf24;
  color: white;
  font-size: 14px;
  padding: 6px 20px;
  border-radius: 20px;
  border-color: #d97706;
}

.rank-badge.silver {
  background: #e2e8f0;
  color: #1e293b;
}

.rank-badge.bronze {
  background: #fdba74;
  color: #7c2d12;
}

/* 信息区域 */
.podium-info {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.student-id-highlight {
  font-size: 12px;
  background: rgba(24, 160, 88, 0.1);
  padding: 4px 12px;
  border-radius: 12px;
  border: 1px solid rgba(24, 160, 88, 0.2);
  display: inline-block;
  margin-top: 4px;
}

/* 分数显示 */
.podium-score {
  font-size: 24px;
  font-weight: 700;
  font-family: 'Rajdhani', 'Courier New', monospace;
  margin-top: 8px;
  color: #333;
}

.podium-score.champion {
  font-size: 36px;
  font-weight: 900;
  background: linear-gradient(to bottom, #333, #666);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .personal-panel {
    display: none;
  }
}

@media (max-width: 768px) {
  .podium {
    flex-direction: column;
    align-items: center;
    gap: 24px;
    min-height: auto;
  }
  
  .podium-item.rank-1 {
    margin-top: 0;
    order: 1;
  }
  
  .podium-item.rank-2 {
    order: 2;
  }
  
  .podium-item.rank-3 {
    order: 3;
  }
  
  .podium-item.rank-1,
  .podium-item.rank-2,
  .podium-item.rank-3 {
    width: 100%;
    max-width: 280px;
  }
}
</style>
