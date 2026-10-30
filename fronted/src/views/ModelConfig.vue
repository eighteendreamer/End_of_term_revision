<template>
  <div>
    <n-page-header title="AI 模型配置" subtitle="配置你的 AI 模型（支持任何 OpenAI 兼容 API）">
      <template #extra>
        <n-button type="primary" @click="openCreate">
          <template #icon>
            <n-icon><add-outline /></n-icon>
          </template>
          添加模型配置
        </n-button>
      </template>
    </n-page-header>

    <n-alert type="info" style="margin-top: 16px;" :bordered="false">
      换模型只需改模型名称、API 地址、API 密钥三项。图片导入与文档导入只会使用勾选了
      「支持图片输入」的模型；没勾的模型不会被用于这两类导入。
    </n-alert>

    <n-spin :show="loading" style="margin-top: 24px;">
      <n-empty
        v-if="models.length === 0"
        description="还没有配置 AI 模型，请先添加一个配置"
        style="margin-top: 60px;"
      />

      <div v-else style="display: flex; flex-wrap: wrap; gap: 20px; margin-top: 20px;">
        <n-card
          v-for="model in models"
          :key="model.id"
          hoverable
          :style="{ width: 'min(100%, 420px)', minHeight: '210px' }"
        >
          <template #header>
            <div style="display: flex; align-items: center; gap: 12px;">
              <n-avatar size="small">
                <n-icon><cube-outline /></n-icon>
              </n-avatar>
              <span style="flex: 1; font-weight: 600;">{{ model.display_name }}</span>
              <n-tag v-if="model.is_default" type="success" size="small">默认</n-tag>
            </div>
          </template>
          <template #header-extra>
            <n-space :size="8">
              <n-button v-if="!model.is_default" size="tiny" @click="makeDefault(model)">
                设为默认
              </n-button>
              <n-button text @click="editModel(model)">
                <n-icon :size="20"><create-outline /></n-icon>
              </n-button>
              <n-button text type="error" @click="deleteModel(model.id)">
                <n-icon :size="20"><trash-outline /></n-icon>
              </n-button>
            </n-space>
          </template>
          <n-space vertical :size="8">
            <div>
              <n-text depth="3" style="font-size: 13px;">模型: {{ model.model_name }}</n-text>
            </div>
            <div>
              <n-text depth="3" style="font-size: 13px;">API: {{ model.base_url }}</n-text>
            </div>
            <div>
              <n-text depth="3" style="font-size: 13px;">Key: {{ model.api_key_masked }}</n-text>
            </div>
            <n-space :size="6">
              <n-tag :type="model.supports_vision ? 'info' : 'default'" size="small">
                图片输入{{ model.supports_vision ? '·支持' : '·不支持' }}
              </n-tag>
              <n-tag :type="model.supports_json_mode ? 'info' : 'default'" size="small">
                JSON模式{{ model.supports_json_mode ? '·支持' : '·自动降级' }}
              </n-tag>
              <n-tag size="small">
                输出上限 {{ model.max_output_tokens }}{{
                  model.output_limit_source === 'provider' ? '（端点返回）' : '（手填，端点未报）'
                }}
              </n-tag>
            </n-space>
            <div>
              <n-text depth="3" style="font-size: 13px;">创建时间: {{ model.created_at }}</n-text>
            </div>
          </n-space>
        </n-card>
      </div>
    </n-spin>

    <!-- 添加/编辑对话框 -->
    <n-modal
      v-model:show="showModal"
      preset="dialog"
      :title="isEdit ? '编辑模型配置' : '添加模型配置'"
      style="width: 560px;"
    >
      <n-form ref="formRef" :model="formData" :rules="rules" label-width="110px">
        <n-form-item label="模型名称" path="model_name">
          <n-input v-model:value="formData.model_name" placeholder="接口里真实的模型名，如 qwen-vl-max" />
        </n-form-item>
        <n-form-item label="显示名称" path="display_name">
          <n-input v-model:value="formData.display_name" placeholder="留空则直接显示模型名称" />
        </n-form-item>
        <n-form-item label="API 地址" path="base_url">
          <n-input v-model:value="formData.base_url" placeholder="如 https://api.example.com/v1，支持内网与本机地址" />
        </n-form-item>
        <n-form-item label="API 密钥" path="api_key">
          <n-input
            v-model:value="formData.api_key"
            type="password"
            show-password-on="click"
            :placeholder="isEdit ? '留空表示不修改原密钥' : 'sk-xxxxxxxxxxxxxxxx'"
          />
        </n-form-item>
        <n-form-item label="支持图片输入">
          <n-switch v-model:value="formData.supports_vision" />
          <n-text depth="3" style="margin-left: 12px; font-size: 12px;">
            图片导入与文档导入只用勾选了这里的模型
          </n-text>
        </n-form-item>
        <n-form-item label="支持 JSON 模式">
          <n-switch v-model:value="formData.supports_json_mode" />
          <n-text depth="3" style="margin-left: 12px; font-size: 12px;">
            关闭后不发送 response_format，由后端代码修复模型输出
          </n-text>
        </n-form-item>
        <n-form-item label="输出 token 上限" path="max_output_tokens">
          <div style="width: 100%;">
            <n-input-number
              v-model:value="formData.max_output_tokens"
              :min="outputLimits.min_output_tokens"
              :max="outputLimits.max_output_tokens_bound"
              :step="512"
              style="width: 100%;"
            />
            <n-text depth="3" style="font-size: 12px;">
              保存时会自动向该端点探测这个模型的真实上限：探到就以端点为准，探不到沿用这里填的值。
              一批塞几题、每批给多少输出预算都由它推出来，填准比填大重要。
            </n-text>
          </div>
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" @click="handleSubmit" :loading="submitting">确定</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { modelApi } from '@/api'
import { AddOutline, CubeOutline, CreateOutline, TrashOutline } from '@vicons/ionicons5'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const submitting = ref(false)
const showModal = ref(false)
const isEdit = ref(false)
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)
const models = ref([])

const formRef = ref(null)
// 默认值与取值范围来自 /api/models/defaults，前端不抄一份字面量
const outputLimits = ref({})

const emptyForm = () => ({
  id: null,
  model_name: '',
  display_name: '',
  base_url: '',
  api_key: '',
  supports_vision: false,
  supports_json_mode: true,
  max_output_tokens: outputLimits.value.max_output_tokens ?? null
})

const formData = ref(emptyForm())

const rules = {
  model_name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入 API 地址', trigger: 'blur' }],
  api_key: [{
    // 读取接口已不下发明文密钥，编辑时留空表示保持原值，因此只有新建必填
    validator: (_rule, value) => {
      if (!isEdit.value && !value) return new Error('请输入 API 密钥')
      return true
    },
    trigger: ['blur', 'input']
  }]
}

const loadModels = async () => {
  loading.value = true
  try {
    models.value = await modelApi.list(userId.value)
  } catch (error) {
    message.error(error.message || '加载模型配置失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  isEdit.value = false
  formData.value = emptyForm()
  showModal.value = true
}

const editModel = (model) => {
  isEdit.value = true
  formData.value = {
    id: model.id,
    model_name: model.model_name,
    display_name: model.display_name === model.model_name ? '' : model.display_name,
    base_url: model.base_url,
    api_key: '',
    supports_vision: model.supports_vision,
    supports_json_mode: model.supports_json_mode,
    max_output_tokens: model.max_output_tokens
  }
  showModal.value = true
}

const payload = () => ({
  model_name: formData.value.model_name,
  display_name: formData.value.display_name || null,
  base_url: formData.value.base_url,
  supports_vision: formData.value.supports_vision,
  supports_json_mode: formData.value.supports_json_mode,
  max_output_tokens: formData.value.max_output_tokens
})

const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    if (isEdit.value) {
      const body = payload()
      if (formData.value.api_key) body.api_key = formData.value.api_key
      await modelApi.update(formData.value.id, userId.value, body)
      message.success('模型配置更新成功')
    } else {
      await modelApi.create({
        ...payload(),
        user_id: userId.value,
        api_key: formData.value.api_key
      })
      message.success('模型配置添加成功')
    }
    showModal.value = false
    loadModels()
  } catch (error) {
    message.error(error.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

const makeDefault = async (model) => {
  try {
    await modelApi.setDefault(model.id, userId.value)
    message.success(`已将「${model.display_name}」设为默认模型`)
    loadModels()
  } catch (error) {
    message.error(error.message || '设置默认模型失败')
  }
}

const deleteModel = (modelId) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除这个模型配置吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await modelApi.delete(modelId, userId.value)
        message.success('删除成功')
        loadModels()
      } catch (error) {
        message.error(error.message || '删除失败')
      }
    }
  })
}

onMounted(async () => {
  try {
    const limits = await modelApi.defaults()
    outputLimits.value = limits.data || {}
  } catch (error) {
    message.warning(`模型输出上限的取值范围加载失败：${error.message}`)
  }
  loadModels()
})
</script>
