from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--user-data-dir=/tmp/chrome-test3")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--no-sandbox")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3002/")
    driver.get("http://localhost:3002/")

    # Wait for menu to appear
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
    )
    time.sleep(2)

    print("\n=== Analyzing Page Structure ===")

    # Get the sidebar structure
    sidebar = driver.find_element(By.CSS_SELECTOR, '.ant-layout-sider')
    print(f"\nFound sidebar: {sidebar.tag_name}")

    # Get all direct children of sidebar
    sidebar_html = sidebar.get_attribute('innerHTML')
    print(f"Sidebar innerHTML length: {len(sidebar_html)}")

    # Count occurrences of key navigation items within sidebar
    sidebar_items = {
        '监控层': sidebar_html.count('监控层'),
        '策略层': sidebar_html.count('策略层'),
        '配置层': sidebar_html.count('配置层'),
        '执行层': sidebar_html.count('执行层'),
        '数据大盘': sidebar_html.count('数据大盘'),
        'TradeAgent': sidebar_html.count('TradeAgent'),
    }

    print("\n=== Sidebar Content Counts ===")
    for item, count in sidebar_items.items():
        print(f"{item}: {count}")

    # Check if there's a second navigation elsewhere
    print("\n=== Checking Main Content Area ===")
    main_content = driver.find_element(By.CSS_SELECTOR, '.ant-layout-content')
    main_html = main_content.get_attribute('innerHTML')

    # Check for "数据大盘" in main content
    dashboard_in_main = main_html.count('数据大盘')
    print(f"'数据大盘' in main content: {dashboard_in_main}")

    # Look for any other nav-like structures
    print("\n=== Looking for other navigation structures ===")

    # Check for header navigation
    headers = driver.find_elements(By.CSS_SELECTOR, '.ant-layout-header')
    print(f"Header elements: {len(headers)}")

    # Check for breadcrumbs or page titles
    page_titles = driver.find_elements(By.XPATH, "//*[contains(@class, 'title') or contains(@class, 'header')]")
    print(f"Title/Header elements: {len(page_titles)}")

    # Take a screenshot with element highlights
    driver.save_screenshot('/tmp/navigation_analysis.png')

    # Check viewport
    print("\n=== Viewport Info ===")
    print(f"Window size: {driver.get_window_size()}")

    # Check if we can see the full sidebar
    sidebar_size = sidebar.size
    sidebar_location = sidebar.location
    print(f"Sidebar size: {sidebar_size}")
    print(f"Sidebar location: {sidebar_location}")

    # Check if sidebar is visible
    is_visible = sidebar.is_displayed()
    print(f"Sidebar visible: {is_visible}")

    print("\n✓ Screenshot saved to /tmp/navigation_analysis.png")

finally:
    input("Press Enter to close browser...")
    driver.quit()
