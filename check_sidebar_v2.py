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

    # Wait for React to render - look for the root element to have content
    print("Waiting for React to render...")
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.getElementById('root').children.length > 0")
    )

    # Additional wait for any dynamic content
    time.sleep(3)

    print(f"\nPage Title: {driver.title}")

    # Get the HTML content
    html = driver.page_source

    # Check for ant-design classes
    print("\n=== Checking for ant-design components ===")
    print(f"Has 'ant-layout': {'ant-layout' in html}")
    print(f"Has 'ant-menu': {'ant-menu' in html}")
    print(f"Has 'ant-drawer': {'ant-drawer' in html}")
    print(f"Has 'ant-sider': {'ant-sider' in html or 'ant-layout-sider' in html}")

    # Check for sidebar text
    print(f"Has 'TradeAgent': {'TradeAgent' in html}")
    print(f"Has '监控层': {'监控层' in html}")

    # Find all elements with ant-menu
    menu_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-menu"]')
    print(f"\nElements with 'ant-menu' in class: {len(menu_elements)}")

    # Find all layout elements
    layout_elements = driver.find_elements(By.CSS_SELECTOR, '[class*="ant-layout"]')
    print(f"Elements with 'ant-layout' in class: {len(layout_elements)}")

    # Find all aside elements
    aside_elements = driver.find_elements(By.TAG_NAME, 'aside')
    print(f"aside elements: {len(aside_elements)}")

    # Try to find the sidebar container by looking for the TradeAgent text
    print("\n=== Searching for sidebar structure ===")

    # Look for elements containing specific text
    try:
        trade_agent_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'TradeAgent')]")
        print(f"Found 'TradeAgent' element: {trade_agent_elem.tag_name}")
        parent = trade_agent_elem
        for i in range(5):
            parent = parent.find_element(By.XPATH, "..")
            print(f"  Parent {i+1}: {parent.tag_name} class={parent.get_attribute('class')[:100] if parent.get_attribute('class') else 'None'}")
    except Exception as e:
        print(f"Error finding TradeAgent: {e}")

    # Try to find the menu items
    print("\n=== Finding navigation items ===")
    try:
        dashboard_link = driver.find_element(By.XPATH, "//*[contains(text(), '数据大盘')]")
        print(f"Found '数据大盘': {dashboard_link.tag_name}")
        menu_parent = dashboard_link
        for i in range(3):
            menu_parent = menu_parent.find_element(By.XPATH, "..")
            cls = menu_parent.get_attribute('class') or ''
            print(f"  Parent {i+1}: {menu_parent.tag_name} class={cls[:80]}")
    except Exception as e:
        print(f"Error finding data大盘: {e}")

    # Get all unique class names
    print("\n=== All unique class prefixes in DOM ===")
    classes = set()
    elements = driver.find_elements(By.XPATH, "//*[@class]")
    for elem in elements[:100]:  # Check first 100 elements with classes
        cls = elem.get_attribute('class')
        if cls:
            for c in cls.split():
                if not c.startswith('ant-') and not c.startswith('css-'):
                    prefix = c.split('-')[0] if '-' in c else c
                    if len(prefix) > 2:
                        classes.add(prefix)
    print(f"Non-ant classes: {sorted(list(classes))[:20]}")

    # Take screenshot
    driver.save_screenshot('/tmp/sidebar_check.png')
    print("\nScreenshot saved to /tmp/sidebar_check.png")

finally:
    input("Press Enter to close browser...")
    driver.quit()
