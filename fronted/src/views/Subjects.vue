<template>
  <div>
    <n-page-header title="科目管理" subtitle="管理你的学习科目">
      <template #extra>
        <n-space>
          <n-button type="primary" @click="showModal = true">
            <template #icon>
              <n-icon><add-outline /></n-icon>
            </template>
            添加科目
          </n-button>
        </n-space>
      </template>
    </n-page-header>

    <n-spin :show="loading" style="margin-top: 24px;">
      <n-empty
        v-if="subjects.length === 0"
        description="还没有科目，快来添加一个吧！"
        style="margin-top: 60px;"
      />
      
      <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(450px, 450px)); gap: 24px; padding: 8px; margin-top: 24px;">
        <n-card
          v-for="subject in subjects"
          :key="subject.id"
          hoverable
          class="subject-card"
        >
          <template #header>
            <n-space align="center" justify="space-between" style="width: 100%;">
              <n-space align="center">
                <!-- 共享标识 -->
                <n-tag v-if="!subject.is_owner && subject.share_type === 'USER'" type="info" size="small">
                  🤝 共享
                </n-tag>
                <n-tag v-else-if="!subject.is_owner && subject.share_type === 'PUBLIC'" type="success" size="small">
                  🌍 公共
                </n-tag>
                <n-tag v-else type="default" size="small">
                  📘 我的
                </n-tag>
                
                <!-- 已共享标识（对于拥有者） -->
                <n-tag v-if="subject.is_owner && subject.has_shared" type="warning" size="small">
                  ✨ 已共享
                </n-tag>
              </n-space>
              
              <n-dropdown :options="getActions(subject)" @select="(key) => handleAction(key, subject)">
                <n-button text circle>
                  <template #icon>
                    <n-icon size="20"><ellipsis-horizontal-outline /></n-icon>
                  </template>
                </n-button>
              </n-dropdown>
            </n-space>
          </template>
          
          <div class="subject-card-content">
            <div class="subject-title">
              <n-text strong style="font-size: 20px;">{{ subject.name }}</n-text>
            </div>
            
            <n-space vertical size="small" class="subject-info">
              <!-- 显示拥有者信息（共享时） -->
              <n-text v-if="subject.owner_username" depth="3" style="font-size: 13px;">
                📤 来自：{{ subject.owner_username }}
              </n-text>
              <n-text depth="3" style="font-size: 13px;">
                🕒 创建时间：{{ subject.created_at }}
              </n-text>
            </n-space>
          </div>
        </n-card>
      </div>
    </n-spin>

    <!-- 添加科目对话框 -->
    <n-modal v-model:show="showModal" preset="dialog" title="添加科目">
      <n-form ref="formRef" :model="formData" :rules="rules">
        <n-form-item label="科目名称" path="name">
          <n-input
            v-model:value="formData.name"
            placeholder="请输入科目名称，如：数学、英语"
            @keyup.enter="handleSubmit"
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-space>
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" @click="handleSubmit" :loading="submitting">
            确定
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 共享设置对话框 -->
    <n-modal v-model:show="showShareModal" preset="card" title="共享设置" style="width: 600px;">
      <n-space vertical size="large">
        <!-- 当前科目信息 -->
        <n-alert type="info">
          正在为科目「{{ currentSubject?.name }}」设置共享
        </n-alert>

        <!-- 添加共享 -->
        <n-card title="添加共享" size="small">
          <n-space vertical>
            <n-radio-group v-model:value="shareForm.type">
              <n-space>
                <n-radio value="USER">指定用户</n-radio>
                <n-radio value="PUBLIC">公共共享</n-radio>
              </n-space>
            </n-radio-group>

            <n-form-item v-if="shareForm.type === 'USER'" label="搜索用户">
              <n-select
                v-model:value="shareForm.targetUserId"
                :options="userOptions"
                filterable
                remote
                clearable
                placeholder="输入用户名搜索"
                :loading="searchingUsers"
                @search="handleSearchUsers"
              />
            </n-form-item>

            <n-button type="primary" @click="handleAddShare" :loading="addingShare" block>
              添加共享
            </n-button>
          </n-space>
        </n-card>

        <!-- 当前共享列表 -->
        <n-card title="当前共享" size="small">
          <n-spin :show="loadingShares">
            <n-empty v-if="shareList.length === 0" description="还没有共享记录" />
            <n-list v-else bordered>
              <n-list-item v-for="share in shareList" :key="share.id">
                <n-space align="center" justify="space-between" style="width: 100%;">
                  <n-space align="center">
                    <n-tag :type="share.share_type === 'PUBLIC' ? 'success' : 'info'" size="small">
                      {{ share.share_type === 'PUBLIC' ? '🌍 公共' : '🤝 用户' }}
                    </n-tag>
                    <n-text>{{ share.share_type === 'PUBLIC' ? '所有用户可见' : share.target_username }}</n-text>
                  </n-space>
                  <n-button text type="error" @click="handleCancelShare(share)">
                    取消共享
                  </n-button>
                </n-space>
              </n-list-item>
            </n-list>
          </n-spin>
        </n-card>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { subjectApi, shareApi } from '@/api'
import { AddOutline, EllipsisHorizontalOutline, TrashOutline, ShareSocialOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const submitting = ref(false)
const showModal = ref(false)
const showShareModal = ref(false)
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)
const subjects = ref([])
const currentSubject = ref(null)
const shareList = ref([])
const loadingShares = ref(false)
const addingShare = ref(false)
const searchingUsers = ref(false)
const userOptions = ref([])

const formRef = ref(null)
const formData = ref({
  name: ''
})

const shareForm = ref({
  type: 'USER',
  targetUserId: null
})

const rules = {
  name: [
    { required: true, message: '请输入科目名称', trigger: 'blur' }
  ]
}

// 获取操作菜单
const getActions = (subject) => {
  const actions = []
  
  // 只有拥有者才能看到共享和删除按钮
  if (subject.is_owner) {
    actions.push({
      label: '共享设置',
      key: 'share',
      icon: () => h(NIcon, null, { default: () => h(ShareSocialOutline) })
    })
    actions.push({
      label: '删除',
      key: 'delete',
      icon: () => h(NIcon, null, { default: () => h(TrashOutline) })
    })
  }
  
  return actions
}

// 处理操作
const handleAction = (key, subject) => {
  if (key === 'delete') {
    handleDelete(subject)
  } else if (key === 'share') {
    handleShowShareModal(subject)
  }
}

// 显示共享设置对话框
const handleShowShareModal = async (subject) => {
  currentSubject.value = subject
  showShareModal.value = true
  await loadShareList(subject.id)
}

// 加载共享列表
const loadShareList = async (subjectId) => {
  loadingShares.value = true
  try {
    shareList.value = await shareApi.getStatus(subjectId)
    syncSubjectShareState(subjectId)
  } catch (error) {
    message.error(error.message || '加载共享列表失败')
  } finally {
    loadingShares.value = false
  }
}

const syncSubjectShareState = (subjectId) => {
  const hasShared = shareList.value.length > 0
  const subject = subjects.value.find(item => item.id === subjectId)
  if (subject) {
    subject.has_shared = hasShared
  }
  if (currentSubject.value?.id === subjectId) {
    currentSubject.value.has_shared = hasShared
  }
}

// 搜索用户
const handleSearchUsers = async (query) => {
  if (!query || query.length < 1) {
    userOptions.value = []
    return
  }
  
  searchingUsers.value = true
  try {
    const users = await shareApi.searchUsers(query, userId.value)
    userOptions.value = users.map(u => ({
      label: u.username,
      value: u.id
    }))
  } catch (error) {
    message.error(error.message || '搜索用户失败')
  } finally {
    searchingUsers.value = false
  }
}

// 添加共享
const handleAddShare = async () => {
  if (shareForm.value.type === 'USER' && !shareForm.value.targetUserId) {
    message.warning('请选择要共享的用户')
    return
  }
  
  addingShare.value = true
  try {
    await shareApi.setShare({
      owner_user_id: userId.value,
      subject_id: currentSubject.value.id,
      target_user_id: shareForm.value.type === 'USER' ? shareForm.value.targetUserId : null,
      share_type: shareForm.value.type
    })
    
    message.success('共享设置成功')
    shareForm.value.targetUserId = null
    await loadShareList(currentSubject.value.id)
    syncSubjectShareState(currentSubject.value.id)
    // 刷新科目列表以更新"已共享"标识
    await loadSubjects()
    syncSubjectShareState(currentSubject.value.id)
  } catch (error) {
    message.error(error.message || '共享设置失败')
  } finally {
    addingShare.value = false
  }
}

// 取消共享
const handleCancelShare = async (share) => {
  try {
    await shareApi.cancelShare(share.subject_id, {
      owner_user_id: userId.value,
      target_user_id: share.target_user_id,
      share_type: share.share_type
    })
    
    message.success('已取消共享')
    await loadShareList(currentSubject.value.id)
    syncSubjectShareState(currentSubject.value.id)
    // 刷新科目列表以更新"已共享"标识
    await loadSubjects()
    syncSubjectShareState(currentSubject.value.id)
  } catch (error) {
    message.error(error.message || '取消共享失败')
  }
}

// 加载科目列表
const loadSubjects = async () => {
  loading.value = true
  try {
    subjects.value = await subjectApi.list(userId.value)
  } catch (error) {
    message.error(error.message || '加载科目列表失败')
  } finally {
    loading.value = false
  }
}

// 提交表单
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    submitting.value = true
    
    await subjectApi.create({
      name: formData.value.name,
      user_id: userId.value
    })
    
    message.success('科目添加成功')
    showModal.value = false
    formData.value.name = ''
    loadSubjects()
  } catch (error) {
    if (error.message) {
      message.error(error.message)
    }
  } finally {
    submitting.value = false
  }
}

// 删除科目
const handleDelete = (subject) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除科目"${subject.name}"吗？\n\n删除后将会：\n• 删除该科目下的所有题目\n• 删除该科目的所有试卷\n• 删除该科目的所有答题记录\n• 删除该科目的错题集\n\n此操作不可恢复，请谨慎操作！`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await subjectApi.delete(subject.id, { params: { user_id: userId.value } })
        message.success('科目及相关数据已删除')
        loadSubjects()
      } catch (error) {
        message.error(error.message || '删除失败')
      }
    }
  })
}

onMounted(() => {
  loadSubjects()
})
</script>


<style scoped>
/* 科目卡片样式 */
.subject-card {
  width: 450px;
  height: 220px;
  display: flex;
  flex-direction: column;
}

/* 卡片内容区域 */
.subject-card-content {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  padding: 8px 0;
}

/* 科目标题 */
.subject-title {
  flex: 1;
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

/* 科目信息 */
.subject-info {
  margin-top: auto;
}

/* 卡片头部优化 */
:deep(.n-card-header) {
  padding: 16px 20px;
}

/* 卡片内容区域优化 */
:deep(.n-card__content) {
  padding: 16px 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
