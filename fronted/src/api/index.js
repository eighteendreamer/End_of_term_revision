import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 120000  // 全局超时改为 120 秒
})

const getErrorMessage = (error) => {
  const detail = error.response?.data?.detail

  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map(item => item.msg || item.message || JSON.stringify(item))
      .join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || JSON.stringify(detail)
  }

  return error.response?.data?.message || error.message || '请求失败'
}

// 请求拦截器 - 添加token
request.interceptors.request.use(
  config => {
    const token = sessionStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    const message = getErrorMessage(error)
    return Promise.reject(new Error(message))
  }
)

// ==================== 用户认证 API ====================
export const authApi = {
  // 用户注册
  register: (data) => request.post('/auth/register', data),

  // 用户登录
  login: (data) => request.post('/auth/login', data),

  // 获取当前用户
  me: (token) => request.get('/auth/me', { params: { token } }),

  // 完善/更新用户信息
  updateProfile: (token, data) => request.put('/auth/profile', data, { params: { token } }),

  // 检查账号信息是否完善
  checkProfile: (token) => request.get('/auth/check-profile', { params: { token } }),

  // 用户登出
  logout: () => request.post('/auth/logout')
}

// ==================== 科目管理 API ====================
export const subjectApi = {
  // 创建科目
  create: (data) => request.post('/subjects/', data),

  // 获取科目列表
  list: (userId) => request.get('/subjects/', { params: { user_id: userId } }),

  // 获取单个科目
  get: (subjectId) => request.get(`/subjects/${subjectId}`),

  // 删除科目
  delete: (subjectId, config) => request.delete(`/subjects/${subjectId}`, config)
}

// ==================== 题目管理 API ====================
export const questionApi = {
  // 创建题目
  create: (data) => request.post('/questions/', data),

  // 获取题目列表（支持分页）
  list: (params) => request.get('/questions/', { params }),

  // 获取题目列表（分页版本，推荐使用）
  listPaginated: (params) => {
    // params: { user_id, subject_id, question_type?, page?, page_size?, summary_only? }
    return request.get('/questions/', { params })
  },

  // 获取科目题型
  getTypes: (subjectId, userId) =>
    request.get(`/questions/types/${subjectId}`, { params: { user_id: userId } }),

  // 获取科目题目数量统计（查询所有题目）
  getStatistics: (subjectId, userId) =>
    request.get(`/questions/statistics/${subjectId}`, { params: { user_id: userId } }),

  // 获取用户所有题目的数量统计
  getAllStatistics: (userId) =>
    request.get('/questions/statistics', { params: { user_id: userId } }),

  // 获取单个题目
  get: (questionId) => request.get(`/questions/${questionId}`),

  // 删除题目
  delete: (questionId, config) => request.delete(`/questions/${questionId}`, config)
}

// ==================== 题目导入 API ====================
export const importApi = {
  // 预览：从文件解析（不保存）
  previewFromFile: (userId, subjectId, file) => {
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('subject_id', subjectId)
    formData.append('file', file)
    return request.post('/import/preview/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000
    })
  },

  // 预览：从图片解析（不保存）
  previewFromImage: (userId, subjectId, image) => {
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('subject_id', subjectId)
    formData.append('image', image)
    return request.post('/import/preview/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000
    })
  },

  // 预览：从文本解析（不保存）
  previewFromText: (data) => request.post('/import/preview/text', data),

  // 确认导入：保存题目到数据库
  confirmImport: (data) => request.post('/import/confirm', data),

  // 旧接口（保留兼容）
  fromFile: (userId, subjectId, file) => {
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('subject_id', subjectId)
    formData.append('file', file)
    return request.post('/import/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000  // 文件导入单独设置 180 秒超时
    })
  },

  // 从图片导入
  fromImage: (userId, subjectId, image) => {
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('subject_id', subjectId)
    formData.append('image', image)
    return request.post('/import/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000  // 图片导入单独设置 180 秒超时（AI 识别需要较长时间）
    })
  },

  // 从文本导入
  fromText: (data) => request.post('/import/text', data)
}

// ==================== 练习 API ====================
export const practiceApi = {
  // 开始练习
  start: (data) => request.post('/practice/start', data),

  // 提交答案
  submit: (data) => request.post('/practice/submit', data),

  // 今日统计
  todayStats: (userId) =>
    request.get('/practice/statistics/today', { params: { user_id: userId } }),

  // 本周统计
  weekStats: (userId) =>
    request.get('/practice/statistics/week', { params: { user_id: userId } }),

  // 全部统计
  allStats: (userId) =>
    request.get('/practice/statistics/all', { params: { user_id: userId } }),

  // 首页统计
  homeStats: (userId) =>
    request.get('/practice/statistics/home', { params: { user_id: userId } })
}

// ==================== 错题集 API ====================
export const errorApi = {
  // 获取错题列表
  list: (params) => request.get('/errors/', { params }),

  // 获取错题数量
  count: (params) => request.get('/errors/count', { params }),

  // 获取错题题型
  getTypes: (subjectId, userId) =>
    request.get(`/errors/types/${subjectId}`, { params: { user_id: userId } }),

  // 开始错题练习
  practice: (data) => request.post('/errors/practice', data),

  // 移除错题
  remove: (errorId, userId) => request.delete(`/errors/${errorId}`, { params: { user_id: userId } })
}

// ==================== AI 模型配置 API ====================
export const modelApi = {
  // 创建模型配置
  create: (data) => request.post('/models/', data),

  // 获取模型配置列表
  list: (userId) => request.get('/models/', { params: { user_id: userId } }),

  // 获取单个模型配置
  get: (modelId) => request.get(`/models/${modelId}`),

  // 更新模型配置
  update: (modelId, data) => request.put(`/models/${modelId}`, data),

  // 删除模型配置
  delete: (modelId) => request.delete(`/models/${modelId}`)
}

// ==================== 题目资源 API ====================
export const resourceApi = {
  // 创建资源
  create: (data) => request.post('/resources/', data),

  // 获取题目的所有资源
  getByQuestion: (questionId) => request.get(`/resources/question/${questionId}`),

  // 删除资源
  delete: (resourceId) => request.delete(`/resources/${resourceId}`)
}

// ==================== 共享管理 API ====================
export const shareApi = {
  // 设置共享
  setShare: (data) => request.post('/shares/', data),

  // 取消共享
  cancelShare: (subjectId, params) =>
    request.delete(`/shares/${subjectId}`, { params }),

  // 获取共享状态
  getStatus: (subjectId) => request.get(`/shares/status/${subjectId}`),

  // 获取我共享的科目
  getMyShared: (userId) =>
    request.get('/shares/my-shared', { params: { user_id: userId } }),

  // 搜索用户
  searchUsers: (keyword, userId) =>
    request.get('/shares/users/search', { params: { keyword, current_user_id: userId } })
}

// ==================== 排行榜 API ====================
export const leaderboardApi = {
  // 获取综合排行榜
  comprehensive: (params) =>
    request.get('/leaderboard/comprehensive', { params }),

  // 获取校级排行榜
  school: (schoolId, params) =>
    request.get(`/leaderboard/school/${schoolId}`, { params }),

  // 获取院级排行榜
  college: (collegeId, params) =>
    request.get(`/leaderboard/college/${collegeId}`, { params }),

  // 获取专业排行榜
  major: (majorId, params) =>
    request.get(`/leaderboard/major/${majorId}`, { params }),

  // 获取班级排行榜
  class: (params) =>
    request.get('/leaderboard/class', { params }),

  // 获取个人统计
  personal: (userId, params) =>
    request.get(`/leaderboard/personal/${userId}`, { params }),

  // 获取用户相关的所有排行榜（一次性）
  userLeaderboards: (userId, params) =>
    request.get(`/leaderboard/user-leaderboards/${userId}`, { params })
}

// ==================== 试卷练习 API ====================
export const examPaperApi = {
  // 创建试卷
  create: (data) => request.post('/exam-papers', data),

  // 获取试卷列表
  list: (userId, paperType = null, status = null) => {
    const params = { user_id: userId }
    if (paperType) params.paper_type = paperType
    if (status) params.status = status
    return request.get('/exam-papers', { params })
  },

  // 获取试卷详情
  get: (paperId, userId) =>
    request.get(`/exam-papers/${paperId}`, { params: { user_id: userId } }),

  // 保存答案（自动保存）
  save: (paperId, userId, answers) =>
    request.post(`/exam-papers/${paperId}/save-answer`, { user_id: userId, answers }),

  // 提交试卷
  submit: (paperId, userId, answers) =>
    request.post(`/exam-papers/${paperId}/submit`, { user_id: userId, answers })
}

// ==================== 资料管理 API ====================
export const materialApi = {
  // 上传资料
  upload: (userId, subjectId, file, name, materialType = 'other', tags = []) => {
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('subject_id', subjectId)
    formData.append('file', file)
    formData.append('name', name)
    formData.append('material_type', materialType)
    formData.append('tags', JSON.stringify(tags))
    return request.post('/materials', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000  // 3分钟超时
    })
  },

  // 获取资料列表
  list: (userId, subjectId = null, materialType = null, status = null, search = null) => {
    const params = { user_id: userId }
    if (subjectId) params.subject_id = subjectId
    if (materialType) params.material_type = materialType
    if (status) params.status = status
    if (search) params.search = search
    return request.get('/materials', { params })
  },

  // 获取资料详情
  get: (materialId, userId) =>
    request.get(`/materials/${materialId}`, { params: { user_id: userId } }),

  // 更新资料
  update: (materialId, data) =>
    request.put(`/materials/${materialId}`, data),

  // 删除资料
  delete: (materialId, userId) =>
    request.delete(`/materials/${materialId}`, { params: { user_id: userId } }),

  // 提取文本
  extractText: (materialId, userId, useAiOcr = false) =>
    request.post(`/materials/${materialId}/extract-text`, null, {
      params: { user_id: userId, use_ai_ocr: useAiOcr }
    }),

  // 生成题目
  generateQuestions: (materialId, userId, questionTypes, questionCounts) =>
    request.post(`/materials/${materialId}/generate-questions`, {
      user_id: userId,
      question_types: questionTypes,
      question_counts: questionCounts
    })
}

export default request

// ==================== 考试日程 API ====================
export const examScheduleApi = {
  // 获取全部考试日程
  list: (userId) =>
    request.get('/exam-schedules', { params: { user_id: userId } }),

  // 获取下一门考试（顶栏倒计时专用）
  upcoming: (userId) =>
    request.get('/exam-schedules/upcoming', { params: { user_id: userId } }),

  // 创建
  create: (data) =>
    request.post('/exam-schedules', data),

  // 更新
  update: (id, userId, data) =>
    request.put(`/exam-schedules/${id}`, data, { params: { user_id: userId } }),

  // 删除
  delete: (id, userId) =>
    request.delete(`/exam-schedules/${id}`, { params: { user_id: userId } }),
}

// ==================== 好友系统 API ====================
export const friendApi = {
  // 搜索用户
  search: (studentId, currentUserId) =>
    request.get('/friends/search', { params: { student_id: studentId, current_user_id: currentUserId } }),

  // 发送好友请求
  sendRequest: (friendId, currentUserId) =>
    request.post('/friends/request', { friend_id: friendId }, { params: { current_user_id: currentUserId } }),

  // 接受好友请求
  accept: (friendId, currentUserId) =>
    request.post('/friends/accept', { friend_id: friendId }, { params: { current_user_id: currentUserId } }),

  // 拒绝好友请求
  reject: (friendId, currentUserId) =>
    request.post('/friends/reject', { friend_id: friendId }, { params: { current_user_id: currentUserId } }),

  // 删除好友
  delete: (friendId, currentUserId) =>
    request.delete('/friends/delete', { params: { friend_id: friendId, current_user_id: currentUserId } }),

  // 拉黑用户
  block: (friendId, currentUserId) =>
    request.post('/friends/block', { friend_id: friendId }, { params: { current_user_id: currentUserId } }),

  // 获取好友列表
  list: (currentUserId) =>
    request.get('/friends/list', { params: { current_user_id: currentUserId } }),

  // 获取待处理的好友请求
  pending: (currentUserId) =>
    request.get('/friends/pending', { params: { current_user_id: currentUserId } })
}

// ==================== 聊天系统 API ====================
export const chatApi = {
  // 发送消息
  send: (toUserId, content, messageType, currentUserId) =>
    request.post('/chat/send', { to_user_id: toUserId, content, message_type: messageType }, 
      { params: { current_user_id: currentUserId } }),

  // 获取聊天历史
  history: (friendId, currentUserId, limit = 50, beforeMessageId = null) => {
    const params = { friend_id: friendId, current_user_id: currentUserId, limit }
    if (beforeMessageId) params.before_message_id = beforeMessageId
    return request.get('/chat/history', { params })
  },

  // 标记为已读
  markRead: (friendId, currentUserId) =>
    request.post('/chat/mark-read', null, { params: { friend_id: friendId, current_user_id: currentUserId } }),

  // 获取未读消息数
  unreadCount: (currentUserId, friendId = null) => {
    const params = { current_user_id: currentUserId }
    if (friendId) params.friend_id = friendId
    return request.get('/chat/unread-count', { params })
  },

  // 获取会话列表
  conversations: (currentUserId) =>
    request.get('/chat/conversations', { params: { current_user_id: currentUserId } })
}

// ==================== 个人信息管理 API ====================
export const profileApi = {
  // 获取个人信息（后端从 token 中提取 user_id，无需传参）
  get: () =>
    request.get('/profile/me'),

  // 更新个人信息
  update: (data) =>
    request.put('/profile/update', data),

  // 修改密码
  changePassword: (oldPassword, newPassword) =>
    request.post('/profile/change-password', { old_password: oldPassword, new_password: newPassword })
}

// ==================== WebSocket 连接 ====================
export class ChatWebSocket {
  constructor(userId) {
    this.userId = userId
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 3000
    this.messageHandlers = []
    this.statusHandlers = []
  }

  connect() {
    const token = sessionStorage.getItem('token')
    const wsUrl = `ws://localhost:8001/ws/${this.userId}?token=${encodeURIComponent(token || '')}`
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
      this.notifyStatus('connected')
    }

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      this.messageHandlers.forEach(handler => handler(data))
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.notifyStatus('error')
    }

    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.notifyStatus('disconnected')
      this.attemptReconnect()
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
      setTimeout(() => this.connect(), this.reconnectDelay)
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else {
      console.error('WebSocket is not connected')
    }
  }

  sendMessage(toUserId, content, messageType = 'text') {
    this.send({
      type: 'chat',
      to_user_id: toUserId,
      content,
      message_type: messageType
    })
  }

  sendTyping(toUserId, isTyping = true) {
    this.send({
      type: 'typing',
      to_user_id: toUserId,
      is_typing: isTyping
    })
  }

  onMessage(handler) {
    this.messageHandlers.push(handler)
  }

  onStatus(handler) {
    this.statusHandlers.push(handler)
  }

  notifyStatus(status) {
    this.statusHandlers.forEach(handler => handler(status))
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}
