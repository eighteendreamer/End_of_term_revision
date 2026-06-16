<template>
  <div>
    <n-upload
      :action="null"
      :max="max"
      :accept="'image/*'"
      :file-list="fileList"
      :show-upload-button="!disabled && fileList.length < max"
      :show-file-list="true"
      list-type="image-card"
      :disabled="disabled"
      @change="handleChange"
      @remove="handleRemove"
      :custom-request="handleCustomRequest"
    >
      <n-button v-if="!disabled && fileList.length < max" secondary>上传图片</n-button>
    </n-upload>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  modelValue: Array,
  max: {
    type: Number,
    default: 3
  },
  disabled: {
    type: Boolean,
    default: false
  }
})
const emit = defineEmits(['update:modelValue'])

const fileList = ref((props.modelValue || []).map((url, idx) => ({
  id: idx + '',
  name: '图片' + (idx + 1),
  status: 'finished',
  url
})))

watch(() => props.modelValue, (val) => {
  fileList.value = (val || []).map((url, idx) => ({
    id: idx + '',
    name: '图片' + (idx + 1),
    status: 'finished',
    url
  }))
})

const handleChange = ({ fileList: newList }) => {
  if (props.disabled) return
  emit('update:modelValue', newList.filter(f => f.status === 'finished').map(f => f.url))
}

const handleRemove = (options) => {
  if (props.disabled) return
  emit('update:modelValue', fileList.value.filter(f => f.id !== options.file.id).map(f => f.url))
}

const handleCustomRequest = async ({ file, onFinish }) => {
  if (props.disabled) return
  // 直接转base64
  const reader = new FileReader()
  reader.onload = (e) => {
    onFinish({ url: e.target.result })
  }
  reader.readAsDataURL(file.file)
}
</script>
