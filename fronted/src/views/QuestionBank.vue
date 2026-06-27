<template>
  <div>
    <n-page-header title="题库管理" subtitle="查看和管理所有题目">
    </n-page-header>

    <n-space vertical size="large" style="margin-top: 24px;">
      <!-- 筛选区域 -->
      <n-card>
        <n-space class="qb-filters">
          <n-select
            v-model:value="filterSemesterId"
            :options="[{label:'全部学期',value:null},...semesterOptions]"
            placeholder="全部学期"
            style="width:150px"
            clearable
            @update:value="() => { filterSubjectId = null }"
          />
          <n-select
            v-model:value="filterSubjectId"
            :options="subjectOptions"
            placeholder="选择科目"
            class="qb-filter-item"
            style="width: 200px"
            clearable
            @update:value="handleFilterChange"
          />
          <n-select
            v-model:value="filterType"
            :options="typeOptions"
            placeholder="题目类型"
            class="qb-filter-item"
            style="width: 150px"
            clearable
            @update:value="handleFilterChange"
          />
          <n-input
            v-model:value="searchKeyword"
            placeholder="搜索题目内容"
            class="qb-filter-item"
            style="width: 300px"
            clearable
            @keyup.enter="loadQuestions"
          >
            <template #prefix>
              <n-icon><search-outline /></n-icon>
            </template>
          </n-input>
          <n-button type="primary" @click="loadQuestions">
            <template #icon>
              <n-icon><search-outline /></n-icon>
            </template>
            搜索
          </n-button>
          <n-button @click="handleReset">
            <template #icon>
              <n-icon><refresh-outline /></n-icon>
            </template>
            重置
          </n-button>
        </n-space>
      </n-card>

      <!-- 题目统计 -->
      <n-card>
        <n-space>
          <n-statistic label="总题数" :value="totalCount" />
          <n-statistic label="单选题" :value="typeCount.single || 0" />
          <n-statistic label="多选题" :value="typeCount.multiple || 0" />
          <n-statistic label="判断题" :value="typeCount.judge || 0" />
          <n-statistic label="填空题" :value="typeCount.fill || 0" />
          <n-statistic label="大型题" :value="typeCount.major || 0" />
        </n-space>
      </n-card>

      <!-- 题目列表 -->
      <n-card title="题目列表">
        <n-spin :show="loading">
          <n-empty
            v-if="questions.length === 0"
            description="暂无题目数据"
            style="margin: 40px 0;"
          />          
          <n-list v-else bordered>
            <n-list-item v-for="(question, index) in questions" :key="question.id">
              <template #prefix>
                <n-tag :type="getTypeTagType(question.type)" size="small">
                  {{ getTypeLabel(question.type) }}
                </n-tag>
              </template>
              
              <n-thing>
                <template #header>
                  <div style="display: flex; align-items: center; gap: 8px; width: 100%;">
                    <span style="font-weight: 500; flex-shrink: 0;">{{ (currentPage - 1) * pageSize + index + 1 }}. </span>
                    <div style="flex: 1; min-width: 0; overflow: hidden;">
                      <template v-if="question.type === 'major'">
                        <!-- 大型题只显示文本内容，不显示表格 -->
                        <div style="width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                          <TableRenderer :content="truncateQuestion(question.question)" />  
                        </div>
                      </template>
                      <template v-else>
                        <div style="width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                          <TableRenderer :content="truncateQuestion(question.question)" />  
                        </div>
                      </template>
                    </div>
                  </div>
                </template>
                
                <template #header-extra>
                  <n-space style="flex-shrink: 0; white-space: nowrap;">
                    <n-button text @click="handleView(question)">
                      <template #icon>
                        <n-icon><eye-outline /></n-icon>
                      </template>
                      查看
                    </n-button>
                    <n-button v-if="question.can_edit" text type="error" @click="handleDelete(question)">
                      <template #icon>
                        <n-icon><trash-outline /></n-icon>
                      </template>
                      删除
                    </n-button>
                  </n-space>
                </template>
                
                <!-- 移除描述部分，只显示题目类型、题目名称、查看和删除按钮 -->
              </n-thing>
            </n-list-item>
          </n-list>
          
          <!-- 分页 -->
          <div v-if="questions.length > 0" style="margin-top: 16px; display: flex; justify-content: flex-end;">
            <n-pagination
              v-model:page="currentPage"
              :page-count="pageCount"
              :page-size="pageSize"
              show-size-picker
              :page-sizes="[10, 20, 50, 100]"
              @update:page="handlePageChange"
              @update:page-size="handlePageSizeChange"
            />          
          </div>
        </n-spin>
      </n-card>
    </n-space>

    <!-- 查看题目详情对话框 -->
    <n-modal v-model:show="showDetailModal" preset="dialog" title="题目详情" style="width: 700px;">
      <div v-if="currentQuestion">
        <n-space vertical size="large">
          <n-descriptions label-placement="left" :column="1" bordered>
            <n-descriptions-item label="题目类型">
              <n-tag :type="getTypeTagType(currentQuestion.type)">
                {{ getTypeLabel(currentQuestion.type) }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="所属科目">
              {{ getSubjectName(currentQuestion.subject_id) }}
            </n-descriptions-item>
            <n-descriptions-item label="题目内容">
              <TableRenderer :content="currentQuestion.question" />  
            </n-descriptions-item>
            <n-descriptions-item label="选项" v-if="currentQuestion.options && currentQuestion.options.length > 0">
              <n-space vertical size="small">
                <div v-for="(option, idx) in currentQuestion.options" :key="idx">
                  <FormulaRenderer :content="option" />  
                </div>
              </n-space>
            </n-descriptions-item>
            <n-descriptions-item label="正确答案">
              <n-text type="success" strong>
                <FormulaRenderer :content="currentQuestion.answer" />  
              </n-text>
            </n-descriptions-item>
            <n-descriptions-item label="答案解析">
              <FormulaRenderer :content="currentQuestion.analysis" />  
            </n-descriptions-item>
            <n-descriptions-item label="创建时间">
              {{ currentQuestion.created_at }}
            </n-descriptions-item>
          </n-descriptions>
        </n-space>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { questionApi, subjectApi, semesterApi } from '@/api'
import {
  SearchOutline,
  RefreshOutline,
  EyeOutline,
  TrashOutline
} from '@vicons/ionicons5'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import FormulaRenderer from '@/components/FormulaRenderer.vue'
import TableRenderer from '@/components/TableRenderer.vue'

const message = useMessage()
const dialog = useDialog()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)
const loading = ref(false)
const questions = ref([])
const subjects = ref([])
const semesters = ref([])
const filterSemesterId = ref(null)
const filterSubjectId = ref(null)
const filterType = ref(null)
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const showDetailModal = ref(false)
const currentQuestion = ref(null)

// 题型选项
const typeOptions = [
  { label: '单选题', value: 'single' },
  { label: '多选题', value: 'multiple' },
  { label: '判断题', value: 'judge' },
  { label: '填空题', value: 'fill' },
  { label: '大型题', value: 'major' }
]

// 学期选项
const semesterOptions = computed(() =>
  semesters.value.map(s => ({ label: s.is_current ? s.name + ' (当前)' : s.name, value: s.id }))
)

// 科目选项（按学期过滤）
const subjectOptions = computed(() => {
  const filtered = filterSemesterId.value
    ? subjects.value.filter(s => s.semester_id === filterSemesterId.value)
    : subjects.value
  return filtered.map(s => ({
    label: s.name,
    value: s.id
  }))
})

// 统计数据（从后端获取）
const totalCount = ref(0)
const typeCount = ref({
  single: 0,
  multiple: 0,
  judge: 0,
  fill: 0,
  major: 0
})

// 分页（后端分页）
// filteredTotal：有题型筛选时用对应类型的题数，否则用总题数
const filteredTotal = computed(() => {
  if (!filterType.value) return totalCount.value
  const map = {
    single:   typeCount.value.single   || 0,
    multiple: typeCount.value.multiple || 0,
    judge:    typeCount.value.judge    || 0,
    fill:     typeCount.value.fill     || 0,
    major:    typeCount.value.major    || 0,
  }
  return map[filterType.value] ?? 0
})
const pageCount = computed(() => Math.ceil(filteredTotal.value / pageSize.value) || 1)

// 获取题型标签类型
const getTypeTagType = (type) => {
  const map = {
    single: 'info',
    multiple: 'success',
    judge: 'warning',
    fill: 'error',
    major: 'primary'
  }
  return map[type] || 'default'
}

// 获取题型标签文本
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

// 截断题目文本（最多110个字符）
const truncateQuestion = (text) => {
  if (!text) return ''
  
  // 移除换行符和多余空格
  let cleanText = text.replace(/\r?\n/g, ' ').replace(/\s+/g, ' ').trim()
  
  // 如果文本长度小于等于110，直接返回
  if (cleanText.length <= 110) {
    return cleanText
  }
  
  // 截取前110个字符
  let truncated = cleanText.substring(0, 110)
  
  // 检查是否在 $ 符号内部截断（KaTeX 公式）
  const dollarCount = (truncated.match(/\$/g) || []).length
  
  // 如果 $ 符号数量为奇数，说明在公式内部截断，需要找到最后一个 $ 之前的位置
  if (dollarCount % 2 !== 0) {
    const lastDollarIndex = truncated.lastIndexOf('$')
    // 如果最后一个 $ 在前14个字符内，则在 $ 之前截断
    if (lastDollarIndex >= 0 && (110 - lastDollarIndex) <= 14) {
      truncated = truncated.substring(0, lastDollarIndex)
    }
  }
  
  return truncated + '...'
}

// 获取科目名称
const getSubjectName = (subjectId) => {
  const subject = subjects.value.find(s => s.id === subjectId)
  return subject ? subject.name : '未知科目'
}

// 加载科目列表
const loadSubjects = async () => {
  try {
    subjects.value = await subjectApi.list(userId.value)
  } catch (error) {
    message.error('加载科目列表失败')
  }
}

const loadSemesters = async () => {
  if (!userId.value) return
  try {
    const res = await semesterApi.list(userId.value)
    semesters.value = res?.data || []
  } catch (_) {}
}

// 加载题目统计
const loadStatistics = async () => {
  try {
    if (filterSubjectId.value) {
      // 加载指定科目的统计
      const stats = await questionApi.getStatistics(filterSubjectId.value, userId.value)
      totalCount.value = stats.total
      typeCount.value = {
        single: stats.single || 0,
        multiple: stats.multiple || 0,
        judge: stats.judge || 0,
        fill: stats.fill || 0,
        major: stats.major || 0
      }
    } else {
      // 加载所有题目的统计
      const stats = await questionApi.getAllStatistics(userId.value)
      totalCount.value = stats.total
      typeCount.value = {
        single: stats.single || 0,
        multiple: stats.multiple || 0,
        judge: stats.judge || 0,
        fill: stats.fill || 0,
        major: stats.major || 0
      }
    }
  } catch (error) {
    console.error('加载统计数据失败', error)
  }
}

// 筛选条件变化时调用：先重置到第 1 页再加载
const handleFilterChange = () => {
  currentPage.value = 1
  loadQuestions()
}

// 加载题目列表（使用后端分页）
const loadQuestions = async () => {
  loading.value = true
  try {
    // 先加载统计数据
    await loadStatistics()
    
    const params = {
      user_id: userId.value,
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    // subject_id 可选，不传则查询所有题目
    if (filterSubjectId.value) {
      params.subject_id = filterSubjectId.value
    }
    
    if (filterType.value) {
      params.question_type = filterType.value
    }
    
    // 使用后端分页查询
    questions.value = await questionApi.list(params)
    
    // 客户端搜索过滤（如果有搜索关键词）
    if (searchKeyword.value) {
      const keyword = searchKeyword.value.toLowerCase()
      questions.value = questions.value.filter(q =>
        q.question.toLowerCase().includes(keyword) ||
        q.answer.toLowerCase().includes(keyword) ||
        q.analysis.toLowerCase().includes(keyword)
      )
    }
  } catch (error) {
    message.error(error.message || '加载题目失败')
  } finally {
    loading.value = false
  }
}

// 重置筛选
const handleReset = () => {
  filterSubjectId.value = null
  filterType.value = null
  searchKeyword.value = ''
  currentPage.value = 1
  loadQuestions()
}

// 查看题目详情
const handleView = (question) => {
  currentQuestion.value = question
  showDetailModal.value = true
}

// 删除题目
const handleDelete = (question) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除题目「${question.question.substring(0, 30)}...」吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await questionApi.delete(question.id, { params: { user_id: userId.value } })
        message.success('删除成功')
        loadQuestions()
      } catch (error) {
        message.error(error.message || '删除失败')
      }
    }
  })
}

// 分页处理
const handlePageChange = (page) => {
  currentPage.value = page
  loadQuestions()  // 重新加载题目
}

const handlePageSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  loadQuestions()  // 重新加载题目
}

onMounted(() => {
  loadSemesters()
  loadSubjects().then(() => {
    loadQuestions()
  })
})
</script>

<style scoped>
:deep(.n-list-item) {
  padding: 16px;
}

:deep(.n-thing-header) {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 16px;
}

:deep(.n-thing-header__main) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

:deep(.n-thing-header__extra) {
  flex-shrink: 0;
}

/* 确保 TableRenderer 内容单行显示 */
:deep(.n-thing-header__main) .table-renderer,
:deep(.n-thing-header__main) p,
:deep(.n-thing-header__main) div {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline;
}

/* 窄屏：筛选控件占满宽度、自动换行 */
@media (max-width: 768px) {
  .qb-filters {
    width: 100%;
  }
  .qb-filters .qb-filter-item {
    width: 100% !important;
    flex: 1 1 100%;
  }
}
</style>
