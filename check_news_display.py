from playwright.sync_api import sync_playwright
import json

def check_news_display():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print("正在访问页面...")
            page.goto('http://localhost:3000/', timeout=30000)
            page.wait_for_load_state('networkidle')
            
            print("\n" + "="*60)
            print("检查新闻数据是否显示")
            print("="*60)
            
            news_sections = page.locator('[class*="news"], [class*="News"]').all()
            print(f"找到 {len(news_sections)} 个新闻相关区块")
            
            news_items = page.locator('text=/Poland passes|Bitcoin Depot|Bitcoin Breaks/i').all()
            print(f"找到 {len(news_items)} 个新闻标题元素")
            for i, item in enumerate(news_items[:5], 1):
                print(f"  {i}. {item.text_content()}")
            
            no_data_elements = page.locator('text=/No data|暂无数据|空/i').all()
            print(f"\n找到 {len(no_data_elements)} 个'无数据'提示")
            for elem in no_data_elements:
                parent = elem.locator('xpath=..')
                parent_text = parent.text_content()
                print(f"  - {parent_text[:100]}")
            
            page_text = page.locator('body').text_content()
            
            keywords = ['Poland', 'Bitcoin Depot', 'MiCA', 'ATM Revenue']
            found_keywords = [kw for kw in keywords if kw in page_text]
            
            print(f"\n在页面中找到的新闻关键词:")
            for kw in found_keywords:
                print(f"  ✓ {kw}")
            
            screenshot_path = '/tmp/frontend_news_check.png'
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n截图已保存到: {screenshot_path}")
            
            if found_keywords:
                print("\n✓ 新闻数据已成功显示在页面上!")
            else:
                print("\n✗ 新闻数据未显示在页面上")
            
        except Exception as e:
            print(f"错误: {str(e)}")
        finally:
            browser.close()

if __name__ == '__main__':
    check_news_display()
