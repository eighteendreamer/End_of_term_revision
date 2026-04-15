<template>
  <n-modal 
    v-model:show="showDialog" 
    preset="card" 
    title="创建新试卷" 
    style="width: 600px;"
    :mask-closable="false"
  >
    <n-form ref="formRef" :model="formData" :rules="rules">
      <!-- 选择科目 -->
      <n-form-item label="选择科目" path="subject_id">
        <n-select
          v-model:value="formData.subject_id"
          :options="subjectOptions"
          placeholder="请选择科目"
          :loading="loadingSubjects"
          @update:value="handleSubjectChange"
        />
      </n-form-item>

      <!-- 题型与数量 -->
      <n-form-item label="题型与数量" path="question_counts">
        <n-space vertical style="width: 100%;">
          <n-alert v-if="availableTypes.length === 0" type="warning">
            {{ paperType === 'error' ? '该科目下暂无错题' : '该科目下暂无题目，请先导入题目' }}
          </n-alert>
          
          <n-checkbox-group v-model:value="selectedTypes">
            <n-space vertical>
              <n-space v-for="type in typeOptions" :key="type.value" align="center">
                <n-checkbox
                  :value="type.value"
                  :label="type.label"
                  :disabled="!availableTypes.includes(type.value)"
                />
                <n-input-number
                  v-model:value="formData.question_counts[type.value]"
                  :min="0"
                  :max="100"
                  :disabled="!selectedTypes.includes(type.value)"
                  style="width: 120px;"
                >
                  <template #suffix>题</template>
                </n-input-number>
              </n-space>
            </n-space>
          </n-checkbox-group>
        </n-space>
      </n-form-item>

      <!-- 试卷时长 -->
      <n-form-item label="试卷时长" path="duration">
        <n-select
          v-model:value="formData.duration"
          :options="durationOptions"
          placeholder="请选择时长"
        />
      </n-form-item>

      <!-- 试卷标题（可选） -->
      <n-form-item label="试卷标题（可选）" path="title">
        <n-input
          v-model:value="formData.title"
          placeholder="留空自动生成"
          clearable
        />
      </n-form-item>
    </n-form>

    <template #footer>
      <n-space justify="end">
        <n-button @click="handleCancel">取消</n-button>
        <n-button 
          type="primary" 
          :loading="creating"
          :disabled="!canCreate"
          @click="handleCreate"
        >
          创建试卷
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { subjectApi, questionApi, errorApi, examPaperApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  paperType: {
    type: String,
    default: 'normal',  // 'normal' or 'error'
    validator: (value) => ['normal', 'error'].includes(value)
  }
})

const emit = defineEmits(['update:show', 'created'])

const message = useMessage()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const showDialog = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const formRef = ref(null)
const loadingSubjects = ref(false)
const creating = ref(false)
const subjects = ref([])
const availableTypes = ref([])
const selectedTypes = ref([])

const formData = ref({
  subject_id: null,
  question_counts: {
    single: 0,
    multiple: 0,
    judge: 0,
    fill: 0,
    major: 0
  },
  duration: 60,  // 默认1小时
  title: ''
})

const typeOptions = [
  { label: '单选题', value: 'single' },
  { label: '多选题', value: 'multiple' },
  { label: '判断题', value: 'judge' },
  { label: '填空题', value: 'fill' },
  { label: '大型题', value: 'major' }
]

const durationOptions = [
  { label: '30分钟', value: 30 },
  { label: '1小时', value: 60 },
  { label: '2小时', value: 120 },
  { label: '3小时', value: 180 },
  { label: '不限时', value: null }
]

const subjectOptions = computed(() => {
  return subjects.value.map(s => ({
    label: s.name,
    value: s.id
  }))
})

const canCreate = computed(() => {
  if (!formData.value.subject_id) return false
  const total = Object.values(formData.value.question_counts).reduce((a, b) => a + b, 0)
  return total > 0
})

const rules = {
  subject_id: {
    required: true,
    type: 'number',
    message: '请选择科目',
    trigger: ['blur', 'change']
  }
}

// 加载科目列表
const loadSubjects = async () => {
  loadingSubjects.value = true
  try {
    subjects.value = await subjectApi.list(userId.value)
  } catch (error) {
    message.error(error.message || '加载科目列表失败')
  } finally {
    loadingSubjects.value = false
  }
}

// 科目变化时获取可用题型
const handleSubjectChange = async (subjectId) => {
  try {
    let data
    if (props.paperType === 'error') {
      // 错题练习：获取错题题型
      data = await errorApi.getTypes(subjectId, userId.value)
    } else {
      // 普通练习：获取题库题型
      data = await questionApi.getTypes(subjectId, userId.value)
    }
    
    availableTypes.value = data.types || []
    selectedTypes.value = []
    
    // 重置题目数量
    formData.value.question_counts = {
      single: 0,
      multiple: 0,
      judge: 0,
      fill: 0,
      major: 0
    }
  } catch (error) {
    message.error(error.message || '获取题型失败')
  }
}

// 生成试卷标题
const generateTitle = () => {
  const subject = subjects.value.find(s => s.id === formData.value.subject_id)
  const now = new Date()
  const dateStr = now.toLocaleString('zh-CN', { 
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
  const typeText = props.paperType === 'error' ? '错题' : '练习'
  return `${subject?.name || '未知科目'} ${typeText} - ${dateStr}`
}

// 创建试卷
const handleCreate = async () => {
  try {
    // 手动验证
    if (!formData.value.subject_id) {
      message.warning('请选择科目')
      return
    }
    
    // 验证题目数量
    const total = Object.values(formData.value.question_counts).reduce((a, b) => a + b, 0)
    if (total === 0) {
      message.warning('请至少选择一道题目')
      return
    }
    
    creating.value = true
    
    const title = formData.value.title || generateTitle()
    
    const response = await examPaperApi.create({
      user_id: userId.value,
      subject_id: formData.value.subject_id,
      paper_type: props.paperType,
      title: title,
      duration: formData.value.duration,
      question_counts: formData.value.question_counts
    })
    
    const data = response.data || response
    emit('created', data)
    handleCancel()
  } catch (error) {
    console.error('创建试卷错误:', error)
    message.error(error.message || '创建试卷失败')
  } finally {
    creating.value = false
  }
}

// 取消
const handleCancel = () => {
  showDialog.value = false
  // 重置表单
  formData.value = {
    subject_id: null,
    question_counts: {
      single: 0,
      multiple: 0,
      judge: 0,
      fill: 0,
      major: 0
    },
    duration: 60,
    title: ''
  }
  selectedTypes.value = []
  availableTypes.value = []
}

// 监听对话框显示状态
watch(() => props.show, (newVal) => {
  if (newVal) {
    loadSubjects()
  }
})
</script>

<style scoped>
/* 样式已由 Naive UI 提供 */
</style>
