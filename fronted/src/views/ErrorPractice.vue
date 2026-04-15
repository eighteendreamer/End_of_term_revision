<template>
  <div>
    <n-page-header title="错题试卷练习" subtitle="创建错题试卷，针对性练习">
      <template #extra>
        <n-space>
          <n-button @click="$router.push('/errors')">
            返回错题集
          </n-button>
          <n-button type="primary" @click="showCreateDialog = true">
            创建新试卷
          </n-button>
        </n-space>
      </template>
    </n-page-header>

    <!-- 试卷列表 -->
    <div style="margin-top: 24px;">
      <n-spin :show="loading">
        <n-empty v-if="papers.length === 0" description="暂无错题试卷，点击右上角创建新试卷" />
        
        <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 16px;">
          <ExamPaperCard
            v-for="paper in papers"
            :key="paper.id"
            :paper="paper"
            @click="goToPaper(paper.id)"
          />
        </div>
      </n-spin>
    </div>

    <!-- 创建试卷对话框 -->
    <CreatePaperDialog
      v-model:show="showCreateDialog"
      paper-type="error"
      @created="handlePaperCreated"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { examPaperApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import ExamPaperCard from '@/components/ExamPaperCard.vue'
import CreatePaperDialog from '@/components/CreatePaperDialog.vue'

const message = useMessage()
const router = useRouter()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const loading = ref(false)
const papers = ref([])
const showCreateDialog = ref(false)

const loadPapers = async () => {
  loading.value = true
  try {
    const response = await examPaperApi.list(userId.value, 'error')
    const data = response.data || response
    papers.value = data.papers || []
  } catch (error) {
    message.error(error.message || '加载试卷列表失败')
  } finally {
    loading.value = false
  }
}

const goToPaper = (paperId) => {
  router.push(`/exam-paper/${paperId}`)
}

const handlePaperCreated = (paper) => {
  message.success('错题试卷创建成功')
  loadPapers()
  // 直接跳转到试卷页面
  goToPaper(paper.paper_id || paper.id)
}

onMounted(() => {
  loadPapers()
})
</script>
