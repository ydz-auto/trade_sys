const DEFAULT_CONFIG = {
    wsUrl: '',
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
    enableNotifications: true,
    enableSound: true,
    autoReconnect: true,
    isConfigured: false
};

const elements = {
    wsUrl: document.getElementById('wsUrl'),
    reconnectInterval: document.getElementById('reconnectInterval'),
    maxReconnectAttempts: document.getElementById('maxReconnectAttempts'),
    enableNotifications: document.getElementById('enableNotifications'),
    enableSound: document.getElementById('enableSound'),
    autoReconnect: document.getElementById('autoReconnect'),
    save: document.getElementById('save'),
    reset: document.getElementById('reset'),
    status: document.getElementById('status'),
    connectionStatus: document.getElementById('connectionStatus'),
    testConnection: document.getElementById('testConnection')
};

function loadConfig() {
    chrome.storage.local.get(DEFAULT_CONFIG, (config) => {
        elements.wsUrl.value = config.wsUrl || '';
        elements.reconnectInterval.value = config.reconnectInterval;
        elements.maxReconnectAttempts.value = config.maxReconnectAttempts;
        elements.enableNotifications.checked = config.enableNotifications;
        elements.enableSound.checked = config.enableSound;
        elements.autoReconnect.checked = config.autoReconnect;
        
        updateConnectionStatus(config.isConfigured ? false : null, config.isConfigured);
    });
}

function saveConfig() {
    const wsUrl = elements.wsUrl.value.trim();
    
    if (!wsUrl) {
        showStatus('请输入 WebSocket 服务器地址', 'error');
        return;
    }
    
    const config = {
        wsUrl: wsUrl,
        reconnectInterval: parseInt(elements.reconnectInterval.value) || DEFAULT_CONFIG.reconnectInterval,
        maxReconnectAttempts: parseInt(elements.maxReconnectAttempts.value) || DEFAULT_CONFIG.maxReconnectAttempts,
        enableNotifications: elements.enableNotifications.checked,
        enableSound: elements.enableSound.checked,
        autoReconnect: elements.autoReconnect.checked,
        isConfigured: true
    };
    
    chrome.storage.local.set(config, () => {
        showStatus('设置已保存！正在连接...', 'success');
        chrome.runtime.sendMessage({ type: 'config_updated', config: config });
    });
}

function resetConfig() {
    chrome.storage.local.set(DEFAULT_CONFIG, () => {
        loadConfig();
        showStatus('已恢复默认设置', 'success');
        chrome.runtime.sendMessage({ type: 'config_updated', config: DEFAULT_CONFIG });
    });
}

function showStatus(message, type) {
    elements.status.textContent = message;
    elements.status.className = 'status ' + type;
    
    setTimeout(() => {
        elements.status.className = 'status';
    }, 3000);
}

function updateConnectionStatus(connected, isConfigured) {
    const statusEl = elements.connectionStatus;
    const statusText = statusEl.querySelector('.status-text');
    
    if (!isConfigured) {
        statusEl.className = 'connection-status disconnected';
        statusText.textContent = '未配置';
    } else if (connected) {
        statusEl.className = 'connection-status connected';
        statusText.textContent = '已连接';
    } else {
        statusEl.className = 'connection-status disconnected';
        statusText.textContent = '未连接';
    }
}

async function testConnection() {
    const wsUrl = elements.wsUrl.value.trim();
    
    if (!wsUrl) {
        showStatus('请先输入 WebSocket 服务器地址', 'error');
        return;
    }
    
    elements.testConnection.disabled = true;
    elements.testConnection.textContent = '测试中...';
    
    try {
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            updateConnectionStatus(true, true);
            showStatus('连接成功！', 'success');
            ws.close();
            elements.testConnection.disabled = false;
            elements.testConnection.textContent = '测试连接';
        };
        
        ws.onerror = () => {
            updateConnectionStatus(false, true);
            showStatus('连接失败，请检查服务器地址', 'error');
            elements.testConnection.disabled = false;
            elements.testConnection.textContent = '测试连接';
        };
        
        setTimeout(() => {
            if (ws.readyState !== WebSocket.OPEN) {
                ws.close();
                updateConnectionStatus(false, true);
                showStatus('连接超时', 'error');
                elements.testConnection.disabled = false;
                elements.testConnection.textContent = '测试连接';
            }
        }, 5000);
        
    } catch (error) {
        updateConnectionStatus(false, true);
        showStatus('连接失败: ' + error.message, 'error');
        elements.testConnection.disabled = false;
        elements.testConnection.textContent = '测试连接';
    }
}

function checkConnectionStatus() {
    chrome.runtime.sendMessage({ type: 'get_connection_status' }, (response) => {
        if (response) {
            updateConnectionStatus(response.connected, response.isConfigured);
        }
    });
}

elements.save.addEventListener('click', saveConfig);
elements.reset.addEventListener('click', resetConfig);
elements.testConnection.addEventListener('click', testConnection);

loadConfig();
checkConnectionStatus();

setInterval(checkConnectionStatus, 5000);
