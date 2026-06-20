<template>
  <div>
    <n-page-header :title="paper.title || '试卷练习'" :subtitle="paper.subject_name || ''">
      <template #extra>
        <n-space align="center">
          <CountdownTimer
            v-if="showCountdown"
            :expires-at="paper.expires_at"
            @expire="handleExpire"
          />
          <n-tag v-else-if="isInProgress" size="large">不限时</n-tag>
          <n-tag v-else-if="paper.status === 'completed'" type="success" size="large">已完成</n-tag>
          <n-tag v-else-if="paper.status === 'expired'" type="error" size="large">已过期</n-tag>
          <n-button @click="handleBack">返回</n-button>
        </n-space>
      </template>
    </n-page-header>

    <!-- 练习中 -->
    <n-spin :show="loading">
      <div
        v-if="!loading && questions.length > 0"
        :style="{ display: 'flex', gap: '16px', marginTop: '24px', flexDirection: isMobile ? 'column' : 'row' }"
      >
        <!-- 左侧题目区域 - 显示所有题目 -->
        <div style="flex: 1; min-width: 0;">
          <n-space vertical size="large">
            <n-card 
              v-for="(question, qIndex) in questions" 
              :key="question.id"
              :id="`question-${qIndex}`"
            >
              <template #header>
                <div style="display: flex; align-items: flex-start; gap: 8px; flex-wrap: wrap;">
                  <span>{{ qIndex + 1 }}.({{ getTypeLabel(question.type) }}) </span>
                  <TableRenderer :content="question.question" />
                </div>
              </template>
              <n-space vertical size="large">
                <n-text strong style="font-size: 14px; color: #666;">分值: {{ question.score || 2 }}分</n-text>
                
                <!-- 单选题和判断题 -->
                <div v-if="question.type === 'single' || question.type === 'judge'">
                  <n-radio-group v-model:value="answers[question.id]" :disabled="isReadOnly">
                    <n-space vertical>
                      <n-radio
                        v-for="(option, index) in question.options"
                        :key="index"
                        :value="getOptionValue(option)"
                        size="large"
                      >
                        <FormulaRenderer :content="option" />
                      </n-radio>
                    </n-space>
                  </n-radio-group>
                </div>

                <!-- 多选题 -->
                <div v-else-if="question.type === 'multiple'">
                  <n-checkbox-group v-model:value="multiAnswers[question.id]" :disabled="isReadOnly">
                    <n-space vertical>
                      <n-checkbox
                        v-for="(option, index) in question.options"
                        :key="index"
                        :value="getOptionValue(option)"
                        size="large"
                      >
                        <FormulaRenderer :content="option" />
                      </n-checkbox>
                    </n-space>
                  </n-checkbox-group>
                </div>

                <!-- 填空题 -->
                <template v-if="question.type === 'fill'">
                  <n-input
                    v-model:value="answers[question.id]"
                    placeholder="请输入答案"
                    size="large"
                    :disabled="isReadOnly"
                  />
                </template>
                <!-- 大题：文本+图片上传 -->
                <template v-else-if="question.type === 'major'">
                  <n-input
                    v-model:value="answers[question.id]"
                    placeholder="请输入答案"
                    size="large"
                    style="margin-bottom: 8px;"
                    :disabled="isReadOnly"
                  />
                  <ImageUploader v-model="majorImages[question.id]" :max="3" :disabled="isReadOnly" />
                </template>
              </n-space>
            </n-card>
          </n-space>
        </div>

        <!-- 桌面端：右侧答题卡 - 固定定位 -->
        <div v-if="!isMobile" style="width: 300px; position: sticky; top: 24px; align-self: flex-start;">
          <n-card :title="`答题卡 (${answeredCount}/${questions.length})`" size="small">
            <n-space vertical size="large">
              <!-- 题号网格 -->
              <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;">
                <n-button
                  v-for="(q, idx) in questions"
                  :key="idx"
                  :type="isAnswered(idx) ? 'primary' : 'default'"
                  size="medium"
                  @click="scrollToQuestion(idx)"
                  style="width: 100%;"
                >
                  {{ idx + 1 }}
                </n-button>
              </div>

              <!-- 提交按钮 -->
              <n-button
                v-if="isInProgress"
                type="primary"
                block
                size="large"
                :loading="submitting"
                @click="submitAnswers"
              >
                提交
              </n-button>
            </n-space>
          </n-card>
        </div>
      </div>

      <!-- 移动端：底部悬浮操作栏 -->
      <div
        v-if="isMobile && !loading && questions.length > 0"
        class="mobile-answer-bar"
      >
        <n-button style="flex: 1;" @click="showAnswerSheet = true">
          答题卡 ({{ answeredCount }}/{{ questions.length }})
        </n-button>
        <n-button
          v-if="isInProgress"
          type="primary"
          style="flex: 1;"
          :loading="submitting"
          @click="submitAnswers"
        >
          提交
        </n-button>
      </div>

      <!-- 移动端：答题卡抽屉 -->
      <n-drawer
        v-if="isMobile"
        v-model:show="showAnswerSheet"
        placement="bottom"
        :height="340"
      >
        <n-drawer-content :title="`答题卡 (${answeredCount}/${questions.length})`" :native-scrollbar="false" closable>
          <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px;">
            <n-button
              v-for="(q, idx) in questions"
              :key="idx"
              :type="isAnswered(idx) ? 'primary' : 'default'"
              size="medium"
              @click="handleSheetJump(idx)"
              style="width: 100%;"
            >
              {{ idx + 1 }}
            </n-button>
          </div>
        </n-drawer-content>
      </n-drawer>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter, useRoute } from 'vue-router'
import { examPaperApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import FormulaRenderer from '@/components/FormulaRenderer.vue'
import TableRenderer from '@/components/TableRenderer.vue'
import ImageUploader from '@/components/ImageUploader.vue'
import CountdownTimer from '@/components/CountdownTimer.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'

const message = useMessage()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

// 响应式：移动端答题卡改为底部抽屉
const { isMobile } = useBreakpoint()
const showAnswerSheet = ref(false)

// 移动端答题卡跳题：跳转后关闭抽屉
const handleSheetJump = (index) => {
  scrollToQuestion(index)
  showAnswerSheet.value = false
}

const loading = ref(false)
const submitting = ref(false)
const paper = ref({
  title: '',
  subject_name: '',
  status: 'in_progress',
  duration: null,
  expires_at: null,
  paper_type: 'normal'
})
const questions = ref([])
const answers = ref({})
const multiAnswers = ref({})
const majorImages = ref({})

const isInProgress = computed(() => paper.value.status === 'in_progress')
const isReadOnly = computed(() => !isInProgress.value)
const hasTimeLimit = computed(() => Number(paper.value.duration) > 0)
const showCountdown = computed(() => isInProgress.value && hasTimeLimit.value && Boolean(paper.value.expires_at))

const answeredCount = computed(() => {
  let count = 0
  questions.value.forEach(q => {
    if (q.type === 'multiple') {
      if (multiAnswers.value[q.id] && multiAnswers.value[q.id].length > 0) {
        count++
      }
    } else {
      if (answers.value[q.id]) {
        count++
      }
    }
  })
  return count
})

const getTypeLabel = (type) => {
  const map = {
    single: '单选题',
    multiple: '多选题',
    judge: '判断题',
    fill: '填空题',
    major: '大型题'
  }
  return map[type] || type
}

const getOptionValue = (option) => {
  const match = option.match(/^([A-Z])\./)
  return match ? match[1] : option
}

const isAnswered = (index) => {
  const q = questions.value[index]
  if (!q) return false
  
  if (q.type === 'multiple') {
    return multiAnswers.value[q.id] && multiAnswers.value[q.id].length > 0
  }
  return answers.value[q.id] && answers.value[q.id].trim() !== ''
}

const scrollToQuestion = (index) => {
  const element = document.getElementById(`question-${index}`)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const loadPaper = async () => {
  loading.value = true
  try {
    const paperId = route.params.id
    const response = await examPaperApi.get(paperId, userId.value)
    
    // 后端返回格式: { code, message, data: { paper, questions } }
    const data = response.data || response
    
    paper.value = data.paper || {}
    questions.value = data.questions || []
    
    // 初始化答案对象
    const newAnswers = {}
    const newMultiAnswers = {}
    const questionsList = data.questions || []
    
    questionsList.forEach(q => {
      // 如果有已保存的答案，加载它
      const savedAnswer = q.user_answer || ''
      
      if (q.type === 'multiple') {
        newMultiAnswers[q.id] = savedAnswer ? savedAnswer.split(',') : []
      } else {
        newAnswers[q.id] = savedAnswer
      }
      
      if (q.type === 'major') {
        majorImages.value[q.id] = q.answer_images || []
      }
    })
    answers.value = newAnswers
    multiAnswers.value = newMultiAnswers
  } catch (error) {
    message.error(error.message || '加载试卷失败')
    router.push('/practice')
  } finally {
    loading.value = false
  }
}

const handleExpire = () => {
  if (!showCountdown.value || submitting.value) return

  message.warning('试卷时间已到，自动提交')
  submitAnswers({ force: true })
}

const submitAnswers = async ({ force = false } = {}) => {
  if (!isInProgress.value || submitting.value) return

  // 检查是否所有题都已作答
  const unanswered = questions.value.filter(q => {
    if (q.type === 'multiple') {
      return !multiAnswers.value[q.id] || multiAnswers.value[q.id].length === 0
    }
    return !answers.value[q.id]
  })

  if (unanswered.length > 0 && !force) {
    message.warning(`还有 ${unanswered.length} 题未作答`)
    return
  }

  submitting.value = true
  try {
    // 格式化答案
    const formattedAnswers = questions.value.map(q => {
      let user_answer = ''
      if (q.type === 'multiple') {
        user_answer = (multiAnswers.value[q.id] || []).sort().join(',')
      } else {
        user_answer = answers.value[q.id] || ''
      }
      let images = q.type === 'major' ? (majorImages.value[q.id] || []) : []
      return {
        question_id: q.id,
        user_answer,
        images
      }
    })

    const data = await examPaperApi.submit(route.params.id, userId.value, formattedAnswers)

    // 提交成功后跳转到练习记录页面
    message.success(`提交成功！`)
    
    // 延迟跳转，让用户看到成功提示
    setTimeout(() => {
      router.push('/practice-history')
    }, 1500)
  } catch (error) {
    message.error(error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

const handleBack = () => {
  if (paper.value.paper_type === 'error') {
    router.push('/error-practice')
  } else {
    router.push('/practice')
  }
}

onMounted(() => {
  loadPaper()
})
</script>

<style scoped>
/* 移动端底部悬浮操作栏 */
.mobile-answer-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 100;
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  padding-bottom: calc(10px + var(--safe-bottom, 0px));
  background: var(--n-color, #fff);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
}

/* 为底部操作栏预留空间，避免遮挡最后一道题 */
@media (max-width: 768px) {
  .n-spin-content {
    padding-bottom: 72px;
  }
}
</style>
