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
chrome_options.add_argument("--user-data-dir=/tmp/chrome-test2")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--no-sandbox")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3002/")
    driver.get("http://localhost:3002/")

    # Wait for menu to appear
    print("Waiting for menu to render...")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
    )
    time.sleep(2)

    print("\n=== Page Title ===")
    print(driver.title)

    print("\n=== Checking for Navigation Structures ===")

    # Count all ant-layout-sider elements
    siders = driver.find_elements(By.CSS_SELECTOR, '.ant-layout-sider')
    print(f"ant-layout-sider count: {len(siders)}")

    # Count all ant-layout elements
    layouts = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-layout"]')
    print(f"Total ant-layout elements: {len(layouts)}")

    # Count all ant-menu elements
    menus = driver.find_elements(By.CSS_SELECTOR, '.ant-menu')
    print(f"ant-menu count: {len(menus)}")

    # Count all menu items
    menu_items = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item')
    print(f"Menu item count: {len(menu_items)}")

    # Count drawer elements
    drawers = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-drawer"]')
    print(f"Drawer elements: {len(drawers)}")

    # Check for open drawers
    open_drawers = driver.find_elements(By.CSS_SELECTOR, '.ant-drawer-open')
    print(f"Open drawers: {len(open_drawers)}")

    # Check for drawer masks
    drawer_masks = driver.find_elements(By.CSS_SELECTOR, '.ant-drawer-mask')
    print(f"Drawer masks: {len(drawer_masks)}")

    # Check for duplicate text content
    print("\n=== Checking for Duplicates ===")

    # Count occurrences of key items
    items_to_check = ['数据大盘', '控制中心', '因子面板', '监控层', '策略层', '配置层', '执行层']

    for item in items_to_check:
        elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{item}')]")
        print(f"'{item}' occurrences: {len(elements)}")

    # Get all menu section titles
    print("\n=== Menu Sections ===")
    section_titles = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item-group-title')
    print(f"Section titles found: {len(section_titles)}")
    for section in section_titles:
        print(f"  - {section.text}")

    # Get all menu item texts
    print("\n=== All Menu Items ===")
    for i, item in enumerate(menu_items):
        try:
            text = item.text
            cls = item.get_attribute('class')
            is_selected = 'ant-menu-item-selected' in cls if cls else False
            print(f"  {i+1}. {text} {'[SELECTED]' if is_selected else ''}")
        except:
            pass

    # Check for React StrictMode double rendering indicator
    print("\n=== Checking for React StrictMode ===")
    menu_count = len(driver.find_elements(By.CSS_SELECTOR, '.ant-menu'))
    if menu_count > 1:
        print(f"⚠️ Found {menu_count} menus - possible double rendering!")
    else:
        print("✓ Single menu rendering")

    # Check for hidden elements
    print("\n=== Hidden Elements ===")
    all_menus = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-menu"]')
    for i, menu in enumerate(all_menus):
        is_displayed = menu.is_displayed()
        style = menu.get_attribute('style') or ''
        print(f"Menu {i+1}: displayed={is_displayed}, style={style[:100]}")

    # Get screenshot
    driver.save_screenshot('/tmp/dual_sidebar_check.png')
    print("\nScreenshot saved to /tmp/dual_sidebar_check.png")

finally:
    input("Press Enter to close browser...")
    driver.quit()
