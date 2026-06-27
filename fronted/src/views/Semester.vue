<template>
  <div>
    <n-page-header title="学期管理" subtitle="管理你的学期，科目和考试均可按学期分类">
      <template #extra>
        <n-button type="primary" @click="openForm()">
          <template #icon><n-icon><add-outline /></n-icon></template>
          添加学期
        </n-button>
      </template>
    </n-page-header>

    <div style="margin-top: 24px;">
      <n-spin :show="loading">
        <n-empty v-if="!loading && semesters.length === 0" description="暂无学期，点击右上角添加">
          <template #icon><n-icon size="64" color="#d0d0d0"><school-outline /></n-icon></template>
        </n-empty>

        <n-grid v-else cols="1 s:2 m:3" responsive="screen" :x-gap="16" :y-gap="16">
          <n-gi v-for="sem in semesters" :key="sem.id">
            <n-card hoverable :class="{ 'card-current': sem.is_current }">
              <template #header>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span style="font-weight: 600; font-size: 15px;">{{ sem.name }}</span>
                  <n-tag v-if="sem.is_current" type="success" size="small" round>当前学期</n-tag>
                </div>
              </template>
              <template #header-extra>
                <n-dropdown
                  trigger="click"
                  :options="cardMenuOptions(sem)"
                  @select="(key) => handleCardMenu(key, sem)"
                >
                  <n-button quaternary circle size="small">
                    <template #icon><n-icon><ellipsis-horizontal-outline /></n-icon></template>
                  </n-button>
                </n-dropdown>
              </template>

              <n-space vertical size="small">
                <div class="sem-meta">
                  <n-icon :size="13"><calendar-outline /></n-icon>
                  <span>{{ formatDate(sem.start_date) }} — {{ formatDate(sem.end_date) }}</span>
                </div>
                <div class="sem-meta" style="color: #9ca3af;">
                  <n-icon :size="13"><time-outline /></n-icon>
                  <span>{{ statusText(sem) }}</span>
                </div>
              </n-space>
            </n-card>
          </n-gi>
        </n-grid>
      </n-spin>
    </div>

    <!-- 添加 / 编辑弹窗 -->
    <n-modal
      v-model:show="showForm"
      preset="card"
      :title="editTarget ? '编辑学期' : '添加学期'"
      :style="{ width: isMobile ? '94vw' : '460px' }"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
        <n-form-item label="学期名称" path="name">
          <n-input
            v-model:value="form.name"
            placeholder="如：2025-2026 第一学期"
            clearable
            maxlength="100"
            show-count
          />
        </n-form-item>
        <n-form-item label="开始日期" path="start_date">
          <n-date-picker
            v-model:value="form.start_date_ts"
            type="date"
            placeholder="选择开始日期"
            style="width: 100%"
            clearable
          />
        </n-form-item>
        <n-form-item label="结束日期" path="end_date">
          <n-date-picker
            v-model:value="form.end_date_ts"
            type="date"
            placeholder="选择结束日期"
            style="width: 100%"
            clearable
          />
        </n-form-item>
        <n-form-item label="当前学期" path="is_current">
          <n-switch v-model:value="form.is_current">
            <template #checked>是</template>
            <template #unchecked>否</template>
          </n-switch>
          <n-text depth="3" style="margin-left: 12px; font-size: 12px;">设为当前后，倒计时默认显示此学期的考试</n-text>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="submitForm">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import {
  AddOutline, EllipsisHorizontalOutline, CalendarOutline,
  TimeOutline, SchoolOutline
} from '@vicons/ionicons5'
import { semesterApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { useBreakpoint } from '@/composables/useBreakpoint'

const message = useMessage()
const dialog = useDialog()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)
const { isMobile } = useBreakpoint()

const loading = ref(false)
const semesters = ref([])

const loadSemesters = async () => {
  if (!userId.value) return
  loading.value = true
  try {
    const res = await semesterApi.list(userId.value)
    semesters.value = res?.data || []
  } catch (e) {
    message.error('加载学期失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadSemesters)

// ─── 卡片菜单 ─────────────────────────────────────────
const cardMenuOptions = (sem) => [
  { label: '编辑', key: 'edit' },
  sem.is_current
    ? { label: '取消当前', key: 'unset-current' }
    : { label: '设为当前', key: 'set-current' },
  { type: 'divider', key: 'd1' },
  { label: '删除', key: 'delete' },
]

const handleCardMenu = async (key, sem) => {
  if (key === 'edit') {
    openForm(sem)
  } else if (key === 'set-current') {
    try {
      await semesterApi.setCurrent(sem.id, userId.value)
      message.success(`「${sem.name}」已设为当前学期`)
      loadSemesters()
    } catch (e) {
      message.error('操作失败')
    }
  } else if (key === 'unset-current') {
    try {
      await semesterApi.update(sem.id, userId.value, { is_current: false })
      message.success('已取消当前学期标记')
      loadSemesters()
    } catch (e) {
      message.error('操作失败')
    }
  } else if (key === 'delete') {
    dialog.warning({
      title: '确认删除',
      content: `删除学期「${sem.name}」后，已关联的科目和考试的学期字段会被清空（科目和考试本身不会删除）。确定继续？`,
      positiveText: '删除',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await semesterApi.delete(sem.id, userId.value)
          message.success('已删除')
          loadSemesters()
        } catch (e) {
          message.error('删除失败')
        }
      }
    })
  }
}

// ─── 表单 ────────────────────────────────────────────
const showForm = ref(false)
const saving = ref(false)
const editTarget = ref(null)
const formRef = ref(null)

const defaultForm = () => ({
  name: '',
  start_date_ts: null,
  end_date_ts: null,
  is_current: false,
})
const form = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入学期名称', trigger: 'blur' },
}

const openForm = (sem = null) => {
  editTarget.value = sem
  if (sem) {
    form.value = {
      name: sem.name,
      start_date_ts: sem.start_date ? new Date(sem.start_date).getTime() : null,
      end_date_ts: sem.end_date ? new Date(sem.end_date).getTime() : null,
      is_current: sem.is_current,
    }
  } else {
    form.value = defaultForm()
  }
  showForm.value = true
}

const submitForm = async () => {
  try { await formRef.value?.validate() } catch (_) { return }
  saving.value = true
  try {
    const payload = {
      user_id: userId.value,
      name: form.value.name.trim(),
      start_date: form.value.start_date_ts
        ? new Date(form.value.start_date_ts).toISOString().split('T')[0]
        : null,
      end_date: form.value.end_date_ts
        ? new Date(form.value.end_date_ts).toISOString().split('T')[0]
        : null,
      is_current: form.value.is_current,
    }
    if (editTarget.value) {
      await semesterApi.update(editTarget.value.id, userId.value, payload)
      message.success('修改成功')
    } else {
      await semesterApi.create(payload)
      message.success('添加成功')
    }
    showForm.value = false
    loadSemesters()
  } catch (e) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ─── 工具 ─────────────────────────────────────────────
const formatDate = (iso) => {
  if (!iso) return '未设置'
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

const statusText = (sem) => {
  if (!sem.start_date && !sem.end_date) return '未设置时间范围'
  const now = Date.now()
  const start = sem.start_date ? new Date(sem.start_date).getTime() : null
  const end = sem.end_date ? new Date(sem.end_date).getTime() : null
  if (end && now > end) return '已结束'
  if (start && now < start) return '未开始'
  return '进行中'
}
</script>

<style scoped>
.sem-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #6b7280;
}
.card-current {
  border: 1.5px solid #18a058 !important;
}
</style>
