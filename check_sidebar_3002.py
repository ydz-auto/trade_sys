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
    print("Opening http://localhost:3002/")
    driver.get("http://localhost:3002/")

    # Wait for React to render
    print("Waiting for React to render...")
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.getElementById('root').children.length > 0")
    )
    time.sleep(3)

    print(f"\nPage Title: {driver.title}")

    # Check for ant-design components
    html = driver.page_source
    print("\n=== Checking for ant-design components ===")
    print(f"Has 'ant-layout': {'ant-layout' in html}")
    print(f"Has 'ant-menu': {'ant-menu' in html}")
    print(f"Has 'ant-drawer': {'ant-drawer' in html}")
    print(f"Has 'ant-sider': {'ant-layout-sider' in html or 'ant-sider' in html}")
    print(f"Has 'TradeAgent': {'TradeAgent' in html}")
    print(f"Has '监控层': {'监控层' in html}")

    # Find all ant-design elements
    menu_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-menu"]')
    print(f"\nElements with 'ant-menu' class: {len(menu_elements)}")

    layout_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-layout"]')
    print(f"Elements with 'ant-layout' class: {len(layout_elements)}")

    sider_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-layout-sider"], [class*="ant-sider"]')
    print(f"Elements with sider class: {len(sider_elements)}")

    drawer_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-drawer"]')
    print(f"Elements with drawer class: {len(drawer_elements)}")

    # Find menu items
    menu_items = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item')
    print(f"\nMenu items: {len(menu_items)}")

    for i, item in enumerate(menu_items):
        try:
            print(f"  {i+1}. {item.text}")
        except:
            pass

    # Find all navigation-related elements
    print("\n=== Checking for multiple nav structures ===")

    # Count visible siders
    aside_elements = driver.find_elements(By.TAG_NAME, 'aside')
    print(f"aside elements: {len(aside_elements)}")

    # Check for duplicated content
    nav_sections = driver.find_elements(By.XPATH, "//*[contains(@class, 'ant-menu-item-group-title')]")
    print(f"Menu section titles: {len(nav_sections)}")

    section_names = []
    for section in nav_sections:
        try:
            section_names.append(section.text)
        except:
            pass
    print(f"Section names: {section_names}")

    # Check for duplicate navigation items
    data_dashboards = driver.find_elements(By.XPATH, "//*[contains(text(), '数据大盘')]")
    print(f"\n'数据大盘' occurrences: {len(data_dashboards)}")

    control_centers = driver.find_elements(By.XPATH, "//*[contains(text(), '控制中心')]")
    print(f"'控制中心' occurrences: {len(control_centers)}")

    # Check for visible drawers
    visible_drawers = driver.find_elements(By.CSS_SELECTOR, '.ant-drawer-open')
    print(f"Open drawers: {len(visible_drawers)}")

    # Check drawer mask (overlay)
    drawer_masks = driver.find_elements(By.CSS_SELECTOR, '.ant-drawer-mask')
    print(f"Drawer masks: {len(drawer_masks)}")

    # Get screenshot
    driver.save_screenshot('/tmp/sidebar_check_3002.png')
    print("\nScreenshot saved to /tmp/sidebar_check_3002.png")

finally:
    input("Press Enter to close browser...")
    driver.quit()
