<template>
  <n-modal
    v-model:show="showDialog"
    preset="card"
    title="预览并编辑题目"
    style="width: 90%; max-width: 1200px; max-height: 90vh;"
    :mask-closable="false"
    :scrollable="true"
  >
    <n-alert type="info" style="margin-bottom: 16px;">
      AI已解析出 {{ questions.length }} 道题目，请检查并编辑后确认导入
    </n-alert>

    <div style="max-height: 60vh; overflow-y: auto; padding-right: 8px;">
      <n-space vertical :size="12">
        <n-card
          v-for="(question, index) in questions"
          :key="index"
          :title="`题目 ${index + 1}`"
          size="small"
        >
        <template #header-extra>
          <n-space>
            <n-button size="small" @click="handleDelete(index)" type="error" ghost>
              删除
            </n-button>
          </n-space>
        </template>

        <n-form :model="question" label-placement="left" label-width="70" size="small">
          <!-- 题型 -->
          <n-form-item label="题型">
            <n-select
              v-model:value="question.type"
              :options="typeOptions"
              @update:value="handleTypeChange(index)"
            />
          </n-form-item>

          <!-- 题干 -->
          <n-form-item label="题干">
            <n-input
              v-model:value="question.question"
              type="textarea"
              :rows="2"
              placeholder="请输入题干"
            />
          </n-form-item>

          <!-- 选项（单选、多选） -->
          <n-form-item
            v-if="question.type === 'single' || question.type === 'multiple'"
            label="选项"
          >
            <n-space vertical style="width: 100%;" :size="4">
              <n-input
                v-for="(opt, key) in question.options"
                :key="key"
                v-model:value="question.options[key]"
                :placeholder="`选项 ${key}`"
                size="small"
              >
                <template #prefix>{{ key }}.</template>
              </n-input>
            </n-space>
          </n-form-item>

          <!-- 答案 -->
          <n-form-item label="答案">
            <n-input
              v-model:value="question.answer"
              placeholder="请输入答案"
              size="small"
            />
          </n-form-item>

          <!-- 解析 -->
          <n-form-item label="解析">
            <n-input
              v-model:value="question.analysis"
              type="textarea"
              :rows="1"
              placeholder="请输入解析（可选）"
            />
          </n-form-item>
        </n-form>
      </n-card>
    </n-space>
    </div>

    <template #footer>
      <n-space justify="space-between">
        <n-text depth="3">共 {{ questions.length }} 道题目</n-text>
        <n-space>
          <n-button @click="handleCancel">取消</n-button>
          <n-button
            type="primary"
            :loading="saving"
            :disabled="questions.length === 0"
            @click="handleConfirm"
          >
            确认导入
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  questions: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:show', 'confirm', 'cancel'])

const message = useMessage()
const saving = ref(false)

const showDialog = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const questions = ref([])

const typeOptions = [
  { label: '单选题', value: 'single' },
  { label: '多选题', value: 'multiple' },
  { label: '判断题', value: 'judge' },
  { label: '填空题', value: 'fill' },
  { label: '大题', value: 'major' }
]

// 监听props变化，初始化题目列表
watch(() => props.questions, (newQuestions) => {
  questions.value = JSON.parse(JSON.stringify(newQuestions))
}, { immediate: true, deep: true })

// 题型变化处理
const handleTypeChange = (index) => {
  const question = questions.value[index]
  
  // 如果切换到判断题，设置默认选项
  if (question.type === 'judge') {
    question.options = { '对': '对', '错': '错' }
  }
  
  // 如果切换到填空题或大题，清空选项
  if (question.type === 'fill' || question.type === 'major') {
    question.options = {}
  }
  
  // 如果切换到单选或多选，确保有选项
  if ((question.type === 'single' || question.type === 'multiple') && Object.keys(question.options || {}).length === 0) {
    question.options = { 'A': '', 'B': '', 'C': '', 'D': '' }
  }
}

// 删除题目
const handleDelete = (index) => {
  questions.value.splice(index, 1)
  message.success('已删除')
}

// 取消
const handleCancel = () => {
  showDialog.value = false
  emit('cancel')
}

// 确认导入
const handleConfirm = () => {
  // 验证题目
  for (let i = 0; i < questions.value.length; i++) {
    const q = questions.value[i]
    
    if (!q.question || !q.question.trim()) {
      message.error(`题目 ${i + 1} 的题干不能为空`)
      return
    }
    
    if (!q.answer || !q.answer.trim()) {
      message.error(`题目 ${i + 1} 的答案不能为空`)
      return
    }
    
    if ((q.type === 'single' || q.type === 'multiple') && (!q.options || Object.keys(q.options).length === 0)) {
      message.error(`题目 ${i + 1} 的选项不能为空`)
      return
    }
  }
  
  emit('confirm', questions.value)
}
</script>
