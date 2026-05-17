from playwright.sync_api import sync_playwright
import os

def check_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        console_messages = []
        errors = []
        
        def handle_console(msg):
            console_messages.append(f"[{msg.type}] {msg.text}")
            if msg.type == 'error':
                errors.append(msg.text)
        
        page.on('console', handle_console)
        
        page.on('pageerror', lambda err: errors.append(f"Page Error: {err}"))
        
        try:
            print("正在访问 http://localhost:3000/ ...")
            page.goto('http://localhost:3000/', timeout=30000)
            
            print("等待页面加载完成...")
            page.wait_for_load_state('networkidle')
            
            screenshot_path = '/tmp/frontend_check.png'
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n✓ 页面截图已保存到: {screenshot_path}")
            
            title = page.title()
            print(f"\n页面标题: {title}")
            
            url = page.url
            print(f"当前URL: {url}")
            
            h1_elements = page.locator('h1').all()
            print(f"\n找到 {len(h1_elements)} 个 h1 标题元素")
            for i, h1 in enumerate(h1_elements[:5]):
                print(f"  - H1 {i+1}: {h1.text_content()}")
            
            buttons = page.locator('button').all()
            print(f"\n找到 {len(buttons)} 个按钮")
            for i, btn in enumerate(buttons[:10]):
                text = btn.text_content()
                if text:
                    print(f"  - 按钮 {i+1}: {text}")
            
            links = page.locator('a').all()
            print(f"\n找到 {len(links)} 个链接")
            for i, link in enumerate(links[:10]):
                text = link.text_content()
                href = link.get_attribute('href')
                if text:
                    print(f"  - 链接 {i+1}: {text} -> {href}")
            
            print("\n" + "="*50)
            print("控制台消息:")
            print("="*50)
            if console_messages:
                for msg in console_messages:
                    print(msg)
            else:
                print("无控制台消息")
            
            print("\n" + "="*50)
            print("错误检查:")
            print("="*50)
            if errors:
                print("❌ 发现错误:")
                for error in errors:
                    print(f"  - {error}")
            else:
                print("✓ 未发现错误")
            
            visible_elements = page.locator('body *:visible').all()
            print(f"\n页面上可见元素数量: {len(visible_elements)}")
            
            body_text = page.locator('body').text_content()
            if body_text:
                print(f"\n页面文本内容长度: {len(body_text)} 字符")
            
            print("\n" + "="*50)
            print("检查结果:")
            print("="*50)
            if errors:
                print("❌ 页面存在问题,请查看上方的错误信息")
                return False
            else:
                print("✓ 页面加载正常,未发现明显错误")
                return True
                
        except Exception as e:
            print(f"\n❌ 访问页面时发生错误: {str(e)}")
            screenshot_path = '/tmp/frontend_error.png'
            try:
                page.screenshot(path=screenshot_path)
                print(f"错误页面截图已保存到: {screenshot_path}")
            except:
                pass
            return False
        finally:
            browser.close()

if __name__ == '__main__':
    success = check_frontend()
    exit(0 if success else 1)
