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
chrome_options.add_argument("--disable-extensions")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3000/")
    driver.get("http://localhost:3000/")

    # Wait for page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(3)  # Wait for React to render

    print("\n=== Page Title ===")
    print(driver.title)

    print("\n=== Checking Navigation Elements ===")

    # Check for ant-layout-sider
    siders = driver.find_elements(By.CSS_SELECTOR, '.ant-layout-sider')
    print(f"ant-layout-sider elements: {len(siders)}")

    # Check for ant-menu
    menus = driver.find_elements(By.CSS_SELECTOR, '.ant-menu')
    print(f"ant-menu elements: {len(menus)}")

    # Check for ant-drawer
    drawers = driver.find_elements(By.CSS_SELECTOR, '.ant-drawer')
    print(f"ant-drawer elements: {len(drawers)}")

    # Check drawer open states
    drawer_wrappers = driver.find_elements(By.CSS_SELECTOR, '.ant-drawer-wrapper-left, .ant-drawer-content-wrapper')
    print(f"Drawer wrappers: {len(drawer_wrappers)}")

    # Get all layout elements
    layouts = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-layout"]')
    print(f"\nTotal ant-layout elements: {len(layouts)}")

    # Find menu items
    menu_items = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item')
    print(f"Menu items found: {len(menu_items)}")

    print("\n=== Menu Items List ===")
    for i, item in enumerate(menu_items):
        try:
            text = item.text
            print(f"{i+1}. {text}")
        except:
            print(f"{i+1}. <unable to get text>")

    # Check for visible elements with sidebar/nav classes
    print("\n=== Checking for multiple navigation structures ===")

    # Count sidebar navs
    nav_elements = driver.find_elements(By.CSS_SELECTOR, 'aside, nav, [role="navigation"]')
    print(f"Semantic nav elements: {len(nav_elements)}")

    # Take screenshot
    driver.save_screenshot('/tmp/sidebar_check.png')
    print("\nScreenshot saved to /tmp/sidebar_check.png")

    # Get page source length to verify full page loaded
    print(f"\nPage source length: {len(driver.page_source)} characters")

finally:
    input("Press Enter to close browser...")
    driver.quit()
