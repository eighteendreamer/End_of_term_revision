<template>
  <div>
    <n-page-header title="资料库" subtitle="管理学习资料，生成练习题目">
      <template #extra>
        <n-space>
          <n-select
            v-model:value="filterSemesterId"
            :options="[{label:'全部学期',value:null},...semesterOptions]"
            placeholder="全部学期"
            style="width:150px"
            clearable
            @update:value="() => { selectedSubject = null }"
          />
          <n-select
            v-model:value="selectedSubject"
            :options="subjectOptions"
            placeholder="选择科目"
            style="width: 200px;"
            clearable
            @update:value="loadMaterials"
          />
          <n-input
            v-model:value="searchKeyword"
            placeholder="搜索资料"
            clearable
            @update:value="handleSearch"
            style="width: 200px;"
          >
            <template #prefix>
              <n-icon :component="SearchOutline" />
            </template>
          </n-input>
          <n-button type="primary" @click="showUploadDialog = true">
            上传资料
          </n-button>
        </n-space>
      </template>
    </n-page-header>

    <!-- 筛选栏 -->
    <n-card style="margin-top: 16px;">
      <n-space>
        <n-tag
          :type="materialTypeFilter === null ? 'primary' : 'default'"
          :bordered="false"
          checkable
          :checked="materialTypeFilter === null"
          @click="materialTypeFilter = null; loadMaterials()"
        >
          全部
        </n-tag>
        <n-tag
          v-for="type in materialTypes"
          :key="type.value"
          :type="materialTypeFilter === type.value ? 'primary' : 'default'"
          :bordered="false"
          checkable
          :checked="materialTypeFilter === type.value"
          @click="materialTypeFilter = type.value; loadMaterials()"
        >
          {{ type.label }}
        </n-tag>
      </n-space>
    </n-card>

    <!-- 资料列表 -->
    <div style="margin-top: 24px;">
      <n-spin :show="loading">
        <n-empty v-if="materials.length === 0" description="暂无资料，点击右上角上传资料" />
        
        <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); gap: 16px;">
          <MaterialCard
            v-for="material in materials"
            :key="material.id"
            :material="material"
            @view="handleViewMaterial"
            @edit="handleEditMaterial"
            @delete="handleDeleteMaterial"
          />
        </div>
      </n-spin>
    </div>

    <!-- 上传对话框 -->
    <MaterialUploadDialog
      v-model:show="showUploadDialog"
      @uploaded="handleMaterialUploaded"
    />

    <!-- 详情对话框 -->
    <MaterialDetailDialog
      v-model:show="showDetailDialog"
      :material-id="selectedMaterialId"
      @updated="loadMaterials"
    />

    <!-- 题目生成对话框 -->
    <QuestionGenerationDialog
      v-model:show="showGenerationDialog"
      :material-id="selectedMaterialId"
      @generated="handleQuestionsGenerated"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { SearchOutline } from '@vicons/ionicons5'
import { materialApi, subjectApi, semesterApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import MaterialCard from '@/components/MaterialCard.vue'
import MaterialUploadDialog from '@/components/MaterialUploadDialog.vue'
import MaterialDetailDialog from '@/components/MaterialDetailDialog.vue'
import QuestionGenerationDialog from '@/components/QuestionGenerationDialog.vue'

const message = useMessage()
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

const loading = ref(false)
const materials = ref([])
const subjects = ref([])
const semesters = ref([])
const filterSemesterId = ref(null)
const selectedSubject = ref(null)
const searchKeyword = ref('')
const materialTypeFilter = ref(null)
const showUploadDialog = ref(false)
const showDetailDialog = ref(false)
const showGenerationDialog = ref(false)
const selectedMaterialId = ref(null)

const materialTypes = [
  { label: '教材', value: 'textbook' },
  { label: '笔记', value: 'note' },
  { label: '习题', value: 'exercise' },
  { label: '其他', value: 'other' }
]

const semesterOptions = computed(() =>
  semesters.value.map(s => ({ label: s.is_current ? s.name + ' (当前)' : s.name, value: s.id }))
)

const subjectOptions = computed(() => {
  const filtered = filterSemesterId.value
    ? subjects.value.filter(s => s.semester_id === filterSemesterId.value)
    : subjects.value
  return filtered.map(s => ({
    label: s.name,
    value: s.id
  }))
})

let searchTimer = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    loadMaterials()
  }, 500)
}

const loadSubjects = async () => {
  try {
    subjects.value = await subjectApi.list(userId.value)
  } catch (error) {
    message.error(error.message || '加载科目列表失败')
  }
}

const loadSemesters = async () => {
  if (!userId.value) return
  try {
    const res = await semesterApi.list(userId.value)
    semesters.value = res?.data || []
  } catch (_) {}
}

const loadMaterials = async () => {
  loading.value = true
  try {
    const response = await materialApi.list(
      userId.value,
      selectedSubject.value,
      materialTypeFilter.value,
      null,
      searchKeyword.value || null
    )
    const data = response.data || response
    materials.value = data.materials || []
  } catch (error) {
    message.error(error.message || '加载资料列表失败')
  } finally {
    loading.value = false
  }
}

const handleViewMaterial = (materialId) => {
  selectedMaterialId.value = materialId
  showDetailDialog.value = true
}

const handleEditMaterial = (materialId) => {
  selectedMaterialId.value = materialId
  showDetailDialog.value = true
}

const handleDeleteMaterial = async (materialId) => {
  try {
    const response = await materialApi.delete(materialId, userId.value)
    message.success('删除成功')
    loadMaterials()
  } catch (error) {
    message.error(error.message || '删除失败')
  }
}

const handleMaterialUploaded = () => {
  message.success('上传成功')
  loadMaterials()
}

const handleQuestionsGenerated = (data) => {
  message.success('题目生成成功')
  loadMaterials()
  // 刷新详情对话框
  if (showDetailDialog.value) {
    showDetailDialog.value = false
    setTimeout(() => {
      showDetailDialog.value = true
    }, 100)
  }
}

onMounted(() => {
  loadSemesters()
  loadSubjects()
  loadMaterials()
})
</script>
