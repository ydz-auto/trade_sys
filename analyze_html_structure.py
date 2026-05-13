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
chrome_options.add_argument("--user-data-dir=/tmp/chrome-test-html")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--no-sandbox")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3002/")
    driver.get("http://localhost:3002/")

    # Wait for menu
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
    )
    time.sleep(2)

    # Get the sidebar HTML
    sidebar = driver.find_element(By.CSS_SELECTOR, '.ant-layout-sider')
    sidebar_html = sidebar.get_attribute('outerHTML')

    # Save to file
    with open('/tmp/sidebar_html.html', 'w', encoding='utf-8') as f:
        f.write(sidebar_html)

    print("\nSidebar HTML saved to /tmp/sidebar_html.html")
    print(f"HTML length: {len(sidebar_html)} characters")

    # Find all menu item group titles
    titles = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item-group-title')
    print(f"\nFound {len(titles)} menu item group titles")

    # Check each title
    for i, title in enumerate(titles):
        text = title.text
        # Get parent structure
        parent = title.find_element(By.XPATH, "..")
        parent_class = parent.get_attribute('class')
        grandparent = parent.find_element(By.XPATH, "..")
        grandparent_class = grandparent.get_attribute('class')

        print(f"\nTitle {i+1}: '{text}'")
        print(f"  Parent: {parent.tag_name} class='{parent_class}'")
        print(f"  Grandparent: {grandparent.tag_name} class='{grandparent_class}'")

        # Check if element is visible
        is_visible = title.is_displayed()
        rect = title.rect
        print(f"  Visible: {is_visible}, Position: x={rect['x']}, y={rect['y']}")

    # Look for React keys or IDs
    print("\n=== Checking for React keys ===")
    all_lis = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item-group')
    print(f"Found {len(all_lis)} ant-menu-item-group elements")

    # Check if there are any data attributes
    for i, li in enumerate(all_lis[:4]):
        data_key = li.get_attribute('data-key') or li.get_attribute('key')
        react_id = li.get_attribute('data-reactid') or li.get_attribute('id')
        print(f"Group {i+1}: data-key={data_key}, id={react_id}")

    # Check menu structure in detail
    print("\n=== Menu Structure Analysis ===")
    menu = driver.find_element(By.CSS_SELECTOR, '.ant-menu')
    menu_children = menu.find_elements(By.XPATH, "./*")
    print(f"Direct children of menu: {len(menu_children)}")

    for i, child in enumerate(menu_children):
        tag = child.tag_name
        cls = child.get_attribute('class') or ''
        inner_text = child.text[:50] if child.text else ''
        print(f"  {i+1}. {tag} class='{cls[:60]}' text='{inner_text}'")

finally:
    input("Press Enter to close browser...")
    driver.quit()
