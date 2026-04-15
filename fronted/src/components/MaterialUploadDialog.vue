<template>
  <n-modal
    v-model:show="showDialog"
    preset="card"
    title="上传资料"
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
        />
      </n-form-item>

      <!-- 资料名称 -->
      <n-form-item label="资料名称" path="name">
        <n-input
          v-model:value="formData.name"
          placeholder="请输入资料名称"
          clearable
        />
      </n-form-item>

      <!-- 资料类型 -->
      <n-form-item label="资料类型" path="material_type">
        <n-select
          v-model:value="formData.material_type"
          :options="materialTypeOptions"
          placeholder="请选择资料类型"
        />
      </n-form-item>

      <!-- 标签 -->
      <n-form-item label="标签（可选）">
        <n-dynamic-tags v-model:value="formData.tags" />
      </n-form-item>

      <!-- 文件上传 -->
      <n-form-item label="选择文件" path="file">
        <n-upload
          ref="uploadRef"
          :max="1"
          :default-upload="false"
          :show-file-list="true"
          @change="handleFileChange"
          accept=".pdf,.doc,.docx,.txt,.md,.jpg,.jpeg,.png"
        >
          <n-upload-dragger>
            <div style="margin-bottom: 12px;">
              <n-icon size="48" :depth="3">
                <CloudUploadOutline />
              </n-icon>
            </div>
            <n-text style="font-size: 16px;">
              点击或拖拽文件到此区域上传
            </n-text>
            <n-p depth="3" style="margin: 8px 0 0 0;">
              支持 PDF、Word、文本、图片格式，单个文件不超过50MB
            </n-p>
          </n-upload-dragger>
        </n-upload>
      </n-form-item>

      <!-- 上传进度 -->
      <n-form-item v-if="uploading">
        <n-progress
          type="line"
          :percentage="uploadProgress"
          :indicator-placement="'inside'"
          processing
        />
      </n-form-item>
    </n-form>

    <template #footer>
      <n-space justify="end">
        <n-button @click="handleCancel" :disabled="uploading">取消</n-button>
        <n-button
          type="primary"
          :loading="uploading"
          :disabled="!canUpload"
          @click="handleUpload"
        >
          上传
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { CloudUploadOutline } from '@vicons/ionicons5'
import { materialApi, subjectApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:show', 'uploaded'])

const message = useMessage()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const showDialog = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const formRef = ref(null)
const uploadRef = ref(null)
const loadingSubjects = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const subjects = ref([])
const selectedFile = ref(null)

const formData = ref({
  subject_id: null,
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

const subjectOptions = computed(() => {
  return subjects.value.map(s => ({
    label: s.name,
    value: s.id
  }))
})

const canUpload = computed(() => {
  return formData.value.subject_id &&
         formData.value.name &&
         selectedFile.value
})

const rules = {
  subject_id: {
    required: true,
    type: 'number',
    message: '请选择科目',
    trigger: ['blur', 'change']
  },
  name: {
    required: true,
    message: '请输入资料名称',
    trigger: ['blur', 'input']
  },
  material_type: {
    required: true,
    message: '请选择资料类型',
    trigger: ['blur', 'change']
  }
}

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

const handleFileChange = ({ fileList }) => {
  if (fileList.length > 0) {
    selectedFile.value = fileList[0].file
    
    // 如果资料名称为空，自动填充文件名（去除扩展名）
    if (!formData.value.name) {
      const filename = fileList[0].name
      formData.value.name = filename.substring(0, filename.lastIndexOf('.')) || filename
    }
  } else {
    selectedFile.value = null
  }
}

const handleUpload = async () => {
  try {
    await formRef.value?.validate()
    
    if (!selectedFile.value) {
      message.warning('请选择文件')
      return
    }
    
    // 检查文件大小
    const maxSize = 50 * 1024 * 1024 // 50MB
    if (selectedFile.value.size > maxSize) {
      message.error('文件大小不能超过50MB')
      return
    }
    
    uploading.value = true
    uploadProgress.value = 0
    
    // 模拟上传进度
    const progressInterval = setInterval(() => {
      if (uploadProgress.value < 90) {
        uploadProgress.value += 10
      }
    }, 200)
    
    try {
      const response = await materialApi.upload(
        userId.value,
        formData.value.subject_id,
        selectedFile.value,
        formData.value.name,
        formData.value.material_type,
        formData.value.tags
      )
      
      clearInterval(progressInterval)
      uploadProgress.value = 100
      
      emit('uploaded', response.data || response)
      handleCancel()
    } catch (error) {
      clearInterval(progressInterval)
      throw error
    }
  } catch (error) {
    if (error.errors) {
      // 表单验证错误
      return
    }
    message.error(error.message || '上传失败')
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}

const handleCancel = () => {
  showDialog.value = false
  
  // 重置表单
  formData.value = {
    subject_id: null,
    name: '',
    material_type: 'other',
    tags: []
  }
  selectedFile.value = null
  uploadProgress.value = 0
  
  // 清空文件列表
  if (uploadRef.value) {
    uploadRef.value.clear()
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    loadSubjects()
  }
})
</script>
