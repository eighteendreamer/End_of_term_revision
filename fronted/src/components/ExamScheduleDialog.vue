<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    title="考试日程管理"
    :style="{ width: isMobile ? '94vw' : '600px' }"
    :mask-closable="true"
  >
    <!-- 顶部：学期筛选 + 添加按钮 -->
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 8px; flex-wrap: wrap;">
      <n-select
        v-model:value="filterSemesterId"
        :options="semesterFilterOptions"
        placeholder="全部学期"
        style="min-width: 150px; flex: 1;"
        clearable
      />
      <n-button type="primary" size="small" @click="openForm()">
        <template #icon><n-icon><add-outline /></n-icon></template>
        添加考试
      </n-button>
    </div>

    <!-- 列表 -->
    <n-spin :show="loading">
      <n-empty v-if="!loading && filteredExams.length === 0" description="暂无考试日程" />
      <n-list v-else bordered>
        <n-list-item v-for="exam in filteredExams" :key="exam.id">
          <div class="exam-item">
            <div class="exam-main">
              <div class="exam-subject">
                {{ exam.subject_name }}
                <n-tag v-if="!exam.is_owner" size="tiny" type="success" style="margin-left: 6px;">
                  共享 · {{ exam.owner_username }}
                </n-tag>
              </div>
              <div class="exam-meta">
                <n-icon :size="13"><time-outline /></n-icon>
                {{ formatTime(exam.exam_time) }}
                <template v-if="exam.exam_location">
                  &nbsp;·&nbsp;
                  <n-icon :size="13"><location-outline /></n-icon>
                  {{ exam.exam_location }}
                </template>
              </div>
              <div v-if="exam.note" class="exam-note">{{ exam.note }}</div>
              <n-tag v-if="isPast(exam.exam_time)" size="tiny" type="default" style="margin-top: 4px;">已过期</n-tag>
              <n-tag v-else size="tiny" type="warning" style="margin-top: 4px;">{{ countdownText(exam.exam_time) }}</n-tag>
            </div>
            <!-- 只有本人创建的考试才显示编辑/删除 -->
            <n-space v-if="exam.is_owner !== false">
              <n-button size="small" quaternary @click="openForm(exam)">
                <template #icon><n-icon><create-outline /></n-icon></template>
              </n-button>
              <n-popconfirm @positive-click="deleteExam(exam.id)">
                <template #trigger>
                  <n-button size="small" quaternary type="error">
                    <template #icon><n-icon><trash-outline /></n-icon></template>
                  </n-button>
                </template>
                确定删除这门考试？
              </n-popconfirm>
            </n-space>
          </div>
        </n-list-item>
      </n-list>
    </n-spin>
  </n-modal>

  <!-- 添加 / 编辑表单弹窗 -->
  <n-modal
    v-model:show="showForm"
    preset="card"
    :title="editTarget ? '编辑考试' : '添加考试'"
    :style="{ width: isMobile ? '94vw' : '460px' }"
    :mask-closable="false"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
      <n-form-item label="科目名称" path="subject_id">
        <n-select
          v-model:value="form.subject_id"
          :options="subjectOptions"
          placeholder="选择科目"
          filterable
          clearable
          :loading="loadingSubjects"
          @update:value="handleSubjectChange"
        />
      </n-form-item>
      <n-form-item label="所属学期">
        <n-select
          v-model:value="form.semester_id"
          :options="semesterOptions"
          placeholder="选择学期（可选）"
          clearable
        />
      </n-form-item>
      <n-form-item label="考试时间" path="exam_time">
        <n-date-picker
          v-model:value="form.exam_time_ts"
          type="datetime"
          placeholder="选择考试时间"
          style="width: 100%;"
          clearable
        />
      </n-form-item>
      <n-form-item label="考试地点" path="exam_location">
        <n-input v-model:value="form.exam_location" placeholder="如：1号教学楼 204" clearable />
      </n-form-item>
      <n-form-item label="备注" path="note">
        <n-input
          v-model:value="form.note"
          type="textarea"
          placeholder="选填（如：带好准考证、计算器）"
          :autosize="{ minRows: 2, maxRows: 4 }"
          clearable
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showForm = false">取消</n-button>
        <n-button type="primary" :loading="saving" @click="submitForm">保存</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { AddOutline, TimeOutline, LocationOutline, CreateOutline, TrashOutline } from '@vicons/ionicons5'
import { examScheduleApi, subjectApi, semesterApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { useBreakpoint } from '@/composables/useBreakpoint'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['update:show', 'changed'])

const message = useMessage()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)
const { isMobile } = useBreakpoint()

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v)
})

// ─── 列表 ────────────────────────────────────────────
const loading = ref(false)
const loadingSubjects = ref(false)
const exams = ref([])
const mySubjects = ref([])
const mySemesters = ref([])
const filterSemesterId = ref(null)

const semesterFilterOptions = computed(() => [
  { label: '全部学期', value: null },
  { label: '无学期', value: 0 },
  ...mySemesters.value.map(s => ({ label: s.name + (s.is_current ? ' (当前)' : ''), value: s.id }))
])

const semesterOptions = computed(() =>
  mySemesters.value.map(s => ({ label: s.name + (s.is_current ? ' (当前)' : ''), value: s.id }))
)

const filteredExams = computed(() => {
  if (filterSemesterId.value === null) return exams.value
  if (filterSemesterId.value === 0) return exams.value.filter(e => !e.semester_id)
  return exams.value.filter(e => e.semester_id === filterSemesterId.value)
})

// n-select 选项：label 显示名称（共享的标注来源），value 为 subject_id
const subjectOptions = computed(() =>
  mySubjects.value.map(s => ({
    label: s.is_owner === false ? `${s.name}（来自 ${s.owner_username || '他人'}）` : s.name,
    value: s.id,
  }))
)

const loadExams = async () => {
  if (!userId.value) return
  loading.value = true
  try {
    const res = await examScheduleApi.list(userId.value)
    exams.value = res?.data || []
  } catch (e) {
    message.error('加载考试日程失败')
  } finally {
    loading.value = false
  }
}

const loadSubjects = async () => {
  if (!userId.value) return
  loadingSubjects.value = true
  try {
    // subjectApi.list 返回 List[SubjectResponse]（含共享科目）
    const res = await subjectApi.list(userId.value)
    // 兼容直接返回数组 或 { data: [...] } 两种情况
    const raw = Array.isArray(res) ? res : (Array.isArray(res?.data) ? res.data : [])
    mySubjects.value = raw
  } catch (_) {
    mySubjects.value = []
  } finally {
    loadingSubjects.value = false
  }
}

watch(visible, (v) => {
  if (v) {
    loadExams()
    loadSubjects()
    loadSemesters()
  }
})

const loadSemesters = async () => {
  if (!userId.value) return
  try {
    const res = await semesterApi.list(userId.value)
    mySemesters.value = res?.data || []
    // 默认选中当前学期
    const cur = mySemesters.value.find(s => s.is_current)
    if (cur && filterSemesterId.value === null) filterSemesterId.value = cur.id
  } catch (_) {}
}

// ─── 表单 ────────────────────────────────────────────
const showForm = ref(false)
const saving = ref(false)
const editTarget = ref(null)
const formRef = ref(null)

const defaultForm = () => ({
  subject_id: null,
  subject_name: '',
  semester_id: null,
  exam_time_ts: null,
  exam_location: '',
  note: '',
})
const form = ref(defaultForm())

const rules = {
  subject_id: { required: true, type: 'number', message: '请选择科目', trigger: 'change' },
  exam_time_ts: { required: true, type: 'number', message: '请选择考试时间', trigger: 'change' },
}

// 选中科目后同步 subject_name
const handleSubjectChange = (val) => {
  const found = mySubjects.value.find(s => s.id === val)
  form.value.subject_name = found ? found.name : ''
}

const openForm = (exam = null) => {
  editTarget.value = exam
  if (exam) {
    form.value = {
      subject_id: exam.subject_id || null,
      subject_name: exam.subject_name,
      semester_id: exam.semester_id || null,
      exam_time_ts: new Date(exam.exam_time).getTime(),
      exam_location: exam.exam_location || '',
      note: exam.note || '',
    }
  } else {
    // 默认带入当前学期
    const defaultSem = mySemesters.value.find(s => s.is_current)
    form.value = { ...defaultForm(), semester_id: defaultSem?.id || null }
  }
  showForm.value = true
}

const submitForm = async () => {
  try {
    await formRef.value?.validate()
  } catch (_) {
    return
  }

  saving.value = true
  try {
    const examTimeISO = new Date(form.value.exam_time_ts).toISOString().replace('Z', '')
    const payload = {
      user_id: userId.value,
      subject_name: form.value.subject_name,
      subject_id: form.value.subject_id || null,
      semester_id: form.value.semester_id || null,
      exam_time: examTimeISO,
      exam_location: form.value.exam_location || null,
      note: form.value.note || null,
    }
    if (editTarget.value) {
      await examScheduleApi.update(editTarget.value.id, userId.value, payload)
      message.success('修改成功')
    } else {
      await examScheduleApi.create(payload)
      message.success('添加成功')
    }
    showForm.value = false
    await loadExams()
    emit('changed')
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const deleteExam = async (id) => {
  try {
    await examScheduleApi.delete(id, userId.value)
    message.success('已删除')
    await loadExams()
    emit('changed')
  } catch (e) {
    message.error('删除失败')
  }
}

// ─── 工具函数 ─────────────────────────────────────────
const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

const isPast = (iso) => new Date(iso) <= new Date()

const countdownText = (iso) => {
  const diff = new Date(iso) - new Date()
  if (diff <= 0) return '已过期'
  const d = Math.floor(diff / 86400000)
  const h = Math.floor((diff % 86400000) / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  if (d > 0) return `还有 ${d} 天 ${h} 时`
  if (h > 0) return `还有 ${h} 时 ${m} 分`
  return `还有 ${m} 分钟`
}
</script>

<style scoped>
.exam-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 8px;
}
.exam-main {
  flex: 1;
  min-width: 0;
}
.exam-subject {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}
.exam-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #6b7280;
}
.exam-note {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 3px;
}
</style>
