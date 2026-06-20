<template>
  <n-card
    :title="material.name"
    hoverable
    style="cursor: pointer;"
    @click="$emit('view', material.id)"
  >
    <template #header-extra>
      <n-dropdown :options="dropdownOptions" @select="handleSelect">
        <n-button text @click.stop>
          <n-icon size="20">
            <EllipsisVertical />
          </n-icon>
        </n-button>
      </n-dropdown>
    </template>

    <n-space vertical size="small">
      <!-- 文件信息 -->
      <n-space align="center">
        <n-icon size="24" :color="getFileTypeColor(material.file_type)">
          <component :is="getFileTypeIcon(material.file_type)" />
        </n-icon>
        <n-text depth="3">{{ formatFileSize(material.file_size) }}</n-text>
      </n-space>

      <!-- 科目和类型 -->
      <n-space>
        <n-tag size="small" type="info">{{ material.subject_name }}</n-tag>
        <n-tag size="small" :type="getMaterialTypeColor(material.material_type)">
          {{ getMaterialTypeLabel(material.material_type) }}
        </n-tag>
        <n-tag v-if="material.is_owner === false" size="small" type="success">
          <template #icon><n-icon><earth-outline /></n-icon></template>
          共享
        </n-tag>
      </n-space>

      <!-- 共享来源 -->
      <n-space v-if="material.is_owner === false && material.owner_username" align="center">
        <n-text depth="3" style="font-size: 12px;">来自：{{ material.owner_username }}</n-text>
      </n-space>

      <!-- 标签 -->
      <n-space v-if="material.tags && material.tags.length > 0">
        <n-tag
          v-for="tag in material.tags.slice(0, 3)"
          :key="tag"
          size="small"
          :bordered="false"
        >
          {{ tag }}
        </n-tag>
        <n-text v-if="material.tags.length > 3" depth="3" style="font-size: 12px;">
          +{{ material.tags.length - 3 }}
        </n-text>
      </n-space>

      <!-- 题目数量 -->
      <n-space align="center">
        <n-icon size="18">
          <DocumentTextOutline />
        </n-icon>
        <n-text>已生成 {{ material.question_count }} 道题目</n-text>
      </n-space>

      <!-- 状态 -->
      <n-space align="center">
        <n-tag
          size="small"
          :type="getStatusType(material.status)"
          :bordered="false"
        >
          {{ getStatusLabel(material.status) }}
        </n-tag>
        <n-text depth="3" style="font-size: 12px;">
          {{ formatDate(material.created_at) }}
        </n-text>
      </n-space>
    </n-space>
  </n-card>
</template>

<script setup>
import { h, computed } from 'vue'
import { useDialog } from 'naive-ui'
import {
  EllipsisVertical,
  DocumentTextOutline,
  DocumentOutline,
  ImageOutline,
  CodeOutline,
  EarthOutline
} from '@vicons/ionicons5'

const props = defineProps({
  material: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['view', 'edit', 'delete'])
const dialog = useDialog()

// 非本人资料（共享而来）只提供「查看详情」，隐藏编辑/删除
const dropdownOptions = computed(() => {
  const options = [{ label: '查看详情', key: 'view' }]
  if (props.material.is_owner !== false) {
    options.push({ label: '编辑', key: 'edit' })
    options.push({ label: '删除', key: 'delete' })
  }
  return options
})

const handleSelect = (key) => {
  if (key === 'delete') {
    dialog.warning({
      title: '确认删除',
      content: `确定要删除资料"${props.material.name}"吗？此操作不可恢复。`,
      positiveText: '删除',
      negativeText: '取消',
      onPositiveClick: () => {
        emit('delete', props.material.id)
      }
    })
  } else {
    emit(key, props.material.id)
  }
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

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}
</script>
