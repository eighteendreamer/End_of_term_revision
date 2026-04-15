<template>
  <div>
    <n-page-header title="导入题目" subtitle="通过文件、图片或文本导入题目，AI 自动解析">
    </n-page-header>

    <n-space vertical size="large" style="margin-top: 24px;">
      <!-- 选择科目 -->
      <n-card title="1. 选择科目">
        <n-select
          v-model:value="selectedSubject"
          :options="subjectOptions"
          placeholder="请选择科目"
          :loading="loadingSubjects"
        />
      </n-card>

      <!-- 导入方式选择 -->
      <n-card title="2. 选择导入方式">
        <n-tabs v-model:value="importType" type="segment" @update:value="handleTabChange">
          <n-tab-pane name="file" tab="文件导入">
            <n-space vertical style="margin-top: 16px;">
              <n-alert type="info">
                支持 PDF、Word、文本文件。AI 将自动识别题目、选项、答案和解析。
              </n-alert>
              <n-upload
                ref="fileUploadRef"
                :custom-request="handleFileUpload"
                :show-file-list="false"
                :disabled="parsing"
                accept=".pdf,.docx,.doc,.txt"
              >
                <n-upload-dragger>
                  <div style="margin-bottom: 12px;">
                    <n-icon size="48" :depth="3">
                      <document-text-outline />
                    </n-icon>
                  </div>
                  <n-text style="font-size: 16px;">
                    {{ parsing ? '正在解析...' : '点击或拖拽文件到此区域上传' }}
                  </n-text>
                  <n-p depth="3" style="margin: 8px 0 0 0;">
                    支持 PDF、Word (.docx, .doc)、文本 (.txt) 格式
                  </n-p>
                </n-upload-dragger>
              </n-upload>
            </n-space>
          </n-tab-pane>

          <n-tab-pane name="image" tab="图片导入">
            <n-space vertical style="margin-top: 16px;">
              <n-alert type="info">
                支持 JPG、PNG 等图片格式。系统将使用 AI 视觉模型直接识别图片中的题目。
              </n-alert>
              
              <n-upload
                ref="imageUploadRef"
                :custom-request="handleImageUpload"
                :show-file-list="false"
                :disabled="parsing"
                accept="image/*"
              >
                <n-upload-dragger>
                  <div style="margin-bottom: 12px;">
                    <n-icon size="48" :depth="3">
                      <image-outline />
                    </n-icon>
                  </div>
                  <n-text style="font-size: 16px;">
                    {{ parsing ? '正在解析...' : '点击或拖拽图片到此区域上传' }}
                  </n-text>
                  <n-p depth="3" style="margin: 8px 0 0 0;">
                    支持 JPG、PNG、BMP 等图片格式
                  </n-p>
                </n-upload-dragger>
              </n-upload>
            </n-space>
          </n-tab-pane>

          <n-tab-pane name="text" tab="文本导入">
            <n-space vertical style="margin-top: 16px;">
              <n-alert type="info">
                直接粘贴题目文本，AI 将自动解析题目结构。
              </n-alert>
              <n-input
                v-model:value="textContent"
                type="textarea"
                placeholder="请粘贴题目内容，例如：&#10;&#10;1. 1+1等于多少？&#10;A. 1&#10;B. 2&#10;C. 3&#10;D. 4&#10;答案：B&#10;解析：基础加法运算"
                :rows="10"
              />
              <n-button
                type="primary"
                :loading="parsing"
                :disabled="!textContent || !selectedSubject"
                @click="handleTextParse"
                block
              >
                开始解析
              </n-button>
            </n-space>
          </n-tab-pane>
        </n-tabs>
      </n-card>

      <!-- 解析进度 -->
      <n-card v-if="parsing" title="解析进度">
        <n-space vertical>
          <n-progress type="line" :percentage="100" processing />
          <n-text>正在使用 AI 解析题目，请稍候...</n-text>
          <n-alert type="warning" style="margin-top: 12px;">
            AI 识别可能需要 30-120 秒，请耐心等待，不要关闭页面
          </n-alert>
        </n-space>
      </n-card>
    </n-space>

    <!-- 题目预览对话框 -->
    <QuestionPreviewDialog
      v-model:show="showPreview"
      :questions="parsedQuestions"
      @confirm="handleConfirmImport"
      @cancel="handleCancelPreview"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { subjectApi, importApi } from '@/api'
import { DocumentTextOutline, ImageOutline } from '@vicons/ionicons5'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import QuestionPreviewDialog from '@/components/QuestionPreviewDialog.vue'

const message = useMessage()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const parsing = ref(false)
const importing = ref(false)
const loadingSubjects = ref(false)
const subjects = ref([])
const selectedSubject = ref(null)
const importType = ref('file')
const textContent = ref('')
const fileUploadRef = ref(null)
const imageUploadRef = ref(null)
const lastUploadedFile = ref(null)

// 预览相关
const showPreview = ref(false)
const parsedQuestions = ref([])

// 科目选项
const subjectOptions = computed(() => {
  return subjects.value.map(s => ({
    label: s.name,
    value: s.id
  }))
})

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

// 处理标签页切换
const handleTabChange = () => {
  lastUploadedFile.value = null
  console.log('[前端] 切换标签页，清空文件缓存')
}

// 处理文件上传
const handleFileUpload = async ({ file, onFinish, onError }) => {
  if (!selectedSubject.value) {
    message.warning('请先选择科目')
    onError()
    return
  }

  if (parsing.value) {
    console.log('[前端] 正在解析中，跳过重复请求')
    onError()
    return
  }

  const fileKey = `${file.file.name}_${file.file.size}_${file.file.lastModified}`
  if (lastUploadedFile.value === fileKey) {
    message.warning('请勿重复上传同一个文件')
    onError()
    return
  }

  parsing.value = true
  try {
    const response = await importApi.previewFromFile(
      userId.value,
      selectedSubject.value,
      file.file
    )
    
    const data = response.data || response
    parsedQuestions.value = data.questions || []
    
    if (parsedQuestions.value.length === 0) {
      message.error('未能解析出题目')
      onError()
      return
    }
    
    message.success(response.message || `成功解析 ${parsedQuestions.value.length} 道题目`)
    showPreview.value = true
    lastUploadedFile.value = fileKey
    onFinish()
  } catch (error) {
    message.error(error.message || '解析失败')
    onError()
  } finally {
    parsing.value = false
  }
}

// 处理图片上传
const handleImageUpload = async ({ file, onFinish, onError }) => {
  if (!selectedSubject.value) {
    message.warning('请先选择科目')
    onError()
    return
  }

  if (parsing.value) {
    console.log('[前端] 正在解析中，跳过重复请求')
    onError()
    return
  }

  const fileKey = `${file.file.name}_${file.file.size}_${file.file.lastModified}`
  if (lastUploadedFile.value === fileKey) {
    message.warning('请勿重复上传同一张图片')
    onError()
    return
  }

  parsing.value = true
  try {
    const response = await importApi.previewFromImage(
      userId.value,
      selectedSubject.value,
      file.file
    )
    
    const data = response.data || response
    parsedQuestions.value = data.questions || []
    
    if (parsedQuestions.value.length === 0) {
      message.error('未能解析出题目')
      onError()
      return
    }
    
    message.success(response.message || `成功解析 ${parsedQuestions.value.length} 道题目`)
    showPreview.value = true
    lastUploadedFile.value = fileKey
    onFinish()
  } catch (error) {
    message.error(error.message || '解析失败')
    onError()
  } finally {
    parsing.value = false
  }
}

// 处理文本解析
const handleTextParse = async () => {
  if (!selectedSubject.value) {
    message.warning('请先选择科目')
    return
  }

  if (!textContent.value.trim()) {
    message.warning('请输入题目文本')
    return
  }

  parsing.value = true
  try {
    const response = await importApi.previewFromText({
      user_id: userId.value,
      subject_id: selectedSubject.value,
      text: textContent.value
    })
    
    const data = response.data || response
    parsedQuestions.value = data.questions || []
    
    if (parsedQuestions.value.length === 0) {
      message.error('未能解析出题目')
      return
    }
    
    message.success(response.message || `成功解析 ${parsedQuestions.value.length} 道题目`)
    showPreview.value = true
  } catch (error) {
    message.error(error.message || '解析失败')
  } finally {
    parsing.value = false
  }
}

// 确认导入
const handleConfirmImport = async (questions) => {
  importing.value = true
  try {
    const response = await importApi.confirmImport({
      user_id: userId.value,
      subject_id: selectedSubject.value,
      questions: questions
    })
    
    message.success(response.message || '导入成功')
    showPreview.value = false
    
    // 清空文本内容
    textContent.value = ''
    lastUploadedFile.value = null
  } catch (error) {
    message.error(error.message || '导入失败')
  } finally {
    importing.value = false
  }
}

// 取消预览
const handleCancelPreview = () => {
  parsedQuestions.value = []
}

onMounted(() => {
  loadSubjects()
})
</script>
