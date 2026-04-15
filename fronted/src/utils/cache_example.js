/**
 * 前端缓存管理模块（示例实现）
 * 使用 IndexedDB 实现本地数据缓存和增量同步
 * 
 * 安装依赖：npm install localforage
 */

import localforage from 'localforage'
import axios from 'axios'

// 配置 localforage
const questionCache = localforage.createInstance({
  name: 'QuestionCache',
  storeName: 'questions',
  description: '题目数据缓存'
})

const syncMetaCache = localforage.createInstance({
  name: 'SyncMeta',
  storeName: 'sync_meta',
  description: '同步元数据'
})

/**
 * 缓存管理类
 */
class CacheManager {
  /**
   * 获取题目列表（优先从缓存读取）
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID
   * @param {boolean} forceSync - 是否强制同步
   * @returns {Promise<Array>} 题目列表
   */
  async getQuestions(userId, subjectId, forceSync = false) {
    const cacheKey = `questions_${userId}_${subjectId}`
    
    // 1. 尝试从缓存读取
    if (!forceSync) {
      const cached = await questionCache.getItem(cacheKey)
      if (cached && cached.length > 0) {
        console.log('[缓存] 从本地缓存读取题目', cached.length, '条')
        
        // 后台检查是否有更新
        this.checkAndSync(userId, subjectId).catch(err => {
          console.warn('[缓存] 后台同步失败', err)
        })
        
        return cached
      }
    }
    
    // 2. 缓存不存在或强制同步，执行完整同步
    console.log('[缓存] 执行完整同步')
    return await this.fullSync(userId, subjectId)
  }

  /**
   * 完整同步（首次加载）
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID
   * @returns {Promise<Array>} 题目列表
   */
  async fullSync(userId, subjectId) {
    try {
      const response = await axios.get('/api/sync/questions', {
        params: { user_id: userId, subject_id: subjectId }
      })
      
      const { server_time, updated } = response.data
      
      // 保存到缓存
      const cacheKey = `questions_${userId}_${subjectId}`
      await questionCache.setItem(cacheKey, updated)
      
      // 保存同步时间
      await this.saveSyncTime(userId, subjectId, server_time)
      
      console.log('[缓存] 完整同步完成', updated.length, '条题目')
      return updated
    } catch (error) {
      console.error('[缓存] 完整同步失败', error)
      throw error
    }
  }

  /**
   * 增量同步
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID
   * @returns {Promise<Object>} 同步结果
   */
  async incrementalSync(userId, subjectId) {
    try {
      // 获取上次同步时间
      const lastSync = await this.getLastSyncTime(userId, subjectId)
      
      if (!lastSync) {
        console.log('[缓存] 无同步记录，执行完整同步')
        return await this.fullSync(userId, subjectId)
      }
      
      // 调用增量同步接口
      const response = await axios.get('/api/sync/questions', {
        params: {
          user_id: userId,
          subject_id: subjectId,
          since: lastSync
        }
      })
      
      const { server_time, updated, deleted, total_updated, total_deleted } = response.data
      
      if (total_updated === 0 && total_deleted === 0) {
        console.log('[缓存] 无新数据需要同步')
        return { updated: 0, deleted: 0 }
      }
      
      // 更新本地缓存
      await this.applyIncrementalChanges(userId, subjectId, updated, deleted)
      
      // 更新同步时间
      await this.saveSyncTime(userId, subjectId, server_time)
      
      console.log('[缓存] 增量同步完成', {
        updated: total_updated,
        deleted: total_deleted
      })
      
      return { updated: total_updated, deleted: total_deleted }
    } catch (error) {
      console.error('[缓存] 增量同步失败', error)
      throw error
    }
  }

  /**
   * 应用增量变更到本地缓存
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID
   * @param {Array} updated - 更新的题目
   * @param {Array} deleted - 删除的题目ID
   */
  async applyIncrementalChanges(userId, subjectId, updated, deleted) {
    const cacheKey = `questions_${userId}_${subjectId}`
    
    // 读取现有缓存
    let cached = await questionCache.getItem(cacheKey) || []
    
    // 创建ID到索引的映射
    const idMap = new Map()
    cached.forEach((q, index) => {
      idMap.set(q.id, index)
    })
    
    // 应用更新
    updated.forEach(updatedQuestion => {
      const index = idMap.get(updatedQuestion.id)
      if (index !== undefined) {
        // 更新现有题目
        cached[index] = updatedQuestion
      } else {
        // 新增题目
        cached.push(updatedQuestion)
      }
    })
    
    // 应用删除
    if (deleted.length > 0) {
      const deletedSet = new Set(deleted)
      cached = cached.filter(q => !deletedSet.has(q.id))
    }
    
    // 保存更新后的缓存
    await questionCache.setItem(cacheKey, cached)
  }

  /**
   * 检查并同步（后台静默同步）
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID
   */
  async checkAndSync(userId, subjectId) {
    try {
      const lastSync = await this.getLastSyncTime(userId, subjectId)
      
      // 检查是否有更新
      const response = await axios.get('/api/sync/questions/check', {
        params: {
          user_id: userId,
          subject_id: subjectId,
          since: lastSync
        }
      })
      
      const { has_updates } = response.data
      
      if (has_updates) {
        console.log('[缓存] 检测到新数据，开始后台同步')
        await this.incrementalSync(userId, subjectId)
      }
    } catch (error) {
      console.warn('[缓存] 后台检查失败', error)
    }
  }

  /**
   * 保存同步时间
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID
   * @param {string} syncTime - 同步时间
   */
  async saveSyncTime(userId, subjectId, syncTime) {
    const key = `sync_time_${userId}_${subjectId}`
    await syncMetaCache.setItem(key, syncTime)
  }

  /**
   * 获取上次同步时间
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID
   * @returns {Promise<string|null>} 同步时间
   */
  async getLastSyncTime(userId, subjectId) {
    const key = `sync_time_${userId}_${subjectId}`
    return await syncMetaCache.getItem(key)
  }

  /**
   * 清除缓存
   * @param {number} userId - 用户ID
   * @param {number} subjectId - 科目ID（可选，不传则清除所有）
   */
  async clearCache(userId, subjectId = null) {
    if (subjectId) {
      const cacheKey = `questions_${userId}_${subjectId}`
      const syncKey = `sync_time_${userId}_${subjectId}`
      await questionCache.removeItem(cacheKey)
      await syncMetaCache.removeItem(syncKey)
      console.log('[缓存] 已清除科目缓存', subjectId)
    } else {
      await questionCache.clear()
      await syncMetaCache.clear()
      console.log('[缓存] 已清除所有缓存')
    }
  }

  /**
   * 获取缓存统计信息
   * @returns {Promise<Object>} 统计信息
   */
  async getCacheStats() {
    const keys = await questionCache.keys()
    const stats = {
      totalSubjects: keys.length,
      subjects: []
    }
    
    for (const key of keys) {
      const data = await questionCache.getItem(key)
      const [, userId, subjectId] = key.split('_')
      const syncTime = await this.getLastSyncTime(parseInt(userId), parseInt(subjectId))
      
      stats.subjects.push({
        userId: parseInt(userId),
        subjectId: parseInt(subjectId),
        questionCount: data ? data.length : 0,
        lastSync: syncTime
      })
    }
    
    return stats
  }
}

// 导出单例
export const cacheManager = new CacheManager()

// 导出工具函数
export default {
  /**
   * 获取题目列表（带缓存）
   */
  async getQuestions(userId, subjectId, forceSync = false) {
    return await cacheManager.getQuestions(userId, subjectId, forceSync)
  },

  /**
   * 手动触发同步
   */
  async sync(userId, subjectId) {
    return await cacheManager.incrementalSync(userId, subjectId)
  },

  /**
   * 清除缓存
   */
  async clearCache(userId, subjectId = null) {
    return await cacheManager.clearCache(userId, subjectId)
  },

  /**
   * 获取缓存统计
   */
  async getStats() {
    return await cacheManager.getCacheStats()
  }
}

/**
 * 使用示例：
 * 
 * 1. 在组件中使用缓存：
 * 
 * import cache from '@/utils/cache'
 * 
 * // 获取题目（自动使用缓存）
 * const questions = await cache.getQuestions(userId, subjectId)
 * 
 * // 强制刷新
 * const questions = await cache.getQuestions(userId, subjectId, true)
 * 
 * // 手动同步
 * await cache.sync(userId, subjectId)
 * 
 * // 清除缓存
 * await cache.clearCache(userId, subjectId)
 * 
 * 
 * 2. 在设置页面显示缓存信息：
 * 
 * const stats = await cache.getStats()
 * console.log('缓存统计', stats)
 * 
 * 
 * 3. 定期后台同步（可选）：
 * 
 * // 每5分钟检查一次更新
 * setInterval(async () => {
 *   await cache.sync(userId, subjectId)
 * }, 5 * 60 * 1000)
 */
