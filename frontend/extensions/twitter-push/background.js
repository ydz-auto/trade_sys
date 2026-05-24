/**
 * Twitter Push Notification Extension - Background Service Worker
 * 
 * 核心功能：
 * 1. 监听 Twitter 浏览器通知
 * 2. 解析通知内容
 * 3. 通过 WebSocket 发送到后端
 */

const DEFAULT_CONFIG = {
    wsUrl: '',
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
    enableNotifications: true,
    enableSound: true,
    autoReconnect: true,
    isConfigured: false
};

let CONFIG = { ...DEFAULT_CONFIG };
let ws = null;
let reconnectAttempts = 0;
let messageQueue = [];
let reconnectTimer = null;

async function loadConfig() {
    return new Promise((resolve) => {
        chrome.storage.local.get(DEFAULT_CONFIG, (config) => {
            CONFIG = { ...DEFAULT_CONFIG, ...config };
            console.log('[TradeAgent] Config loaded:', CONFIG);
            resolve(CONFIG);
        });
    });
}

function init() {
    console.log('[TradeAgent] Extension initialized');
    loadConfig().then(() => {
        setupNotificationListener();
        setupMessageListener();
        
        if (CONFIG.isConfigured && CONFIG.wsUrl) {
            console.log('[TradeAgent] Auto-connecting to:', CONFIG.wsUrl);
            connectWebSocket();
        } else {
            console.log('[TradeAgent] Not configured yet, waiting for user setup');
        }
    });
}

function connectWebSocket() {
    if (!CONFIG.wsUrl) {
        console.warn('[TradeAgent] No WebSocket URL configured');
        return;
    }
    
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
        console.log('[TradeAgent] WebSocket already connected or connecting');
        return;
    }
    
    try {
        console.log('[TradeAgent] Connecting to:', CONFIG.wsUrl);
        ws = new WebSocket(CONFIG.wsUrl);
        
        ws.onopen = () => {
            console.log('[TradeAgent] WebSocket connected');
            reconnectAttempts = 0;
            flushMessageQueue();
        };
        
        ws.onclose = () => {
            console.log('[TradeAgent] WebSocket disconnected');
            ws = null;
            if (CONFIG.autoReconnect && CONFIG.isConfigured) {
                scheduleReconnect();
            }
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
        if (CONFIG.autoReconnect && CONFIG.isConfigured) {
            scheduleReconnect();
        }
    }
}

function disconnectWebSocket() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    
    if (ws) {
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
        ws = null;
    }
    
    console.log('[TradeAgent] WebSocket disconnected');
}

function scheduleReconnect() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
    }
    
    if (!CONFIG.isConfigured) {
        console.log('[TradeAgent] Not configured, skip reconnect');
        return;
    }
    
    if (reconnectAttempts >= CONFIG.maxReconnectAttempts) {
        console.error('[TradeAgent] Max reconnect attempts reached');
        return;
    }
    
    reconnectAttempts++;
    const delay = CONFIG.reconnectInterval * Math.pow(1.5, reconnectAttempts - 1);
    
    console.log(`[TradeAgent] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
    
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket();
    }, delay);
}

function sendToServer(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        return true;
    } else {
        messageQueue.push(message);
        console.log('[TradeAgent] Message queued (WebSocket not ready)');
        return false;
    }
}

function flushMessageQueue() {
    while (messageQueue.length > 0 && ws && ws.readyState === WebSocket.OPEN) {
        const message = messageQueue.shift();
        ws.send(JSON.stringify(message));
    }
}

function handleServerMessage(data) {
    if (data.type === 'ping') {
        sendToServer({ type: 'pong', timestamp: Date.now() });
    } else if (data.type === 'config_update') {
        Object.assign(CONFIG, data.config);
        console.log('[TradeAgent] Config updated from server:', CONFIG);
    }
}

function setupNotificationListener() {
    chrome.notifications.onClicked.addListener((notificationId) => {
        console.log('[TradeAgent] Notification clicked:', notificationId);
        handleNotificationClick(notificationId);
    });
    
    chrome.notifications.onClosed.addListener((notificationId, byUser) => {
        console.log('[TradeAgent] Notification closed:', notificationId, byUser);
    });
}

function setupMessageListener() {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'tweet') {
            forwardTweet(message.data);
            sendResponse({ success: true });
        } else if (message.type === 'config_updated') {
            handleConfigUpdate(message.config);
            sendResponse({ success: true });
        } else if (message.type === 'get_connection_status') {
            sendResponse({
                connected: ws && ws.readyState === WebSocket.OPEN,
                wsUrl: CONFIG.wsUrl,
                isConfigured: CONFIG.isConfigured
            });
        } else if (message.type === 'reconnect') {
            disconnectWebSocket();
            reconnectAttempts = 0;
            if (CONFIG.wsUrl) {
                connectWebSocket();
            }
            sendResponse({ success: true });
        } else if (message.type === 'disconnect') {
            disconnectWebSocket();
            sendResponse({ success: true });
        }
        return true;
    });
}

function handleConfigUpdate(newConfig) {
    console.log('[TradeAgent] Config update received:', newConfig);
    
    const oldWsUrl = CONFIG.wsUrl;
    const wasConfigured = CONFIG.isConfigured;
    CONFIG = { ...CONFIG, ...newConfig };
    
    if (newConfig.wsUrl && newConfig.wsUrl !== oldWsUrl && CONFIG.isConfigured) {
        console.log('[TradeAgent] WebSocket URL changed, reconnecting...');
        disconnectWebSocket();
        reconnectAttempts = 0;
        connectWebSocket();
    } else if (!wasConfigured && CONFIG.isConfigured && CONFIG.wsUrl) {
        console.log('[TradeAgent] First time configured, connecting...');
        connectWebSocket();
    }
}

async function handleNotificationClick(notificationId) {
    try {
        const notification = await chrome.notifications.getAll();
        console.log('[TradeAgent] All notifications:', notification);
        chrome.tabs.create({ url: 'https://twitter.com/i/notifications' });
    } catch (error) {
        console.error('[TradeAgent] Failed to handle notification click:', error);
    }
}

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

init();

if (typeof globalThis !== 'undefined') {
    globalThis.TradeAgentExtension = {
        forwardTweet,
        sendToServer,
        connectWebSocket,
        disconnectWebSocket,
        CONFIG,
        getConnectionStatus: () => ({
            connected: ws && ws.readyState === WebSocket.OPEN,
            wsUrl: CONFIG.wsUrl,
            isConfigured: CONFIG.isConfigured
        })
    };
}
