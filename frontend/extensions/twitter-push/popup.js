const elements = {
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    serverInfo: document.getElementById('serverInfo'),
    reconnectBtn: document.getElementById('reconnectBtn'),
    settingsBtn: document.getElementById('settingsBtn'),
    queuedCount: document.getElementById('queuedCount'),
    reconnectCount: document.getElementById('reconnectCount')
};

function updateStatus(connected, wsUrl, isConfigured) {
    if (!isConfigured) {
        elements.statusDot.className = 'status-dot disconnected';
        elements.statusText.className = 'status-value disconnected';
        elements.statusText.textContent = '未配置';
        elements.serverInfo.textContent = '请先配置服务器地址';
        elements.reconnectBtn.textContent = '去配置';
    } else if (connected) {
        elements.statusDot.className = 'status-dot connected';
        elements.statusText.className = 'status-value connected';
        elements.statusText.textContent = '已连接';
        elements.serverInfo.textContent = '服务器: ' + wsUrl;
        elements.reconnectBtn.textContent = '重新连接';
    } else {
        elements.statusDot.className = 'status-dot disconnected';
        elements.statusText.className = 'status-value disconnected';
        elements.statusText.textContent = '未连接';
        elements.serverInfo.textContent = '服务器: ' + wsUrl;
        elements.reconnectBtn.textContent = '连接';
    }
}

function refreshStatus() {
    chrome.runtime.sendMessage({ type: 'get_connection_status' }, (response) => {
        if (chrome.runtime.lastError) {
            updateStatus(false, null, false);
            console.error('Error:', chrome.runtime.lastError);
            return;
        }
        
        if (response) {
            updateStatus(response.connected, response.wsUrl, response.isConfigured);
        }
    });
}

elements.reconnectBtn.addEventListener('click', () => {
    chrome.runtime.sendMessage({ type: 'get_connection_status' }, (response) => {
        if (!response || !response.isConfigured) {
            chrome.runtime.openOptionsPage();
            return;
        }
        
        elements.reconnectBtn.disabled = true;
        elements.reconnectBtn.textContent = '连接中...';
        
        chrome.runtime.sendMessage({ type: 'reconnect' }, () => {
            setTimeout(() => {
                elements.reconnectBtn.disabled = false;
                refreshStatus();
            }, 1000);
        });
    });
});

elements.settingsBtn.addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
});

refreshStatus();

setInterval(refreshStatus, 2000);
