<template>
  <div class="chat-page">
    <!-- 主容器 -->
    <div class="chat-container">
      <!-- 中间列表区 (好友列表) -->
      <section class="list-column">
        <!-- 搜索栏 -->
        <div class="search-bar-wrapper">
          <div class="search-bar">
            <input v-model="searchKeyword" type="text" placeholder="搜索" class="search-input">
            <i class="fa-solid fa-magnifying-glass search-icon"></i>
            <button class="add-btn" @click="showSearchDialog = true">
              <i class="fa-solid fa-plus"></i>
            </button>
          </div>
        </div>

        <!-- 好友请求徽章 -->
        <div v-if="pendingCount > 0" class="pending-badge" @click="showPendingDialog = true">
          <span>好友请求</span>
          <span class="badge">{{ pendingCount }}</span>
        </div>

        <!-- 好友列表 -->
        <div class="list-container custom-scrollbar">
          <div v-if="filteredFriends.length === 0" class="empty-state">
            <i class="fa-solid fa-users empty-icon"></i>
            <p>暂无好友</p>
          </div>
          <div
            v-for="friend in filteredFriends"
            :key="friend.user_id"
            @click="openChat(friend)"
            :class="['list-card', { active: currentFriend?.user_id === friend.user_id }]"
          >
            <div class="avatar-wrapper">
              <div class="avatar" :style="{ background: getAvatarColor(friend.username) }">
                {{ friend.username.charAt(0) }}
              </div>
              <span v-if="friend.unreadCount > 0" class="unread-badge">{{ friend.unreadCount > 99 ? '99+' : friend.unreadCount }}</span>
            </div>
            <div class="friend-info">
              <div class="friend-header">
                <h3 class="friend-name">{{ friend.username }}</h3>
                <span class="last-time">{{ getLastTime(friend.last_message_time) }}</span>
              </div>
              <p class="last-message">{{ friend.last_message || '暂无消息' }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 右侧聊天/内容区 -->
      <main class="main-content">
        <template v-if="currentFriend">
          <!-- 聊天头部 -->
          <header class="chat-header">
            <div class="header-info">
              <h2 class="chat-title">{{ currentFriend.username }}</h2>
              <span class="chat-subtitle">{{ currentFriend.student_id }}</span>
            </div>
          </header>

          <!-- 聊天历史记录 -->
          <div ref="messageListRef" class="chat-messages custom-scrollbar">
            <div class="messages-inner">
              <div v-if="messages.length === 0" class="empty-chat">
                <i class="fa-regular fa-comments empty-icon"></i>
                <p>暂无消息</p>
              </div>

              <template v-for="(msg, index) in messages" :key="msg.message_id || index">
                <!-- 时间轴 -->
                <div v-if="shouldShowTime(index)" class="time-divider">
                  <span class="time-text">{{ formatMessageTime(msg.created_at) }}</span>
                </div>

                <!-- 消息：左侧 (接收) -->
                <div v-if="msg.from_user_id !== currentUserId" class="message-wrapper message-left">
                  <div class="avatar" :style="{ background: getAvatarColor(currentFriend.username) }">
                    {{ currentFriend.username.charAt(0) }}
                </div>
                <div class="message-content-left">
                  <span class="sender-name">{{ currentFriend.username }}</span>
                  <div class="bubble bubble-left">
                    <div v-if="msg.message_type === 'text'" class="message-text">{{ msg.content }}</div>
                    <div v-else-if="msg.message_type === 'image'" class="message-image">
                      <img :src="msg.content" alt="图片" />
                    </div>
                  </div>
                </div>
              </div>

              <!-- 消息：右侧 (发送) -->
              <div v-else class="message-wrapper message-right">
                <div class="message-content-right">
                  <span class="sender-name sender-name-right">我</span>
                  <div class="bubble bubble-right">
                    <div v-if="msg.message_type === 'text'" class="message-text">{{ msg.content }}</div>
                    <div v-else-if="msg.message_type === 'image'" class="message-image">
                      <img :src="msg.content" alt="图片" />
                    </div>
                  </div>
                </div>
                <div class="avatar" :style="{ background: getAvatarColor(username) }">
                  {{ username.charAt(0) }}
                </div>
              </div>
              </template>

              <!-- 正在输入提示 -->
              <div v-if="isTyping" class="typing-indicator">
                <span>{{ currentFriend.username }} 正在输入...</span>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <footer class="input-area">
            <!-- 工具栏 -->
            <div class="input-toolbar">
              <button class="toolbar-btn"><i class="fa-regular fa-face-smile"></i></button>
              <button class="toolbar-btn"><i class="fa-regular fa-image"></i></button>
              <button class="toolbar-btn"><i class="fa-regular fa-folder-open"></i></button>
              <button class="toolbar-btn"><i class="fa-solid fa-scissors"></i></button>
              <button class="toolbar-btn toolbar-btn-auto"><i class="fa-regular fa-clock"></i></button>
            </div>
            <!-- 文本框 -->
            <textarea
              v-model="messageText"
              placeholder="请输入内容..."
              class="message-textarea no-scrollbar"
              @keydown.enter.exact.prevent="sendMessage"
              @input="handleTyping"
            ></textarea>
            <!-- 发送按钮 -->
            <div class="send-btn-wrapper">
              <button @click="sendMessage" class="send-btn">发送(S)</button>
            </div>
          </footer>
        </template>

        <!-- 未选择好友状态 -->
        <div v-else class="empty-main">
          <i class="fa-regular fa-comment-dots empty-icon"></i>
          <p>选择一个好友开始聊天</p>
        </div>
      </main>
    </div>

    <!-- 搜索用户对话框 -->
    <div v-if="showSearchDialog" class="modal-overlay" @click="showSearchDialog = false">
      <div class="modal-card" @click.stop>
        <div class="modal-header">
          <h3>添加好友</h3>
          <button class="modal-close" @click="showSearchDialog = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="search-input-group">
            <input
              v-model="searchStudentId"
              placeholder="输入学号搜索"
              class="modal-input"
              @keyup.enter="searchUsers"
            />
            <button @click="searchUsers" class="search-submit-btn"><i class="fa-solid fa-magnifying-glass"></i></button>
          </div>
          
          <div v-if="searching" class="loading">搜索中...</div>
          <div v-else-if="searchResults.length === 0" class="empty-state">暂无搜索结果</div>
          <div v-else class="search-results">
            <div v-for="user in searchResults" :key="user.user_id" class="search-result-item">
              <div class="avatar" :style="{ background: getAvatarColor(user.username) }">
                {{ user.username.charAt(0) }}
              </div>
              <div class="result-info">
                <div class="result-name">{{ user.username }}</div>
                <div class="result-desc">学号: {{ user.student_id }}</div>
              </div>
              <button
                v-if="!user.friendship_status"
                @click="sendFriendRequest(user)"
                class="add-friend-btn-small"
              >
                添加
              </button>
              <span v-else class="status-tag">{{ getStatusText(user.friendship_status) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 好友请求对话框 -->
    <div v-if="showPendingDialog" class="modal-overlay" @click="showPendingDialog = false">
      <div class="modal-card" @click.stop>
        <div class="modal-header">
          <h3>好友请求</h3>
          <button class="modal-close" @click="showPendingDialog = false">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingPending" class="loading">加载中...</div>
          <div v-else-if="pendingRequests.length === 0" class="empty-state">暂无好友请求</div>
          <div v-else class="pending-requests">
            <div v-for="user in pendingRequests" :key="user.user_id" class="pending-request-item">
              <div class="avatar" :style="{ background: getAvatarColor(user.username) }">
                {{ user.username.charAt(0) }}
              </div>
              <div class="result-info">
                <div class="result-name">{{ user.username }}</div>
                <div class="result-desc">学号: {{ user.student_id }}</div>
                <div class="result-time">{{ formatTime(user.requested_at) }}</div>
              </div>
              <div class="request-actions">
                <button @click="acceptRequest(user)" class="accept-btn">接受</button>
                <button @click="rejectRequest(user)" class="reject-btn">拒绝</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { chatApi, friendApi, ChatWebSocket } from '@/api'
import { useUserStore } from '@/stores/user'
import { getAvatarColor } from '@/utils/avatarUtils'

const userStore = useUserStore()
const currentUserId = computed(() => userStore.userId)
const username = computed(() => userStore.username)

// 好友列表相关
const friends = ref([])
const filteredFriends = ref([])
const searchKeyword = ref('')
const currentFriend = ref(null)

// 搜索用户相关
const showSearchDialog = ref(false)
const searchStudentId = ref('')
const searchResults = ref([])
const searching = ref(false)

// 好友请求相关
const showPendingDialog = ref(false)
const pendingRequests = ref([])
const pendingCount = ref(0)
const loadingPending = ref(false)

// 聊天相关
const messages = ref([])
const messageText = ref('')
const messageListRef = ref(null)
const isTyping = ref(false)
const typingTimeout = ref(null)
let ws = null

// 加载好友列表
const loadFriends = async () => {
  try {
    const res = await friendApi.list(currentUserId.value)
    if (res.code === 200) {
      friends.value = res.data
      filterFriends()
      
      // 加载未读消息数
      for (const friend of friends.value) {
        const unreadRes = await chatApi.unreadCount(currentUserId.value, friend.user_id)
        if (unreadRes.code === 200) {
          friend.unreadCount = unreadRes.data.count
        }
      }
    }
  } catch (error) {
    console.error('加载好友列表失败', error)
  }
}

// 加载待处理请求
const loadPendingRequests = async () => {
  try {
    const res = await friendApi.pending(currentUserId.value)
    if (res.code === 200) {
      pendingRequests.value = res.data
      pendingCount.value = pendingRequests.value.length
    }
  } catch (error) {
    console.error('加载好友请求失败', error)
  }
}

// 过滤好友
const filterFriends = () => {
  if (!searchKeyword.value) {
    filteredFriends.value = friends.value
  } else {
    filteredFriends.value = friends.value.filter(f =>
      f.username.includes(searchKeyword.value) ||
      f.student_id.includes(searchKeyword.value)
    )
  }
}

// 监听搜索关键词变化
watch(() => searchKeyword.value, filterFriends)

// 打开聊天
const openChat = (friend) => {
  currentFriend.value = friend
  loadChatHistory()
  markAsRead()
}

// 加载聊天历史
const loadChatHistory = async () => {
  if (!currentFriend.value) return

  try {
    const res = await chatApi.history(currentFriend.value.user_id, currentUserId.value, 50)
    if (res.code === 200) {
      messages.value = res.data
      scrollToBottom()
    }
  } catch (error) {
    console.error('加载聊天记录失败', error)
  }
}

// 发送消息
const sendMessage = async () => {
  if (!messageText.value.trim()) return
  if (!currentFriend.value) return

  const content = messageText.value.trim()
  messageText.value = ''

  try {
    // 通过WebSocket发送
    if (ws && ws.ws && ws.ws.readyState === WebSocket.OPEN) {
      ws.sendMessage(currentFriend.value.user_id, content, 'text')
      
      // 添加临时消息到列表
      messages.value.push({
        from_user_id: currentUserId.value,
        to_user_id: currentFriend.value.user_id,
        content,
        message_type: 'text',
        is_read: 0,
        created_at: new Date().toISOString()
      })
      scrollToBottom()
    } else {
      // 降级到HTTP API
      const res = await chatApi.send(currentFriend.value.user_id, content, 'text', currentUserId.value)
      if (res.code === 200) {
        messages.value.push(res.data)
        scrollToBottom()
      }
    }
  } catch (error) {
    console.error('发送失败', error)
    messageText.value = content
  }
}

// 标记为已读
const markAsRead = async () => {
  if (!currentFriend.value) return

  try {
    await chatApi.markRead(currentFriend.value.user_id, currentUserId.value)
    // 更新好友列表中的未读数
    const friend = friends.value.find(f => f.user_id === currentFriend.value.user_id)
    if (friend) {
      friend.unreadCount = 0
    }
  } catch (error) {
    console.error('标记已读失败', error)
  }
}

// 处理正在输入
const handleTyping = () => {
  if (!currentFriend.value) return

  // 发送正在输入状态
  if (ws && ws.ws && ws.ws.readyState === WebSocket.OPEN) {
    ws.sendTyping(currentFriend.value.user_id, true)
  }

  // 清除之前的定时器
  if (typingTimeout.value) {
    clearTimeout(typingTimeout.value)
  }

  // 3秒后发送停止输入状态
  typingTimeout.value = setTimeout(() => {
    if (ws && ws.ws && ws.ws.readyState === WebSocket.OPEN) {
      ws.sendTyping(currentFriend.value.user_id, false)
    }
  }, 3000)
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 搜索用户
const searchUsers = async () => {
  if (!searchStudentId.value) {
    alert('请输入学号')
    return
  }
  
  searching.value = true
  try {
    const res = await friendApi.search(searchStudentId.value, currentUserId.value)
    if (res.code === 200) {
      searchResults.value = res.data || []
    }
  } catch (error) {
    console.error('搜索错误:', error)
  } finally {
    searching.value = false
  }
}

// 发送好友请求
const sendFriendRequest = async (user) => {
  try {
    const res = await friendApi.sendRequest(user.user_id, currentUserId.value)
    if (res.code === 200) {
      alert('好友请求已发送')
      user.friendship_status = 'pending'
    }
  } catch (error) {
    alert(error.message || '发送请求失败')
  }
}

// 接受好友请求
const acceptRequest = async (user) => {
  try {
    const res = await friendApi.accept(user.user_id, currentUserId.value)
    if (res.code === 200) {
      alert('已接受好友请求')
      loadFriends()
      loadPendingRequests()
    }
  } catch (error) {
    alert('操作失败')
  }
}

// 拒绝好友请求
const rejectRequest = async (user) => {
  try {
    const res = await friendApi.reject(user.user_id, currentUserId.value)
    if (res.code === 200) {
      alert('已拒绝好友请求')
      loadPendingRequests()
    }
  } catch (error) {
    alert('操作失败')
  }
}

// 获取状态文本
const getStatusText = (status) => {
  const map = {
    pending: '待处理',
    accepted: '已是好友',
    rejected: '已拒绝',
    blocked: '已拉黑'
  }
  return map[status] || status
}

// 获取最后消息时间
const getLastTime = (timeStr) => {
  if (!timeStr) return ''
  
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', { 
    year: 'numeric',
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

// 格式化消息时间
const formatMessageTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 是否显示时间分隔符
const shouldShowTime = (index) => {
  if (index === 0) return true
  
  const currentMsg = messages.value[index]
  const prevMsg = messages.value[index - 1]
  
  const currentTime = new Date(currentMsg.created_at).getTime()
  const prevTime = new Date(prevMsg.created_at).getTime()
  
  // 超过5分钟显示时间
  return currentTime - prevTime > 300000
}

// 初始化WebSocket
const initWebSocket = () => {
  ws = new ChatWebSocket(currentUserId.value)
  
  ws.onMessage((data) => {
    if (data.type === 'message') {
      // 收到新消息
      if (data.from_user_id === currentFriend.value?.user_id || data.to_user_id === currentFriend.value?.user_id) {
        messages.value.push(data)
        scrollToBottom()
        
        // 如果是收到的消息，标记为已读
        if (data.to_user_id === currentUserId.value) {
          markAsRead()
        }
      }
      // 更新好友列表
      loadFriends()
    } else if (data.type === 'sent') {
      // 消息发送成功确认
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && !lastMsg.message_id) {
        lastMsg.message_id = data.message_id
        lastMsg.created_at = data.created_at
      }
    } else if (data.type === 'typing') {
      // 对方正在输入
      if (data.from_user_id === currentFriend.value?.user_id) {
        isTyping.value = data.is_typing
        if (data.is_typing) {
          setTimeout(() => {
            isTyping.value = false
          }, 5000)
        }
      }
    }
  })

  ws.onStatus((status) => {
    if (status === 'connected') {
      console.log('WebSocket已连接')
    } else if (status === 'disconnected') {
      console.log('WebSocket已断开')
    }
  })

  ws.connect()
}

onMounted(() => {
  loadFriends()
  loadPendingRequests()
  initWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.disconnect()
  }
  if (typingTimeout.value) {
    clearTimeout(typingTimeout.value)
  }
})
</script>

<style scoped>
.chat-page {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  background: transparent;
  display: flex;
  font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* 隐藏滚动条但保留功能 */
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 10px;
}

/* 主容器 */
.chat-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: white;
  border-radius: 8px;
  display: flex;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

/* 中间列表区 (List Column) */
.list-column {
  width: 280px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #f3f4f6;
  background: white;
  overflow: hidden;
}

/* 搜索栏 */
.search-bar-wrapper {
  padding: 16px;
  padding-top: 24px;
  flex-shrink: 0;
}

.search-bar {
  position: relative;
  width: 100%;
}

.search-input {
  width: 100%;
  background: #f3f4f6;
  border: none;
  border-radius: 6px;
  padding: 6px 32px 6px 32px;
  font-size: 14px;
  outline: none;
}

.search-input:focus {
  ring: 1px solid #3b82f6;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 10px;
  color: #9ca3af;
  font-size: 12px;
  pointer-events: none;
}

.add-btn {
  position: absolute;
  right: 8px;
  top: 6px;
  color: #9ca3af;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  transition: color 0.2s;
}

.add-btn:hover {
  color: #3b82f6;
}

/* 好友请求徽章 */
.pending-badge {
  margin: 0 16px 8px 16px;
  padding: 12px;
  background: #fef3f2;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.2s;
  flex-shrink: 0;
}

.pending-badge:hover {
  background: #fde8e8;
}

.pending-badge .badge {
  background: #ef4444;
  color: white;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
}

/* 消息列表 */
.list-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  min-height: 0;
}

.list-card {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 4px;
}

.list-card:hover {
  background: #f9fafb;
}

.list-card.active {
  background: #e5efff;
}

.avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 500;
  font-size: 16px;
}

.unread-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ef4444;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 12px;
  border: 2px solid white;
  min-width: 18px;
  text-align: center;
}

.friend-info {
  margin-left: 12px;
  overflow: hidden;
  flex: 1;
}

.friend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.friend-name {
  font-weight: 500;
  font-size: 14px;
  color: #1f2937;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.last-time {
  font-size: 10px;
  color: #9ca3af;
  white-space: nowrap;
}

.last-message {
  font-size: 12px;
  color: #6b7280;
  margin: 4px 0 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 右侧聊天/内容区 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  overflow: hidden;
}

/* 聊天头部 */
.chat-header {
  height: 64px;
  min-height: 64px;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.header-info {
  display: flex;
  align-items: center;
}

.chat-title {
  font-size: 18px;
  font-weight: 500;
  color: #1f2937;
  margin: 0;
}

.chat-subtitle {
  font-size: 12px;
  color: #9ca3af;
  margin-left: 8px;
}

/* 聊天历史记录 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 24px;
  background: #fcfcfc;
}

.messages-inner {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.time-divider {
  display: flex;
  justify-content: center;
}

.time-text {
  font-size: 11px;
  background: rgba(0, 0, 0, 0.05);
  color: #9ca3af;
  padding: 2px 8px;
  border-radius: 12px;
}

.message-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.message-left {
  justify-content: flex-start;
}

.message-right {
  justify-content: flex-end;
}

.message-content-left,
.message-content-right {
  display: flex;
  flex-direction: column;
  max-width: 60%;
}

.message-content-right {
  align-items: flex-end;
}

.sender-name {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 4px;
  margin-left: 4px;
}

.sender-name-right {
  margin-left: 0;
  margin-right: 4px;
}

.message-wrapper .avatar {
  margin-top: 4px;
  width: 36px;
  height: 36px;
  font-size: 14px;
}

.bubble {
  padding: 12px;
  font-size: 14px;
  line-height: 1.625;
  word-break: break-word;
}

.bubble-left {
  background-color: white;
  color: #374151;
  border-radius: 2px 14px 14px 14px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
}

.bubble-right {
  background-color: #0099FF;
  color: white;
  border-radius: 14px 14px 2px 14px;
  box-shadow: 0 2px 5px rgba(0, 153, 255, 0.2);
}

.message-text {
  white-space: pre-wrap;
}

.message-image img {
  max-width: 200px;
  border-radius: 8px;
}

.typing-indicator {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  color: #999;
  font-size: 12px;
  font-style: italic;
  background: white;
  border-radius: 16px;
  margin: 0 auto;
  width: fit-content;
}

/* 输入区 */
.input-area {
  height: 176px;
  min-height: 176px;
  max-height: 176px;
  border-top: 1px solid #f3f4f6;
  display: flex;
  flex-direction: column;
  background: white;
  flex-shrink: 0;
}

.input-toolbar {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  gap: 16px;
  color: #6b7280;
  font-size: 18px;
}

.toolbar-btn {
  color: #6b7280;
  font-size: inherit;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s;
  padding: 0;
}

.toolbar-btn:hover {
  color: #3b82f6;
}

.toolbar-btn-auto {
  margin-left: auto;
}

.message-textarea {
  flex: 1;
  padding: 8px 20px;
  font-size: 14px;
  color: #374151;
  border: none;
  outline: none;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
}

.message-textarea::placeholder {
  color: #bbb;
}

.send-btn-wrapper {
  display: flex;
  justify-content: flex-end;
  padding: 16px;
}

.send-btn {
  background: linear-gradient(180deg, #0099FF 0%, #007ACC 100%);
  color: white;
  border: none;
  padding: 6px 24px;
  border-radius: 6px;
  font-size: 14px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover {
  filter: brightness(1.1);
}

.send-btn:active {
  transform: scale(0.95);
}

/* 空状态 */
.empty-state, .empty-chat, .empty-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: #999;
  text-align: center;
  height: 100%;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.2;
}

/* 模态框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  background: white;
  border-radius: 12px;
  width: 600px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
}

.modal-close {
  background: none;
  border: none;
  font-size: 24px;
  color: #9ca3af;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.modal-close:hover {
  background: #f3f4f6;
  color: #1f2937;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.search-input-group {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.modal-input {
  flex: 1;
  padding: 10px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
}

.modal-input:focus {
  border-color: #3b82f6;
}

.search-submit-btn {
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.2s;
}

.search-submit-btn:hover {
  background: #2563eb;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #9ca3af;
}

.search-results,
.pending-requests {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-result-item,
.pending-request-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  gap: 12px;
}

.result-info {
  flex: 1;
}

.result-name {
  font-weight: 500;
  font-size: 14px;
  color: #1f2937;
  margin-bottom: 4px;
}

.result-desc {
  font-size: 12px;
  color: #6b7280;
}

.result-time {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
}

.add-friend-btn-small {
  padding: 6px 16px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.add-friend-btn-small:hover {
  background: #2563eb;
}

.status-tag {
  font-size: 12px;
  color: #6b7280;
  padding: 4px 12px;
  background: #e5e7eb;
  border-radius: 4px;
}

.request-actions {
  display: flex;
  gap: 8px;
}

.accept-btn,
.reject-btn {
  padding: 6px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.accept-btn {
  background: #10b981;
  color: white;
}

.accept-btn:hover {
  background: #059669;
}

.reject-btn {
  background: #f3f4f6;
  color: #6b7280;
}

.reject-btn:hover {
  background: #e5e7eb;
  color: #1f2937;
}
</style>
