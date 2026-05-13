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
chrome_options.add_argument("--user-data-dir=/tmp/chrome-test-final2")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--no-sandbox")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3002/")
    driver.get("http://localhost:3002/")

    # Wait for menu to appear
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
    )
    time.sleep(3)

    print("\n=== PC端导航栏修复验证 ===\n")

    # Check if menu button is hidden in PC mode
    menu_buttons = driver.find_elements(By.CSS_SELECTOR, '.ant-btn-icon-only')
    print(f"图标按钮数量: {len(menu_buttons)}")

    # Check if header has the menu button
    header = driver.find_element(By.CSS_SELECTOR, '.ant-layout-header')
    header_html = header.get_attribute('innerHTML')

    has_menu_button = 'MenuOutlined' in header_html or 'anticon-menu' in header_html
    print(f"Header中包含菜单按钮: {has_menu_button}")

    # Check for the sidebar
    sidebar = driver.find_element(By.CSS_SELECTOR, '.ant-layout-sider')
    sidebar_visible = sidebar.is_displayed()
    sidebar_position = sidebar.location
    print(f"\n侧边栏可见: {sidebar_visible}")
    print(f"侧边栏位置: x={sidebar_position['x']}, y={sidebar_position['y']}")

    # Check menu structure
    menu_items = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item')
    print(f"\n菜单项数量: {len(menu_items)}")

    # Check for duplicates
    sidebar_html = sidebar.get_attribute('innerHTML')
    sections = ['监控层', '策略层', '配置层', '执行层']

    print("\n=== 菜单分组检查 ===")
    all_ok = True
    for section in sections:
        count = sidebar_html.count(section)
        status = "✓" if count == 1 else "⚠️"
        print(f"{status} '{section}': {count}次")
        if count != 1:
            all_ok = False

    # Check page layout
    print("\n=== 页面布局检查 ===")
    main_content = driver.find_element(By.CSS_SELECTOR, '.ant-layout-content')
    main_visible = main_content.is_displayed()
    print(f"主内容区可见: {main_visible}")

    # Take screenshot
    driver.save_screenshot('/tmp/pc_fix_verification.png')
    print("\n✓ 截图已保存到 /tmp/pc_fix_verification.png")

    print("\n" + "="*50)
    if all_ok and not has_menu_button and sidebar_visible:
        print("✅ PC端导航栏修复成功！")
        print("   - 菜单按钮已隐藏")
        print("   - 侧边栏正常显示")
        print("   - 无重复菜单项")
    else:
        print("⚠️  可能仍有问题，请检查截图")
    print("="*50)

finally:
    input("按 Enter 关闭浏览器...")
    driver.quit()
