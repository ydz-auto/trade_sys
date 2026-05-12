/**
 * Twitter Push Notification Extension - Background Service Worker
 * 
 * 核心功能：
 * 1. 监听 Twitter 浏览器通知
 * 2. 解析通知内容
 * 3. 通过 WebSocket 发送到后端
 */

// 配置
const CONFIG = {
    wsUrl: 'ws://localhost:8765/twitter-push',
    reconnectInterval: 3000,
    maxReconnectAttempts: 10
};

// 状态
let ws = null;
let reconnectAttempts = 0;
let messageQueue = [];

// 初始化
function init() {
    console.log('[TradeAgent] Extension initialized');
    connectWebSocket();
    setupNotificationListener();
}

// WebSocket 连接
function connectWebSocket() {
    try {
        ws = new WebSocket(CONFIG.wsUrl);
        
        ws.onopen = () => {
            console.log('[TradeAgent] WebSocket connected');
            reconnectAttempts = 0;
            flushMessageQueue();
        };
        
        ws.onclose = () => {
            console.log('[TradeAgent] WebSocket disconnected');
            scheduleReconnect();
        };
        
        ws.onerror = (error) => {
            console.error('[TradeAgent] WebSocket error:', error);
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleServerMessage(data);
            } catch (e) {
                console.error('[TradeAgent] Failed to parse message:', e);
            }
        };
    } catch (error) {
        console.error('[TradeAgent] Failed to create WebSocket:', error);
        scheduleReconnect();
    }
}

// 重连逻辑
function scheduleReconnect() {
    if (reconnectAttempts >= CONFIG.maxReconnectAttempts) {
        console.error('[TradeAgent] Max reconnect attempts reached');
        return;
    }
    
    reconnectAttempts++;
    const delay = CONFIG.reconnectInterval * Math.pow(1.5, reconnectAttempts - 1);
    
    console.log(`[TradeAgent] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
    setTimeout(connectWebSocket, delay);
}

// 发送消息
function sendToServer(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        return true;
    } else {
        messageQueue.push(message);
        return false;
    }
}

// 发送队列中的消息
function flushMessageQueue() {
    while (messageQueue.length > 0 && ws && ws.readyState === WebSocket.OPEN) {
        const message = messageQueue.shift();
        ws.send(JSON.stringify(message));
    }
}

// 处理服务器消息
function handleServerMessage(data) {
    if (data.type === 'ping') {
        sendToServer({ type: 'pong', timestamp: Date.now() });
    } else if (data.type === 'config_update') {
        Object.assign(CONFIG, data.config);
        console.log('[TradeAgent] Config updated:', CONFIG);
    }
}

// 设置通知监听
function setupNotificationListener() {
    // 监听通知被点击
    chrome.notifications.onClicked.addListener((notificationId) => {
        console.log('[TradeAgent] Notification clicked:', notificationId);
        handleNotificationClick(notificationId);
    });
    
    // 监听通知被关闭
    chrome.notifications.onClosed.addListener((notificationId, byUser) => {
        console.log('[TradeAgent] Notification closed:', notificationId, byUser);
    });
}

// 处理通知点击
async function handleNotificationClick(notificationId) {
    try {
        // 获取通知数据
        const notification = await chrome.notifications.getAll();
        console.log('[TradeAgent] All notifications:', notification);
        
        // 打开 Twitter 标签页
        chrome.tabs.create({ url: `https://twitter.com/i/notifications` });
    } catch (error) {
        console.error('[TradeAgent] Failed to handle notification click:', error);
    }
}

// 转发推文到服务器（由 content script 调用）
function forwardTweet(tweetData) {
    const message = {
        type: 'tweet',
        source: 'twitter_push',
        timestamp: Date.now(),
        data: {
            id: tweetData.id,
            author: tweetData.author,
            authorId: tweetData.authorId,
            content: tweetData.content,
            url: tweetData.url,
            likes: tweetData.likes,
            retweets: tweetData.retweets,
            hashtags: tweetData.hashtags,
            mentionedSymbols: tweetData.mentionedSymbols
        }
    };
    
    sendToServer(message);
    console.log('[TradeAgent] Tweet forwarded:', message.data.author);
}

// 监听来自 content script 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'tweet') {
        forwardTweet(message.data);
        sendResponse({ success: true });
    }
    return true;
});

// 初始化
init();

// 导出（用于调试）
if (typeof globalThis !== 'undefined') {
    globalThis.TradeAgentExtension = {
        forwardTweet,
        sendToServer,
        CONFIG
    };
}
