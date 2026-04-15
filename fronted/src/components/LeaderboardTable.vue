<template>
  <div class="leaderboard-table-container">
    <n-data-table
      :columns="columns"
      :data="data"
      :pagination="pagination"
      :row-class-name="rowClassName"
      :bordered="false"
      striped
      size="large"
    />
  </div>
</template>

<script setup>
import { h } from 'vue'
import { NTag, NText, NAvatar, NSpace, NIcon } from 'naive-ui'
import { TrophyOutline, MedalOutline, RibbonOutline } from '@vicons/ionicons5'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  currentUserId: {
    type: Number,
    default: null
  },
  title: {
    type: String,
    default: '排行榜'
  }
})

const pagination = {
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100]
}

// 获取排名标签类型
const getRankType = (rank) => {
  if (rank === 1) return 'error'
  if (rank === 2) return 'warning'
  if (rank === 3) return 'info'
  return 'default'
}

// 获取排名图标
const getRankIcon = (rank) => {
  if (rank === 1) return h(NIcon, { size: 20, color: '#FFD700' }, { default: () => h(TrophyOutline) })
  if (rank === 2) return h(NIcon, { size: 20, color: '#C0C0C0' }, { default: () => h(MedalOutline) })
  if (rank === 3) return h(NIcon, { size: 20, color: '#CD7F32' }, { default: () => h(RibbonOutline) })
  return null
}

// 获取排名背景色
const getRankBgColor = (rank) => {
  if (rank === 1) return 'linear-gradient(135deg, #FFD700 0%, #FFA500 100%)'
  if (rank === 2) return 'linear-gradient(135deg, #C0C0C0 0%, #A9A9A9 100%)'
  if (rank === 3) return 'linear-gradient(135deg, #CD7F32 0%, #B8860B 100%)'
  return '#f5f5f5'
}

// 获取正确率颜色类型
const getAccuracyType = (accuracy) => {
  if (accuracy >= 90) return 'success'
  if (accuracy >= 80) return 'info'
  if (accuracy >= 70) return 'warning'
  return 'error'
}

// 获取正确率颜色
const getAccuracyColor = (accuracy) => {
  if (accuracy >= 90) return '#18a058'
  if (accuracy >= 80) return '#2080f0'
  if (accuracy >= 70) return '#f0a020'
  return '#d03050'
}

const columns = [
  {
    title: '排名',
    key: 'rank',
    width: 100,
    align: 'center',
    render: (row) => {
      const icon = getRankIcon(row.rank)
      const isTopThree = row.rank <= 3
      
      return h(
        'div',
        {
          style: {
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '8px',
            borderRadius: '8px',
            background: isTopThree ? getRankBgColor(row.rank) : '#f5f5f5',
            color: isTopThree ? 'white' : '#333',
            fontWeight: isTopThree ? '600' : '500',
            fontSize: isTopThree ? '16px' : '14px'
          }
        },
        [
          icon,
          h('span', {}, row.rank)
        ]
      )
    }
  },
  {
    title: '用户',
    key: 'username',
    width: 200,
    render: (row) => {
      const isCurrentUser = row.user_id === props.currentUserId
      return h(
        'div',
        {
          style: {
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }
        },
        [
          h(NAvatar, {
            round: true,
            size: 'medium',
            style: {
              background: isCurrentUser ? '#18a058' : '#2080f0'
            }
          }, {
            default: () => row.username.charAt(0).toUpperCase()
          }),
          h(
            'div',
            {},
            [
              h(
                NText,
                { 
                  strong: isCurrentUser, 
                  type: isCurrentUser ? 'success' : 'default',
                  style: { fontSize: '14px' }
                },
                { default: () => isCurrentUser ? `${row.username} (我)` : row.username }
              ),
              h(
                NText,
                { 
                  depth: 3,
                  style: { fontSize: '12px', display: 'block', marginTop: '2px' }
                },
                { default: () => row.student_id }
              )
            ]
          )
        ]
      )
    }
  },
  {
    title: '综合得分',
    key: 'score',
    width: 140,
    align: 'center',
    sorter: (a, b) => a.score - b.score,
    render: (row) => {
      return h(
        'div',
        {
          style: {
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px'
          }
        },
        [
          h(
            NText,
            { 
              type: 'info', 
              strong: true,
              style: { fontSize: '18px' }
            },
            { default: () => row.score.toFixed(2) }
          ),
          h(
            NText,
            { 
              depth: 3,
              style: { fontSize: '12px' }
            },
            { default: () => '分' }
          )
        ]
      )
    }
  },
  {
    title: '练习数据',
    key: 'stats',
    width: 200,
    align: 'center',
    render: (row) => {
      return h(
        NSpace,
        { vertical: true, size: 'small', align: 'center' },
        {
          default: () => [
            h(
              NText,
              { style: { fontSize: '14px' } },
              { default: () => `总题数: ${row.total_count}` }
            ),
            h(
              NSpace,
              { size: 'small' },
              {
                default: () => [
                  h(
                    NText,
                    { type: 'success', style: { fontSize: '13px' } },
                    { default: () => `✓ ${row.correct_count}` }
                  ),
                  h(
                    NText,
                    { type: 'error', style: { fontSize: '13px' } },
                    { default: () => `✗ ${row.wrong_count}` }
                  )
                ]
              }
            )
          ]
        }
      )
    }
  },
  {
    title: '正确率',
    key: 'accuracy',
    width: 140,
    align: 'center',
    sorter: (a, b) => a.accuracy - b.accuracy,
    render: (row) => {
      return h(
        'div',
        {
          style: {
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '8px'
          }
        },
        [
          h(
            'div',
            {
              style: {
                width: '80px',
                height: '8px',
                background: '#f0f0f0',
                borderRadius: '4px',
                overflow: 'hidden'
              }
            },
            [
              h('div', {
                style: {
                  width: `${row.accuracy}%`,
                  height: '100%',
                  background: getAccuracyColor(row.accuracy),
                  transition: 'width 0.3s ease'
                }
              })
            ]
          ),
          h(
            NText,
            { 
              strong: true,
              style: { 
                fontSize: '16px',
                color: getAccuracyColor(row.accuracy)
              }
            },
            { default: () => `${row.accuracy}%` }
          )
        ]
      )
    }
  }
]

// 行样式
const rowClassName = (row) => {
  return row.user_id === props.currentUserId ? 'current-user-row' : ''
}
</script>

<style scoped>
.leaderboard-table-container {
  border-radius: 12px;
  overflow: hidden;
}

:deep(.n-data-table) {
  font-size: 14px;
}

:deep(.n-data-table-th) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
  font-size: 14px;
  padding: 16px 12px;
}

:deep(.n-data-table-td) {
  padding: 16px 12px;
}

:deep(.current-user-row) {
  background: linear-gradient(90deg, rgba(24, 160, 88, 0.08) 0%, rgba(24, 160, 88, 0.02) 100%);
  border-left: 4px solid #18a058;
}

:deep(.current-user-row:hover) {
  background: linear-gradient(90deg, rgba(24, 160, 88, 0.12) 0%, rgba(24, 160, 88, 0.04) 100%) !important;
}

:deep(.n-data-table-tr:hover) {
  background-color: rgba(0, 0, 0, 0.02);
}

:deep(.n-pagination) {
  margin-top: 16px;
  justify-content: center;
}
</style>
