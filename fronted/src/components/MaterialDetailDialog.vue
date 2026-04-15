<template>
  <n-modal
    v-model:show="showDialog"
    preset="card"
    :title="material?.name || '资料详情'"
    style="width: 800px; max-height: 85vh;"
    :mask-closable="true"
    :scrollable="true"
  >
    <n-spin :show="loading">
      <div v-if="material">
        <!-- 快速信息栏 -->
        <n-space align="center" justify="space-between" style="margin-bottom: 16px; padding: 12px; background: #f6f8fa; border-radius: 8px;">
          <n-space align="center" :size="12">
            <n-icon size="24" :color="getFileTypeColor(material.file_type)">
              <component :is="getFileTypeIcon(material.file_type)" />
            </n-icon>
            <div>
              <div style="font-weight: 600; font-size: 16px; margin-bottom: 4px;">{{ material.name }}</div>
              <n-space :size="8">
                <n-tag size="small" :type="getMaterialTypeColor(material.material_type)">
                  {{ getMaterialTypeLabel(material.material_type) }}
                </n-tag>
                <n-tag size="small" :type="getStatusType(material.status)" :bordered="false">
                  {{ getStatusLabel(material.status) }}
                </n-tag>
                <n-text depth="3" style="font-size: 12px;">{{ material.subject_name }}</n-text>
              </n-space>
            </div>
          </n-space>
          <n-statistic label="题目数量" :value="material.question_count">
            <template #suffix>道</template>
          </n-statistic>
        </n-space>

        <!-- 操作按钮 -->
        <n-space style="margin-bottom: 16px;">
          <n-button
            v-if="material.file_url"
            type="primary"
            @click="handleDownload"
          >
            <template #icon>
              <n-icon><DownloadOutline /></n-icon>
            </template>
            下载文件
          </n-button>
          <n-button @click="showEditDialog = true">
            <template #icon>
              <n-icon><CreateOutline /></n-icon>
            </template>
            编辑信息
          </n-button>
          <n-button
            v-if="material.status === 'error' || !material.content_text"
            type="warning"
            :loading="extracting"
            @click="handleExtractText"
          >
            <template #icon>
              <n-icon><RefreshOutline /></n-icon>
            </template>
            {{ material.status === 'error' ? '重新提取文本' : '提取文本' }}
          </n-button>
          <n-button
            v-if="material.content_text"
            type="success"
            @click="handleGenerateQuestions"
          >
            <template #icon>
              <n-icon><BulbOutline /></n-icon>
            </template>
            生成题目
          </n-button>
        </n-space>

        <!-- 内容与题目标签页 -->
        <n-card :bordered="false" style="background-color: #f6f8fa;">
          <n-tabs type="line" animated>
            <!-- 基本信息标签 -->
            <n-tab-pane name="info" tab="基本信息">
              <n-descriptions :column="2" size="small">
                <n-descriptions-item label="文件类型">
                  <n-space align="center" :size="4">
                    <n-icon size="16" :color="getFileTypeColor(material.file_type)">
                      <component :is="getFileTypeIcon(material.file_type)" />
                    </n-icon>
                    <span>{{ material.file_type.toUpperCase() }}</span>
                  </n-space>
                </n-descriptions-item>
                <n-descriptions-item label="文件大小">
                  {{ formatFileSize(material.file_size) }}
                </n-descriptions-item>
                <n-descriptions-item label="资料类型">
                  <n-tag size="small" :type="getMaterialTypeColor(material.material_type)">
                    {{ getMaterialTypeLabel(material.material_type) }}
                  </n-tag>
                </n-descriptions-item>
                <n-descriptions-item label="状态">
                  <n-tag size="small" :type="getStatusType(material.status)" :bordered="false">
                    {{ getStatusLabel(material.status) }}
                  </n-tag>
                </n-descriptions-item>
                <n-descriptions-item label="上传时间" :span="2">
                  {{ formatDateTime(material.created_at) }}
                </n-descriptions-item>
                <n-descriptions-item v-if="material.tags && material.tags.length > 0" label="标签" :span="2">
                  <n-space :size="4">
                    <n-tag
                      v-for="tag in material.tags"
                      :key="tag"
                      size="small"
                      :bordered="false"
                    >
                      {{ tag }}
                    </n-tag>
                  </n-space>
                </n-descriptions-item>
                <n-descriptions-item v-if="material.error_message" label="错误信息" :span="2">
                  <n-text type="error">{{ material.error_message }}</n-text>
                </n-descriptions-item>
              </n-descriptions>
            </n-tab-pane>

            <!-- 文本内容标签 -->
            <n-tab-pane name="content" :disabled="!material.content_text">
              <template #tab>
                <n-space align="center" :size="4">
                  <span>文本内容</span>
                  <n-tag v-if="material.content_text" size="tiny" round>
                    {{ material.content_text.length }} 字符
                  </n-tag>
                </n-space>
              </template>
              <div v-if="material.content_text" style="max-height: 400px; overflow-y: auto; padding: 16px; background: white; border-radius: 4px;">
                <n-text style="white-space: pre-wrap; line-height: 1.8; font-size: 14px; color: #333;">
                  {{ material.content_text }}
                </n-text>
              </div>
              <n-empty v-else description="暂无文本内容" style="padding: 60px 0;" />
            </n-tab-pane>

            <!-- 生成的题目标签 -->
            <n-tab-pane name="questions">
              <template #tab>
                <n-space align="center" :size="4">
                  <span>生成的题目</span>
                  <n-tag size="tiny" round :type="questions.length > 0 ? 'success' : 'default'">
                    {{ questions.length }}
                  </n-tag>
                </n-space>
              </template>
              
              <n-empty v-if="questions.length === 0" description="暂无生成的题目，点击上方生成题目按钮开始生成" style="padding: 60px 0;" />
              
              <div v-else style="max-height: 400px; overflow-y: auto;">
                <n-list>
                  <n-list-item v-for="(question, index) in questions" :key="question.id" style="background: white; margin-bottom: 8px; border-radius: 4px; padding: 12px;">
                    <n-space vertical style="width: 100%;" :size="8">
                      <n-space align="center" justify="space-between">
                        <n-space align="center" :size="8">
                          <n-tag size="small" round :bordered="false" style="font-weight: 600;">
                            {{ index + 1 }}
                          </n-tag>
                          <n-tag size="small" :type="getQuestionTypeColor(question.type)">
                            {{ getQuestionTypeLabel(question.type) }}
                          </n-tag>
                          <n-tag size="small" :bordered="false">
                            置信度 {{ (question.confidence_score * 100).toFixed(0) }}%
                          </n-tag>
                        </n-space>
                        <n-text depth="3" style="font-size: 11px;">
                          {{ formatDateTime(question.generated_at) }}
                        </n-text>
                      </n-space>
                      <n-text style="line-height: 1.6;">{{ question.question }}</n-text>
                    </n-space>
                  </n-list-item>
                </n-list>
              </div>
            </n-tab-pane>
          </n-tabs>
        </n-card>
      </div>
    </n-spin>

    <!-- 编辑对话框 -->
    <n-modal
      v-model:show="showEditDialog"
      preset="card"
      title="编辑资料信息"
      style="width: 500px;"
      :mask-closable="false"
    >
      <n-form ref="editFormRef" :model="editForm">
        <n-form-item label="资料名称" path="name">
          <n-input v-model:value="editForm.name" placeholder="请输入资料名称" />
        </n-form-item>
        <n-form-item label="资料类型" path="material_type">
          <n-select
            v-model:value="editForm.material_type"
            :options="materialTypeOptions"
            placeholder="请选择资料类型"
          />
        </n-form-item>
        <n-form-item label="标签">
          <n-dynamic-tags v-model:value="editForm.tags" />
        </n-form-item>
      </n-form>
      
      <template #footer>
        <n-space justify="end">
          <n-button @click="showEditDialog = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">
            保存
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </n-modal>

  <!-- 题目生成对话框 -->
  <QuestionGenerationDialog
    v-model:show="showGenerationDialog"
    :material-id="materialId"
    @generated="handleQuestionsGenerated"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import {
  DownloadOutline,
  CreateOutline,
  DocumentOutline,
  ImageOutline,
  CodeOutline,
  RefreshOutline,
  BulbOutline
} from '@vicons/ionicons5'
import { materialApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import QuestionGenerationDialog from '@/components/QuestionGenerationDialog.vue'

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

const emit = defineEmits(['update:show', 'updated'])

const message = useMessage()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const showDialog = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const loading = ref(false)
const saving = ref(false)
const extracting = ref(false)
const material = ref(null)
const questions = ref([])
const showEditDialog = ref(false)
const showGenerationDialog = ref(false)
const editFormRef = ref(null)

const editForm = ref({
  name: '',
  material_type: 'other',
  tags: []
})

const materialTypeOptions = [
  { label: '教材', value: 'textbook' },
  { label: '笔记', value: 'note' },
  { label: '习题', value: 'exercise' },
  { label: '其他', value: 'other' }
]

const loadMaterialDetail = async () => {
  if (!props.materialId) return
  
  loading.value = true
  try {
    const response = await materialApi.get(props.materialId, userId.value)
    const data = response.data || response
    material.value = data.material
    questions.value = data.questions || []
    
    // 初始化编辑表单
    editForm.value = {
      name: material.value.name,
      material_type: material.value.material_type,
      tags: material.value.tags || []
    }
  } catch (error) {
    message.error(error.message || '加载资料详情失败')
  } finally {
    loading.value = false
  }
}

const handleDownload = () => {
  if (material.value?.file_url) {
    window.open(material.value.file_url, '_blank')
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await materialApi.update(props.materialId, {
      user_id: userId.value,
      name: editForm.value.name,
      material_type: editForm.value.material_type,
      tags: editForm.value.tags
    })
    
    message.success('保存成功')
    showEditDialog.value = false
    
    // 重新加载详情
    await loadMaterialDetail()
    
    // 通知父组件更新列表
    emit('updated')
  } catch (error) {
    message.error(error.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleExtractText = async () => {
  extracting.value = true
  try {
    const response = await materialApi.extractText(props.materialId, userId.value)
    message.success('文本提取成功')
    
    // 重新加载详情
    await loadMaterialDetail()
    
    // 通知父组件更新列表
    emit('updated')
  } catch (error) {
    message.error(error.message || '文本提取失败')
  } finally {
    extracting.value = false
  }
}

const handleGenerateQuestions = () => {
  showGenerationDialog.value = true
}

const handleQuestionsGenerated = async () => {
  message.success('题目生成成功')
  // 重新加载详情以显示新生成的题目
  await loadMaterialDetail()
  emit('updated')
}

const getFileTypeIcon = (fileType) => {
  const iconMap = {
    pdf: DocumentOutline,
    doc: DocumentOutline,
    docx: DocumentOutline,
    txt: CodeOutline,
    md: CodeOutline,
    jpg: ImageOutline,
    jpeg: ImageOutline,
    png: ImageOutline
  }
  return iconMap[fileType] || DocumentOutline
}

const getFileTypeColor = (fileType) => {
  const colorMap = {
    pdf: '#f56c6c',
    doc: '#409eff',
    docx: '#409eff',
    txt: '#67c23a',
    md: '#67c23a',
    jpg: '#e6a23c',
    jpeg: '#e6a23c',
    png: '#e6a23c'
  }
  return colorMap[fileType] || '#909399'
}

const getMaterialTypeLabel = (type) => {
  const labelMap = {
    textbook: '教材',
    note: '笔记',
    exercise: '习题',
    other: '其他'
  }
  return labelMap[type] || type
}

const getMaterialTypeColor = (type) => {
  const colorMap = {
    textbook: 'success',
    note: 'warning',
    exercise: 'info',
    other: 'default'
  }
  return colorMap[type] || 'default'
}

const getStatusLabel = (status) => {
  const labelMap = {
    uploading: '上传中',
    processing: '处理中',
    ready: '就绪',
    error: '错误'
  }
  return labelMap[status] || status
}

const getStatusType = (status) => {
  const typeMap = {
    uploading: 'info',
    processing: 'warning',
    ready: 'success',
    error: 'error'
  }
  return typeMap[status] || 'default'
}

const getQuestionTypeLabel = (type) => {
  const labelMap = {
    single: '单选题',
    multiple: '多选题',
    judge: '判断题',
    blank: '填空题',
    essay: '大题'
  }
  return labelMap[type] || type
}

const getQuestionTypeColor = (type) => {
  const colorMap = {
    single: 'info',
    multiple: 'success',
    judge: 'warning',
    blank: 'default',
    essay: 'error'
  }
  return colorMap[type] || 'default'
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const formatDateTime = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

watch(() => props.show, (newVal) => {
  if (newVal && props.materialId) {
    loadMaterialDetail()
  }
})
</script>
