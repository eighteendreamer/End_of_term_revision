/**
 * 禁用开发者工具
 * 防止用户通过F12、右键检查等方式打开控制台
 */

// 禁用右键菜单
export function disableContextMenu() {
  document.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    return false;
  }, false);
  
  console.log('✅ 右键菜单已禁用');
}

// 禁用F12和其他开发者工具快捷键
export function disableDevToolsShortcuts() {
  document.addEventListener('keydown', (e) => {
    // F12
    if (e.key === 'F12') {
      e.preventDefault();
      return false;
    }
    
    // Ctrl+Shift+I (Chrome DevTools)
    if (e.ctrlKey && e.shiftKey && e.key === 'I') {
      e.preventDefault();
      return false;
    }
    
    // Ctrl+Shift+J (Chrome Console)
    if (e.ctrlKey && e.shiftKey && e.key === 'J') {
      e.preventDefault();
      return false;
    }
    
    // Ctrl+Shift+C (Chrome Inspect Element)
    if (e.ctrlKey && e.shiftKey && e.key === 'C') {
      e.preventDefault();
      return false;
    }
    
    // Ctrl+U (View Source)
    if (e.ctrlKey && e.key === 'u') {
      e.preventDefault();
      return false;
    }
    
    // Ctrl+S (Save Page)
    if (e.ctrlKey && e.key === 's') {
      e.preventDefault();
      return false;
    }
    
    // Cmd+Option+I (Mac DevTools)
    if (e.metaKey && e.altKey && e.key === 'i') {
      e.preventDefault();
      return false;
    }
    
    // Cmd+Option+J (Mac Console)
    if (e.metaKey && e.altKey && e.key === 'j') {
      e.preventDefault();
      return false;
    }
    
    // Cmd+Option+C (Mac Inspect)
    if (e.metaKey && e.altKey && e.key === 'c') {
      e.preventDefault();
      return false;
    }
  }, false);
  
  console.log('✅ 开发者工具快捷键已禁用');
}

// 检测开发者工具是否打开
export function startDevToolsDetection() {
  const threshold = 160;
  let devtoolsOpen = false;
  
  const checkDevTools = () => {
    const widthThreshold = window.outerWidth - window.innerWidth > threshold;
    const heightThreshold = window.outerHeight - window.innerHeight > threshold;
    
    if (widthThreshold || heightThreshold) {
      if (!devtoolsOpen) {
        devtoolsOpen = true;
        handleDevToolsOpen();
      }
    } else {
      devtoolsOpen = false;
    }
  };
  
  // 定期检测
  setInterval(checkDevTools, 1000);
  
  // 使用debugger检测
  const detectDebugger = () => {
    const start = new Date();
    debugger;
    const end = new Date();
    if (end - start > 100) {
      handleDevToolsOpen();
    }
  };
  
  // 定期触发debugger检测
  setInterval(detectDebugger, 1000);
  
  console.log('✅ 开发者工具检测已启动');
}

// 当检测到开发者工具打开时的处理
function handleDevToolsOpen() {
  // 方案1: 显示警告
  alert('⚠️ 检测到开发者工具！\n为了系统安全，请关闭开发者工具。');
  
  // 方案2: 重定向到警告页面
  // window.location.href = '/warning';
  
  // 方案3: 清空页面内容
  // document.body.innerHTML = '<div style="text-align:center;margin-top:100px;"><h1>⚠️ 检测到非法操作</h1><p>页面已被禁用，请关闭开发者工具后刷新页面</p></div>';
  
  // 方案4: 关闭当前窗口（仅在某些浏览器有效）
  // window.close();
}

// 禁用控制台输出
export function disableConsole() {
  // 保存原始console方法
  const noop = () => {};
  
  // 只在生产环境重写console方法
  const originalConsole = window.console;
  
  window.console = {
    ...originalConsole,
    log: noop,
    warn: noop,
    error: noop,
    info: noop,
    debug: noop,
    trace: noop,
    dir: noop,
    dirxml: noop,
    group: noop,
    groupEnd: noop,
    time: noop,
    timeEnd: noop,
    assert: noop,
    profile: noop,
  };
  
  console.log('✅ 控制台输出已禁用');
}

// 防止通过iframe嵌入
export function preventIframeEmbedding() {
  if (window.top !== window.self) {
    // 如果页面被嵌入iframe，跳转到顶层
    window.top.location = window.self.location;
  }
  console.log('✅ iframe嵌入防护已启用');
}

// 禁用文本选择和复制
export function disableTextSelection() {
  document.addEventListener('selectstart', (e) => {
    e.preventDefault();
    return false;
  }, false);
  
  document.addEventListener('copy', (e) => {
    e.preventDefault();
    return false;
  }, false);
  
  // CSS方式
  const style = document.createElement('style');
  style.innerHTML = `
    * {
      -webkit-user-select: none !important;
      -moz-user-select: none !important;
      -ms-user-select: none !important;
      user-select: none !important;
    }
  `;
  document.head.appendChild(style);
  
  console.log('✅ 文本选择已禁用');
}

// 禁用拖拽
export function disableDragAndDrop() {
  document.addEventListener('dragstart', (e) => {
    e.preventDefault();
    return false;
  }, false);
  
  console.log('✅ 拖拽已禁用');
}

// 清除调试信息
export function clearDebugInfo() {
  // 清除所有console历史
  if (window.console && window.console.clear) {
    window.console.clear();
  }
  
  // 清除localStorage中的调试信息
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.includes('debug') || key.includes('dev'))) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
  } catch (e) {
    // localStorage可能被禁用
  }
  
  console.log('✅ 调试信息已清除');
}

// 初始化所有安全措施
export function initSecurityMeasures(options = {}) {
  const {
    disableRightClick = true,
    disableShortcuts = true,
    detectDevTools = true,
    disableConsole = false, // 默认不禁用，方便看到初始化日志
    preventIframe = true,
    disableSelection = false,
    disableDrag = false,
    clearDebug = true,
  } = options;
  
  console.log('🔒 正在初始化前端安全措施...');
  
  // 确保DOM加载完成后再执行
  const init = () => {
    if (disableRightClick) {
      disableContextMenu();
    }
    
    if (disableShortcuts) {
      disableDevToolsShortcuts();
    }
    
    if (detectDevTools) {
      startDevToolsDetection();
    }
    
    if (preventIframe) {
      preventIframeEmbedding();
    }
    
    if (disableSelection) {
      disableTextSelection();
    }
    
    if (disableDrag) {
      disableDragAndDrop();
    }
    
    if (clearDebug) {
      clearDebugInfo();
    }
    
    // 最后禁用console（这样前面的日志还能看到）
    if (disableConsole) {
      setTimeout(() => {
        disableConsole();
      }, 1000);
    }
    
    console.log('🔒 前端安全措施初始化完成！');
  };
  
  // 如果DOM已加载，立即执行
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}

// 默认导出
export default {
  disableContextMenu,
  disableDevToolsShortcuts,
  startDevToolsDetection,
  disableConsole,
  preventIframeEmbedding,
  disableTextSelection,
  disableDragAndDrop,
  clearDebugInfo,
  initSecurityMeasures,
};
