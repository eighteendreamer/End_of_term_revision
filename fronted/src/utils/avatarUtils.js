/**
 * 生成基于用户名的头像颜色
 * @param {string} username - 用户名
 * @returns {string} 颜色值
 */
export function getAvatarColor(username) {
  if (!username) return '#4ECDC4';
  
  const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2'];
  const index = username.charCodeAt(0) % colors.length;
  return colors[index];
}