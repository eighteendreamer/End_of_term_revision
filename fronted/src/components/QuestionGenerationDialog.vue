<template>
  <n-modal
    v-model:show="showDialog"
    preset="card"
    title="生成练习题目"
    style="width: 600px;"
    :mask-closable="false"
  >
    <n-spin :show="generating">
      <n-form ref="formRef" :model="formData">
        <n-alert type="info" style="margin-bottom: 16px;">
          AI将根据资料内容自动生成练习题目。生成过程可能需要1-2分钟，请耐心等待。
        </n-alert>

        <!-- 题型选择 -->
        <n-form-item label="选择题型">
          <n-space vertical style="width: 100%;">
            <n-checkbox
              v-model:checked="formData.types.single.enabled"
              @update:checked="handleTypeToggle('single')"
            >
              单选题
            </n-checkbox>
            <n-input-number
              v-if="formData.types.single.enabled"
              v-model:value="formData.types.single.count"
              :min="1"
              :max="50"
              placeholder="数量"
              style="width: 200px; margin-left: 24px;"
            />

            <n-checkbox
              v-model:checked="formData.types.multiple.enabled"
              @update:checked="handleTypeToggle('multiple')"
            >
              多选题
            </n-checkbox>
            <n-input-number
              v-if="formData.types.multiple.enabled"
              v-model:value="formData.types.multiple.count"
              :min="1"
              :max="50"
              placeholder="数量"
              style="width: 200px; margin-left: 24px;"
            />

            <n-checkbox
              v-model:checked="formData.types.judge.enabled"
              @update:checked="handleTypeToggle('judge')"
            >
              判断题
            </n-checkbox>
            <n-input-number
              v-if="formData.types.judge.enabled"
              v-model:value="formData.types.judge.count"
              :min="1"
              :max="50"
              placeholder="数量"
              style="width: 200px; margin-left: 24px;"
            />

            <n-checkbox
              v-model:checked="formData.types.fill.enabled"
              @update:checked="handleTypeToggle('fill')"
            >
              填空题
            </n-checkbox>
            <n-input-number
              v-if="formData.types.fill.enabled"
              v-model:value="formData.types.fill.count"
              :min="1"
              :max="50"
              placeholder="数量"
              style="width: 200px; margin-left: 24px;"
            />

            <n-checkbox
              v-model:checked="formData.types.major.enabled"
              @update:checked="handleTypeToggle('major')"
            >
              大题
            </n-checkbox>
            <n-input-number
              v-if="formData.types.major.enabled"
              v-model:value="formData.types.major.count"
              :min="1"
              :max="20"
              placeholder="数量"
              style="width: 200px; margin-left: 24px;"
            />
          </n-space>
        </n-form-item>

        <!-- 统计信息 -->
        <n-form-item>
          <n-space>
            <n-tag type="info">
              总计: {{ totalCount }} 道题目
            </n-tag>
            <n-text depth="3" style="font-size: 12px;">
              预计生成时间: {{ estimatedTime }}
            </n-text>
          </n-space>
        </n-form-item>

        <!-- 生成进度 -->
        <n-form-item v-if="generating">
          <n-progress
            type="line"
            :percentage="progress"
            :indicator-placement="'inside'"
            processing
          />
          <n-text depth="3" style="font-size: 12px; margin-top: 8px;">
            {{ progressText }}
          </n-text>
        </n-form-item>
      </n-form>
    </n-spin>

    <template #footer>
      <n-space justify="end">
        <n-button @click="handleCancel" :disabled="generating">取消</n-button>
        <n-button
          type="primary"
          :loading="generating"
          :disabled="!canGenerate"
          @click="handleGenerate"
        >
          开始生成
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { materialApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  materialId: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['update:show', 'generated'])

const message = useMessage()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const showDialog = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const formRef = ref(null)
const generating = ref(false)
const progress = ref(0)
const progressText = ref('')

const formData = ref({
  types: {
    single: { enabled: true, count: 10 },
    multiple: { enabled: true, count: 5 },
    judge: { enabled: true, count: 5 },
    fill: { enabled: false, count: 5 },
    major: { enabled: false, count: 3 }
  }
})

const totalCount = computed(() => {
  let total = 0
  Object.values(formData.value.types).forEach(type => {
    if (type.enabled) {
      total += type.count
    }
  })
  return total
})

const estimatedTime = computed(() => {
  const seconds = Math.ceil(totalCount.value * 3) // 每道题约3秒
  if (seconds < 60) {
    return `${seconds}秒`
  }
  const minutes = Math.ceil(seconds / 60)
  return `${minutes}分钟`
})

const canGenerate = computed(() => {
  return totalCount.value > 0 && !generating.value
})

const handleTypeToggle = (type) => {
  // 确保至少有一个题型被选中
  const enabledCount = Object.values(formData.value.types).filter(t => t.enabled).length
  if (enabledCount === 0) {
    formData.value.types[type].enabled = true
    message.warning('至少选择一种题型')
  }
}

const handleGenerate = async () => {
  if (!props.materialId) {
    message.error('资料ID无效')
    return
  }

  generating.value = true
  progress.value = 0
  progressText.value = '正在准备生成...'

  try {
    // 构建请求参数
    const questionTypes = []
    const questionCounts = {}

    Object.entries(formData.value.types).forEach(([type, config]) => {
      if (config.enabled) {
        questionTypes.push(type)
        questionCounts[type] = config.count
      }
    })

    // 模拟进度更新
    const progressInterval = setInterval(() => {
      if (progress.value < 90) {
        progress.value += 5
        if (progress.value < 30) {
          progressText.value = '正在分析资料内容...'
        } else if (progress.value < 60) {
          progressText.value = '正在生成题目...'
        } else {
          progressText.value = '正在保存题目...'
        }
      }
    }, 1000)

    // 调用API生成题目
    const response = await materialApi.generateQuestions(
      props.materialId,
      userId.value,
      questionTypes,
      questionCounts
    )

    clearInterval(progressInterval)
    progress.value = 100
    progressText.value = '生成完成！'

    const data = response.data || response
    const stats = data.statistics || {}

    message.success(`成功生成 ${stats.total_generated || 0} 道题目`)

    // 通知父组件
    emit('generated', data)

    // 延迟关闭对话框
    setTimeout(() => {
      handleCancel()
    }, 1000)

  } catch (error) {
    message.error(error.message || '题目生成失败')
  } finally {
    generating.value = false
    progress.value = 0
  }
}

const handleCancel = () => {
  if (!generating.value) {
    showDialog.value = false
    // 重置表单
    formData.value = {
      types: {
        single: { enabled: true, count: 10 },
        multiple: { enabled: true, count: 5 },
        judge: { enabled: true, count: 5 },
        fill: { enabled: false, count: 5 },
        major: { enabled: false, count: 3 }
      }
    }
  }
}

watch(() => props.show, (newVal) => {
  if (!newVal) {
    progress.value = 0
    progressText.value = ''
  }
})
</script>
