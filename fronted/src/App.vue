<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <!-- 主界面 -->
          <n-layout style="height: 100vh">
            <n-layout-header bordered style="height: 64px; padding: 0 24px; display: flex; align-items: center;">
              <div style="display: flex; align-items: center; gap: 12px; flex: 1;">
                <img src="./assets/logo.svg" alt="Logo" style="width: 40px; height: 40px;" />
                <h2 style="margin: 0;">神阁卷藏</h2>
              </div>
              <n-space v-if="isLoggedIn">
                <n-button @click="showSystemInfo">
                  <template #icon>
                    <n-icon><information-circle-outline /></n-icon>
                  </template>
                  系统信息
                </n-button>
                <n-tag type="info" style="cursor: pointer" @click="showProfileModal = true">
                  {{ currentUser?.username }}
                </n-tag>
                <n-button text @click="handleLogout">
                  <template #icon>
                    <n-icon><log-out-outline /></n-icon>
                  </template>
                  退出
                </n-button>
              </n-space>
              <n-space v-else>
                <n-button type="primary" @click="showAuthModal = true">
                  登录 / 注册
                </n-button>
              </n-space>
            </n-layout-header>
            
            <n-layout has-sider style="height: calc(100vh - 64px)">
              <n-layout-sider
                bordered
                show-trigger
                collapse-mode="width"
                :collapsed-width="64"
                :width="240"
                :native-scrollbar="false"
              >
                <n-menu
                  :collapsed-width="64"
                  :collapsed-icon-size="22"
                  :options="menuOptions"
                  :value="activeKey"
                  @update:value="handleMenuSelect"
                />
              </n-layout-sider>
              
              <n-layout-content
                content-style="padding: 24px;"
                :native-scrollbar="false"
              >
                <div v-if="!isLoggedIn" style="height: 100%; display: flex; align-items: center; justify-content: center;">
                  <n-empty description="请先登录以使用系统功能" style="margin-top: -100px;">
                    <template #extra>
                      <n-button type="primary" @click="showAuthModal = true">
                        立即登录
                      </n-button>
                    </template>
                  </n-empty>
                </div>
                <router-view v-else />
              </n-layout-content>
            </n-layout>
          </n-layout>

          <!-- 登录注册弹窗 -->
          <n-modal 
            v-model:show="showAuthModal" 
            :mask-closable="false"
            :close-on-esc="false"
            :closable="false"
            preset="card"
            style="width: 450px;"
            title="欢迎使用神阁卷藏"
          >
            <n-tabs v-model:value="authTab" type="segment" animated>
              <!-- 登录标签页 -->
              <n-tab-pane name="login" tab="登录">
                <n-form ref="loginFormRef" :model="loginForm" :rules="loginRules" style="margin-top: 20px;">
                  <n-form-item path="account" label="学号">
                    <n-input 
                      v-model:value="loginForm.account" 
                      placeholder="请输入学号"
                      @keyup.enter="handleLogin"
                    />
                  </n-form-item>
                  <n-form-item path="password" label="密码">
                    <n-input 
                      v-model:value="loginForm.password" 
                      type="password" 
                      show-password-on="click"
                      placeholder="请输入密码"
                      @keyup.enter="handleLogin"
                    />
                  </n-form-item>
                  <n-button 
                    type="primary" 
                    block 
                    :loading="loading"
                    @click="handleLogin"
                  >
                    登录
                  </n-button>
                </n-form>
              </n-tab-pane>
              
              <!-- 注册标签页 -->
              <n-tab-pane name="register" tab="注册">
                <n-form ref="registerFormRef" :model="registerForm" :rules="registerRules" style="margin-top: 20px;">
                  <n-form-item path="student_id" label="学号">
                    <n-input 
                      v-model:value="registerForm.student_id" 
                      placeholder="请输入学号（唯一标识）"
                    />
                  </n-form-item>
                  <n-form-item path="username" label="用户名">
                    <n-input 
                      v-model:value="registerForm.username" 
                      placeholder="请输入用户名"
                    />
                  </n-form-item>
                  <n-form-item path="password" label="密码">
                    <n-input 
                      v-model:value="registerForm.password" 
                      type="password" 
                      show-password-on="click"
                      placeholder="至少6个字符"
                    />
                  </n-form-item>
                  <n-form-item path="confirmPassword" label="确认密码">
                    <n-input 
                      v-model:value="registerForm.confirmPassword" 
                      type="password" 
                      show-password-on="click"
                      placeholder="再次输入密码"
                    />
                  </n-form-item>
                  <n-form-item path="school" label="学校">
                    <n-input 
                      v-model:value="registerForm.school" 
                      placeholder="请输入学校（必填）"
                    />
                  </n-form-item>
                  <n-form-item path="college" label="二级学院">
                    <n-input 
                      v-model:value="registerForm.college" 
                      placeholder="请输入二级学院（可选）"
                    />
                  </n-form-item>
                  <n-form-item path="major" label="专业">
                    <n-input 
                      v-model:value="registerForm.major" 
                      placeholder="请输入专业（可选）"
                    />
                  </n-form-item>
                  <n-form-item path="class_name" label="班级">
                    <n-input 
                      v-model:value="registerForm.class_name" 
                      placeholder="请输入班级（必填）"
                    />
                  </n-form-item>
                  <n-form-item path="gender" label="性别">
                    <n-select 
                      v-model:value="registerForm.gender" 
                      :options="genderOptions"
                      placeholder="请选择性别（必填）"
                    />
                  </n-form-item>
                  <n-button 
                    type="primary" 
                    block 
                    :loading="loading"
                    @click="handleRegister"
                  >
                    注册
                  </n-button>
                </n-form>
              </n-tab-pane>
            </n-tabs>
          </n-modal>

          <!-- 个人信息弹窗 -->
          <n-modal 
            v-model:show="showProfileModal" 
            :mask-closable="!isFirstTimeSetup"
            :close-on-esc="!isFirstTimeSetup"
            :closable="!isFirstTimeSetup"
            preset="card"
            style="width: 500px;"
            :title="isFirstTimeSetup ? '完善账号信息' : '个人信息'"
          >
            <n-alert v-if="isFirstTimeSetup" type="warning" style="margin-bottom: 16px;">
              内测用户首次登录必须完善信息并设置新密码，完善后才能使用系统功能
            </n-alert>
            
            <n-tabs v-if="!isFirstTimeSetup" type="segment" animated>
              <!-- 基本信息标签页 -->
              <n-tab-pane name="info" tab="基本信息">
                <n-form ref="profileFormRef" :model="profileForm" :rules="profileRules" style="margin-top: 16px;">
                  <n-form-item path="username" label="用户名">
                    <n-input 
                      v-model:value="profileForm.username" 
                      placeholder="请输入用户名"
                    />
                  </n-form-item>
                  <n-form-item label="学号">
                    <n-input 
                      :value="profileForm.student_id" 
                      disabled
                      placeholder="学号不可修改"
                    />
                  </n-form-item>
                  <n-form-item path="school" label="学校">
                    <n-input 
                      v-model:value="profileForm.school" 
                      placeholder="请输入学校"
                    />
                  </n-form-item>
                  <n-form-item path="college" label="二级学院">
                    <n-input 
                      v-model:value="profileForm.college" 
                      placeholder="请输入二级学院"
                    />
                  </n-form-item>
                  <n-form-item path="major" label="专业">
                    <n-input 
                      v-model:value="profileForm.major" 
                      placeholder="请输入专业"
                    />
                  </n-form-item>
                  <n-form-item path="class_name" label="班级">
                    <n-input 
                      v-model:value="profileForm.class_name" 
                      placeholder="请输入班级"
                    />
                  </n-form-item>
                  <n-space justify="end">
                    <n-button @click="showProfileModal = false">
                      取消
                    </n-button>
                    <n-button 
                      type="primary" 
                      :loading="loading"
                      @click="handleUpdateBasicInfo"
                    >
                      保存
                    </n-button>
                  </n-space>
                </n-form>
              </n-tab-pane>
              
              <!-- 修改密码标签页 -->
              <n-tab-pane name="password" tab="修改密码">
                <n-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" style="margin-top: 16px;">
                  <n-form-item path="old_password" label="旧密码">
                    <n-input 
                      v-model:value="passwordForm.old_password" 
                      type="password"
                      show-password-on="click"
                      placeholder="请输入旧密码"
                    />
                  </n-form-item>
                  <n-form-item path="new_password" label="新密码">
                    <n-input 
                      v-model:value="passwordForm.new_password" 
                      type="password"
                      show-password-on="click"
                      placeholder="请输入新密码（至少6个字符）"
                    />
                  </n-form-item>
                  <n-form-item path="confirm_password" label="确认密码">
                    <n-input 
                      v-model:value="passwordForm.confirm_password" 
                      type="password"
                      show-password-on="click"
                      placeholder="请再次输入新密码"
                    />
                  </n-form-item>
                  <n-space justify="end">
                    <n-button @click="resetPasswordForm">
                      重置
                    </n-button>
                    <n-button 
                      type="primary" 
                      :loading="changingPassword"
                      @click="handleChangePassword"
                    >
                      修改密码
                    </n-button>
                  </n-space>
                </n-form>
              </n-tab-pane>
            </n-tabs>
            
            <!-- 首次设置表单 -->
            <n-form v-else ref="profileFormRef" :model="profileForm" :rules="profileRules">
              <n-form-item path="student_id" label="学号">
                <n-input 
                  v-model:value="profileForm.student_id" 
                  placeholder="请输入学号（必填，用于后续登录）"
                />
              </n-form-item>
              <n-form-item path="username" label="用户名">
                <n-input 
                  v-model:value="profileForm.username" 
                  placeholder="请输入用户名（必填）"
                />
              </n-form-item>
              <n-form-item path="password" label="新密码">
                <n-input 
                  v-model:value="profileForm.password" 
                  type="password"
                  show-password-on="click"
                  placeholder="请设置新密码（至少6个字符）"
                />
              </n-form-item>
              <n-form-item path="confirmPassword" label="确认密码">
                <n-input 
                  v-model:value="profileForm.confirmPassword" 
                  type="password"
                  show-password-on="click"
                  placeholder="请再次输入密码"
                />
              </n-form-item>
              <n-form-item path="school" label="学校">
                <n-input 
                  v-model:value="profileForm.school" 
                  placeholder="请输入学校（必填）"
                />
              </n-form-item>
              <n-form-item path="college" label="二级学院">
                <n-input 
                  v-model:value="profileForm.college" 
                  placeholder="请输入二级学院（可选）"
                />
              </n-form-item>
              <n-form-item path="major" label="专业">
                <n-input 
                  v-model:value="profileForm.major" 
                  placeholder="请输入专业（可选）"
                />
              </n-form-item>
              <n-form-item path="class_name" label="班级">
                <n-input 
                  v-model:value="profileForm.class_name" 
                  placeholder="请输入班级（必填）"
                />
              </n-form-item>
              <n-form-item path="gender" label="性别">
                <n-select 
                  v-model:value="profileForm.gender" 
                  :options="genderOptions"
                  placeholder="请选择性别（必填）"
                />
              </n-form-item>
              <n-space justify="end">
                <n-button 
                  type="primary" 
                  :loading="loading"
                  @click="handleUpdateProfile"
                >
                  保存并完成
                </n-button>
              </n-space>
            </n-form>
          </n-modal>
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, h, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { createDiscreteApi } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { 
  NIcon,
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  NLayout,
  NLayoutHeader,
  NLayoutSider,
  NLayoutContent,
  NMenu,
  NSpace,
  NTag,
  NButton,
  NCard,
  NTabs,
  NTabPane,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NEmpty,
  NSelect,
  NAlert
} from 'naive-ui'
import {
  HomeOutline,
  BookOutline,
  CloudUploadOutline,
  CreateOutline,
  AlertCircleOutline,
  SettingsOutline,
  ServerOutline,
  LogOutOutline,
  LibraryOutline,
  TimeOutline,
  InformationCircleOutline,
  TrophyOutline,
  FolderOutline,
  ChatbubbleEllipsesOutline,
  PersonOutline
} from '@vicons/ionicons5'
import { authApi, profileApi } from './api'
import { useUserStore } from './stores/user'
import { md5 } from './utils/crypto'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 创建独立的 message 和 notification API
const { message, notification } = createDiscreteApi(['message', 'notification'])

// 认证状态（使用 store）
const { isLoggedIn, currentUser } = storeToRefs(userStore)
const authTab = ref('login')
const loading = ref(false)
const showAuthModal = ref(false)
const showProfileModal = ref(false)
const isFirstTimeSetup = ref(false)
const changingPassword = ref(false)

// 密码修改表单
const passwordFormRef = ref(null)
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const passwordRules = {
  old_password: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value) => {
        return value === passwordForm.value.new_password
      },
      message: '两次输入的密码不一致',
      trigger: 'blur'
    }
  ]
}

// 性别选项
const genderOptions = [
  { label: '男', value: 'male' },
  { label: '女', value: 'female' },
  { label: '隐藏', value: 'hidden' }
]

// 登录表单
const loginFormRef = ref(null)
const loginForm = ref({
  account: '',  // 学号或用户名
  password: ''
})

const loginRules = {
  account: [
    { required: true, message: '请输入学号', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

// 注册表单
const registerFormRef = ref(null)
const registerForm = ref({
  student_id: '',
  username: '',
  password: '',
  confirmPassword: '',
  school: '',
  college: '',
  major: '',
  class_name: '',
  gender: null
})

const registerRules = {
  student_id: [
    { required: true, message: '请输入学号', trigger: 'blur' },
    { min: 1, max: 50, message: '学号长度为1-50个字符', trigger: 'blur' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 255, message: '用户名长度为2-255个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value) => {
        return value === registerForm.value.password
      },
      message: '两次输入的密码不一致',
      trigger: 'blur'
    }
  ],
  school: [
    { required: true, message: '请输入学校', trigger: 'blur' }
  ],
  class_name: [
    { required: true, message: '请输入班级', trigger: 'blur' }
  ],
  gender: [
    { required: true, message: '请选择性别', trigger: 'change' }
  ]
}

// 账号信息完善表单
const profileFormRef = ref(null)
const profileForm = ref({
  student_id: '',
  username: '',
  password: '',
  confirmPassword: '',
  school: '',
  college: '',
  major: '',
  class_name: '',
  gender: null
})

const profileRules = {
  student_id: [
    { required: true, message: '请输入学号', trigger: 'blur' },
    { min: 1, max: 50, message: '学号长度为1-50个字符', trigger: 'blur' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 255, message: '用户名长度为2-255个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请设置密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value) => {
        return value === profileForm.value.password
      },
      message: '两次输入的密码不一致',
      trigger: 'blur'
    }
  ],
  school: [
    { required: true, message: '请输入学校', trigger: 'blur' }
  ],
  class_name: [
    { required: true, message: '请输入班级', trigger: 'blur' }
  ],
  gender: [
    { required: true, message: '请选择性别', trigger: 'change' }
  ]
}

// 登录处理
const handleLogin = async () => {
  try {
    await loginFormRef.value?.validate()
    loading.value = true
    
    // 对密码进行MD5加密
    const password_md5 = md5(loginForm.value.password)
    
    // 智能判断：如果account看起来像学号（纯数字或TEMP开头），用student_id，否则用username
    const isStudentId = /^(TEMP)?\d+$/.test(loginForm.value.account)
    
    const response = await authApi.login({
      student_id: isStudentId ? loginForm.value.account : undefined,
      username: !isStudentId ? loginForm.value.account : undefined,
      password_md5
    })
    
    // 使用 store 保存用户信息
    userStore.setUser(response.user, response.token)
    showAuthModal.value = false
    
    message.success('登录成功！')
    
    // 内测用户（profile_completed=0）必须完善信息
    if (response.profile_completed === 0) {
      // 立即显示完善信息弹窗
      setTimeout(() => {
        showProfileCompleteModal()
      }, 500)
    }
  } catch (error) {
    if (error.errors) return // 表单验证错误
    message.error(error.message || '登录失败')
  } finally {
    loading.value = false
  }
}

// 注册处理
const handleRegister = async () => {
  try {
    await registerFormRef.value?.validate()
    loading.value = true
    
    // 对密码进行MD5加密
    const password_md5 = md5(registerForm.value.password)
    
    const response = await authApi.register({
      student_id: registerForm.value.student_id,
      username: registerForm.value.username,
      password_md5,
      school: registerForm.value.school || null,
      college: registerForm.value.college || null,
      major: registerForm.value.major || null,
      class_name: registerForm.value.class_name || null,
      gender: registerForm.value.gender || null
    })
    
    // 使用 store 保存用户信息
    userStore.setUser(response.user, response.token)
    showAuthModal.value = false
    
    message.success('注册成功！')
    
    // 检查账号信息是否完善
    if (response.profile_completed === 0 && response.message) {
      notification.warning({
        title: '请完善账号信息',
        content: response.message,
        duration: 5000,
        action: () =>
          h(
            NButton,
            {
              text: true,
              type: 'primary',
              onClick: () => {
                showProfileCompleteModal()
              }
            },
            { default: () => '立即完善' }
          )
      })
    }
  } catch (error) {
    if (error.errors) return // 表单验证错误
    message.error(error.message || '注册失败')
  } finally {
    loading.value = false
  }
}

// 显示账号信息完善弹窗（首次设置）
const showProfileCompleteModal = () => {
  isFirstTimeSetup.value = true
  // 不填充已有信息，让用户重新填写
  // 但保留当前用户名作为提示
  profileForm.value = {
    student_id: '',
    username: currentUser.value?.username || '',
    password: '',
    confirmPassword: '',
    school: '',
    college: '',
    major: '',
    class_name: '',
    gender: null
  }
  showProfileModal.value = true
}

// 加载个人信息（用于编辑）
const loadProfileInfo = async () => {
  try {
    const res = await profileApi.get()
    if (res.code === 200) {
      const data = res.data
      profileForm.value = {
        student_id: data.student_id,
        username: data.username,
        school: data.school_name || '',
        college: data.college_name || '',
        major: data.major_name || '',
        class_name: data.class_name || '',
        gender: data.gender || null,
        password: '',
        confirmPassword: ''
      }
    }
  } catch (error) {
    message.error('加载个人信息失败')
  }
}

// 点击用户名显示个人信息弹窗
watch(showProfileModal, async (newVal) => {
  if (newVal && !isFirstTimeSetup.value) {
    await loadProfileInfo()
  }
})

// 完善账号信息（首次设置）
const handleUpdateProfile = async () => {
  try {
    await profileFormRef.value?.validate()
    loading.value = true
    
    const token = sessionStorage.getItem('token')
    
    // 对新密码进行MD5加密
    const password_md5 = md5(profileForm.value.password)
    
    const response = await authApi.updateProfile(token, {
      student_id: profileForm.value.student_id,
      username: profileForm.value.username,
      password_md5: password_md5,
      school: profileForm.value.school,
      college: profileForm.value.college || null,
      major: profileForm.value.major || null,
      class_name: profileForm.value.class_name,
      gender: profileForm.value.gender
    })
    
    // 关闭弹窗
    showProfileModal.value = false
    isFirstTimeSetup.value = false
    
    // 提示用户
    message.success('账号信息已完善！')
    
    // 延迟1秒后退出登录，让用户使用新学号和密码登录
    setTimeout(() => {
      userStore.logout()
      showAuthModal.value = true
      notification.info({
        title: '请重新登录',
        content: '请使用新学号和密码登录系统',
        duration: 5000
      })
    }, 1000)
  } catch (error) {
    if (error.errors) return // 表单验证错误
    message.error(error.message || '更新失败')
  } finally {
    loading.value = false
  }
}

// 更新基本信息
const handleUpdateBasicInfo = async () => {
  try {
    await profileFormRef.value?.validate()
    loading.value = true
    
    const res = await profileApi.update({
      username: profileForm.value.username,
      school_id: profileForm.value.school || null,
      college_id: profileForm.value.college || null,
      major_id: profileForm.value.major || null,
      class_name: profileForm.value.class_name || null
    })
    
    if (res.code === 200) {
      message.success('保存成功')
      // 更新store中的用户名
      userStore.username = profileForm.value.username
      showProfileModal.value = false
    }
  } catch (error) {
    if (error.errors) return // 表单验证错误
    message.error(error.response?.data?.detail || '保存失败')
  } finally {
    loading.value = false
  }
}

// 修改密码
const handleChangePassword = async () => {
  try {
    await passwordFormRef.value?.validate()
    changingPassword.value = true
    
    const res = await profileApi.changePassword(
      passwordForm.value.old_password,
      passwordForm.value.new_password
    )
    
    if (res.code === 200) {
      message.success('密码修改成功，请重新登录')
      resetPasswordForm()
      
      // 延迟1秒后退出登录
      setTimeout(() => {
        userStore.logout()
        showProfileModal.value = false
        showAuthModal.value = true
      }, 1000)
    }
  } catch (error) {
    if (error.errors) return // 表单验证错误
    message.error(error.response?.data?.detail || '修改失败')
  } finally {
    changingPassword.value = false
  }
}

// 重置密码表单
const resetPasswordForm = () => {
  passwordForm.value = {
    old_password: '',
    new_password: '',
    confirm_password: ''
  }
  passwordFormRef.value?.restoreValidation()
}

// 登出处理
const handleLogout = () => {
  userStore.logout()
  showAuthModal.value = true
  message.info('已退出登录')
}

// 显示系统信息
const showSystemInfo = () => {
  notification.info({
    title: '系统信息',
    content: '版本：v2.0.0\n作者：程序员Eighteen\n联系方式：QQ邮箱：3273495516@qq.com',
    meta: '神阁卷藏 - AI智能期末复习系统',
    duration: 5000,
    keepAliveOnHover: true
  })
}

// 初始化检查登录状态
onMounted(() => {
  const success = userStore.initUser()
  if (!success) {
    // 未登录或初始化失败，显示登录弹窗
    showAuthModal.value = true
  }
})

// 当前激活的菜单项
const activeKey = computed(() => route.path)

// 主题配置
const themeOverrides = {
  common: {
    primaryColor: '#18a058',
    primaryColorHover: '#36ad6a',
    primaryColorPressed: '#0c7a43'
  }
}

// 渲染图标
const renderIcon = (icon) => {
  return () => h(NIcon, null, { default: () => h(icon) })
}

// 菜单选项
const menuOptions = [
  {
    label: '首页',
    key: '/',
    icon: renderIcon(HomeOutline)
  },
  {
    label: '科目管理',
    key: '/subjects',
    icon: renderIcon(BookOutline)
  },
  {
    label: '题库管理',
    key: '/question-bank',
    icon: renderIcon(LibraryOutline)
  },
  {
    label: '资料库',
    key: '/materials',
    icon: renderIcon(FolderOutline)
  },
  {
    label: '导入题目',
    key: '/import',
    icon: renderIcon(CloudUploadOutline)
  },
  {
    label: '开始练习',
    key: '/practice',
    icon: renderIcon(CreateOutline)
  },
  {
    label: '错题集',
    key: '/errors',
    icon: renderIcon(AlertCircleOutline)
  },
  {
    label: '做题记录',
    key: '/practice-history',
    icon: renderIcon(TimeOutline)
  },
  {
    label: '排行榜',
    key: '/leaderboard',
    icon: renderIcon(TrophyOutline)
  },
  {
    label: '聊天',
    key: '/chat',
    icon: renderIcon(ChatbubbleEllipsesOutline)
  },
  {
    type: 'divider'
  },
  {
    label: '配置',
    key: 'config',
    icon: renderIcon(SettingsOutline),
    children: [
      {
        label: 'AI 模型配置',
        key: '/model-config'
      }
    ]
  }
]

// 菜单选择处理
const handleMenuSelect = (key) => {
  router.push(key)
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

#app {
  height: 100vh;
}
</style>
