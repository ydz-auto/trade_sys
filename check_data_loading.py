from playwright.sync_api import sync_playwright
import json

def check_data_loading():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        api_requests = []
        api_responses = []
        console_errors = []
        
        def handle_request(request):
            if '/api/' in request.url or '/projection/' in request.url:
                api_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'resource_type': request.resource_type
                })
        
        def handle_response(response):
            if '/api/' in response.url or '/projection/' in response.url:
                try:
                    body = response.text()
                    api_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'body': body[:500] if body else None
                    })
                except Exception as e:
                    api_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'error': str(e)
                    })
        
        def handle_console(msg):
            if msg.type in ['error', 'warning']:
                console_errors.append({
                    'type': msg.type,
                    'text': msg.text
                })
        
        page.on('request', handle_request)
        page.on('response', handle_response)
        page.on('console', handle_console)
        
        try:
            print("正在访问页面并监控网络请求...")
            page.goto('http://localhost:3000/', timeout=30000)
            page.wait_for_load_state('networkidle')
            
            print("\n" + "="*60)
            print("API 请求列表:")
            print("="*60)
            for i, req in enumerate(api_requests, 1):
                print(f"{i}. {req['method']} {req['url']}")
            
            print("\n" + "="*60)
            print("API 响应详情:")
            print("="*60)
            for i, resp in enumerate(api_responses, 1):
                print(f"\n{i}. {resp['url']}")
                print(f"   状态码: {resp['status']}")
                if 'body' in resp and resp['body']:
                    print(f"   响应内容: {resp['body']}")
                if 'error' in resp:
                    print(f"   错误: {resp['error']}")
            
            print("\n" + "="*60)
            print("控制台错误/警告:")
            print("="*60)
            for err in console_errors:
                print(f"[{err['type']}] {err['text']}")
            
            print("\n" + "="*60)
            print("页面内容检查:")
            print("="*60)
            
            sections = {
                '价格数据': page.locator('text=/价格|Price|BTC|ETH/i').first,
                '新闻数据': page.locator('text=/新闻|News|资讯/i').first,
                '市场情绪': page.locator('text=/情绪|Sentiment|Fear/i').first,
                '技术指标': page.locator('text=/技术|Technical|RSI|MACD/i').first,
            }
            
            for name, locator in sections.items():
                try:
                    if locator.count() > 0:
                        print(f"✓ {name}: 找到元素")
                    else:
                        print(f"✗ {name}: 未找到元素")
                except:
                    print(f"? {name}: 检查失败")
            
            news_cards = page.locator('[class*="news"], [class*="News"], article').all()
            print(f"\n找到 {len(news_cards)} 个新闻相关元素")
            
            empty_states = page.locator('text=/暂无数据|No data|空|加载中|Loading/i').all()
            print(f"找到 {len(empty_states)} 个空状态/加载提示")
            for elem in empty_states:
                text = elem.text_content()
                if text:
                    print(f"  - {text}")
            
            screenshot_path = '/tmp/frontend_data_check.png'
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n截图已保存到: {screenshot_path}")
            
        except Exception as e:
            print(f"错误: {str(e)}")
        finally:
            browser.close()

if __name__ == '__main__':
    check_data_loading()
