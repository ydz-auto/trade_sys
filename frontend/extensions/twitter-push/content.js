/**
 * Twitter Push Notification Extension - Content Script
 * 
 * 核心功能：
 * 1. 监听 Twitter 页面上的推文
 * 2. 解析推文内容
 * 3. 提取币种信息
 * 4. 转发到 background script
 */

// 币种关键词列表
const CRYPTO_KEYWORDS = [
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX', 'LINK',
    'MATIC', 'UNI', 'ATOM', 'LTC', 'BCH', 'FIL', 'NEAR', 'APT', 'ARB', 'OP',
    'SUI', 'SEI', 'TIA', 'INJ', 'ATOM', 'FTM', 'ALGO', 'XLM', 'VET', 'ICP',
    'DOGE', 'SHIB', 'PEPE', 'WIF', 'BONK', 'SAND', 'MANA', 'AXS', 'ENJ'
];

// P0 账号列表（可配置）
const P0_ACCOUNTS = [
    'elonmusk',
    'cz_binance',
    'VitalikButerin',
    'saylor',
    'BarrySilbert',
    'binance',
    'okx',
    'coinbase',
    'EricBalchunas',
    'WatcherGuru',
    'Phyrex_Ni'
];

// 状态
let lastProcessedTweetId = null;
let observer = null;

// 初始化
function init() {
    console.log('[TradeAgent] Content script initialized');
    
    // 检查是否在 Twitter 页面
    if (!isTwitterPage()) {
        console.log('[TradeAgent] Not on Twitter page, skipping');
        return;
    }
    
    // 启动监控
    startMonitoring();
    
    // 处理现有推文
    processExistingTweets();
}

// 检查是否在 Twitter 页面
function isTwitterPage() {
    const url = window.location.href;
    return url.includes('twitter.com') || url.includes('x.com');
}

// 启动监控
function startMonitoring() {
    // 使用 MutationObserver 监控新推文
    observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    const tweet = findTweetElement(node);
                    if (tweet) {
                        processTweet(tweet);
                    }
                }
            }
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    console.log('[TradeAgent] Monitoring started');
}

// 查找推文元素
function findTweetElement(node) {
    // Twitter 推文容器选择器
    const selectors = [
        '[data-testid="tweet"]',
        'article[role="article"]',
        '.tweet',
        '[data-item-id]'
    ];
    
    for (const selector of selectors) {
        const element = node.matches?.(selector) ? node : node.querySelector?.(selector);
        if (element) {
            return element;
        }
    }
    
    return null;
}

// 处理现有推文
function processExistingTweets() {
    const tweets = document.querySelectorAll('[data-testid="tweet"]');
    tweets.forEach(tweet => processTweet(tweet));
}

// 处理推文
function processTweet(tweetElement) {
    try {
        // 获取推文 ID
        const tweetId = tweetElement.getAttribute('data-item-id') || 
                        tweetElement.querySelector('[data-testid="tweet"]')?.getAttribute('data-item-id');
        
        if (!tweetId || tweetId === lastProcessedTweetId) {
            return;
        }
        
        // 解析推文数据
        const tweetData = parseTweet(tweetElement);
        
        if (!tweetData || !tweetData.content) {
            return;
        }
        
        // 检查是否 P0 账号
        const isP0 = P0_ACCOUNTS.some(account => 
            tweetData.author?.toLowerCase().includes(account.toLowerCase())
        );
        
        // 如果不是 P0 账号，跳过（节省资源）
        if (!isP0) {
            return;
        }
        
        lastProcessedTweetId = tweetId;
        
        // 提取币种信息
        tweetData.mentionedSymbols = extractCryptoSymbols(tweetData.content);
        
        // 发送到 background script
        chrome.runtime.sendMessage({
            type: 'tweet',
            data: tweetData
        }, (response) => {
            if (response?.success) {
                console.log('[TradeAgent] Tweet forwarded:', tweetData.author);
            }
        });
        
    } catch (error) {
        console.error('[TradeAgent] Error processing tweet:', error);
    }
}

// 解析推文
function parseTweet(tweetElement) {
    try {
        // 获取作者
        const authorElement = tweetElement.querySelector('[data-testid="User-Name"] span');
        const authorLink = tweetElement.querySelector('a[role="link"][href*="/"]');
        let author = authorElement?.textContent?.trim() || 
                     authorLink?.getAttribute('href')?.replace('/', '') || '';
        
        // 获取内容
        const contentElement = tweetElement.querySelector('[data-testid="tweetText"]');
        const content = contentElement?.textContent?.trim() || '';
        
        // 获取 URL
        const linkElement = tweetElement.querySelector('a[href*="/status/"]');
        const url = linkElement?.href || '';
        
        // 获取互动数据
        const likesElement = tweetElement.querySelector('[data-testid="like"] span');
        const retweetsElement = tweetElement.querySelector('[data-testid="retweet"] span');
        
        const likes = parseInt(likesElement?.textContent?.replace(/,/g, '') || '0');
        const retweets = parseInt(retweetsElement?.textContent?.replace(/,/g, '') || '0');
        
        // 获取话题标签
        const hashtagElements = contentElement?.querySelectorAll('a[href*="/hashtag/"]');
        const hashtags = Array.from(hashtagElements || []).map(el => el.textContent);
        
        // 获取推文 ID
        const id = url.match(/\/status\/(\d+)/)?.[1] || '';
        
        return {
            id,
            author,
            authorId: authorLink?.getAttribute('href')?.replace('/', ''),
            content,
            url,
            likes,
            retweets,
            hashtags,
            timestamp: Date.now()
        };
    } catch (error) {
        console.error('[TradeAgent] Error parsing tweet:', error);
        return null;
    }
}

// 提取币种符号
function extractCryptoSymbols(text) {
    const symbols = [];
    
    // 检查是否包含币种关键词
    for (const keyword of CRYPTO_KEYWORDS) {
        const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
        if (regex.test(text) && !symbols.includes(keyword)) {
            symbols.push(keyword);
        }
    }
    
    return symbols;
}

// 页面加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
