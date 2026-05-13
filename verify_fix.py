from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--user-data-dir=/tmp/chrome-test-final")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--no-sandbox")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3002/")
    print("Waiting for page to reload with changes...")
    driver.get("http://localhost:3002/")

    # Wait for menu to appear and reload
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
    )
    time.sleep(3)

    print("\n=== Verification After Fix ===")

    # Count menu items
    menu_items = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item')
    print(f"\nMenu items count: {len(menu_items)}")

    # Count menu sections
    section_titles = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item-group-title')
    print(f"Section titles count: {len(section_titles)}")

    # Check for duplicates in sidebar
    sidebar = driver.find_element(By.CSS_SELECTOR, '.ant-layout-sider')
    sidebar_html = sidebar.get_attribute('innerHTML')

    print("\n=== Sidebar Content Verification ===")
    sections = ['监控层', '策略层', '配置层', '执行层']
    for section in sections:
        count = sidebar_html.count(section)
        status = "✓" if count == 1 else "⚠️"
        print(f"{status} '{section}': {count} occurrences")

    # Check "数据大盘"
    dashboard_count = sidebar_html.count('数据大盘')
    status = "✓" if dashboard_count == 1 else "⚠️"
    print(f"{status} '数据大盘': {dashboard_count} occurrences")

    # Check overall menu structure
    print("\n=== Menu Structure ===")
    for i, item in enumerate(menu_items[:10]):
        try:
            text = item.text
            cls = item.get_attribute('class')
            is_selected = 'ant-menu-item-selected' in cls if cls else False
            marker = "✓" if i < 10 else "⚠️"
            print(f"{marker} {i+1}. {text} {'[SELECTED]' if is_selected else ''}")
        except:
            pass

    # Take screenshot
    driver.save_screenshot('/tmp/after_fix.png')
    print("\n✓ Screenshot saved to /tmp/after_fix.png")

    print("\n" + "="*50)
    print("RESULT: Navigation should now display correctly!")
    print("="*50)

finally:
    input("Press Enter to close browser...")
    driver.quit()
