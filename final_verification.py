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
chrome_options.add_argument("--user-data-dir=/tmp/chrome-final-check")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--no-sandbox")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3002/")
    driver.get("http://localhost:3002/")

    # Wait for page to fully load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
    )
    time.sleep(3)

    print("\n" + "="*60)
    print(" PC端导航栏修复验证报告")
    print("="*60 + "\n")

    # 1. 检查侧边栏关闭按钮
    sidebar = driver.find_element(By.CSS_SELECTOR, '.ant-layout-sider')
    sidebar_html = sidebar.get_attribute('innerHTML')
    has_close_button = 'CloseOutlined' in sidebar_html or 'anticon-close' in sidebar_html

    print("1. 侧边栏关闭按钮检查:")
    if has_close_button:
        close_buttons = driver.find_elements(By.CSS_SELECTOR, '.ant-layout-sider .ant-btn')
        print(f"   ⚠️  发现 {len(close_buttons)} 个关闭按钮")
    else:
        print("   ✅ 侧边栏关闭按钮已正确隐藏")

    # 2. 检查 Header 菜单按钮
    header = driver.find_element(By.CSS_SELECTOR, '.ant-layout-header')
    header_html = header.get_attribute('innerHTML')
    has_menu_button = 'MenuOutlined' in header_html or 'anticon-menu' in header_html

    print("\n2. Header 菜单按钮检查:")
    if has_menu_button:
        print("   ⚠️  Header 中仍包含菜单按钮")
    else:
        print("   ✅ Header 菜单按钮已正确隐藏")

    # 3. 检查菜单结构
    print("\n3. 菜单结构检查:")
    menu_items = driver.find_elements(By.CSS_SELECTOR, '.ant-menu-item')
    print(f"   菜单项数量: {len(menu_items)}")

    sections = ['监控层', '策略层', '配置层', '执行层']
    all_ok = True
    for section in sections:
        count = sidebar_html.count(section)
        if count == 1:
            print(f"   ✅ '{section}': 1次 (正常)")
        else:
            print(f"   ⚠️  '{section}': {count}次 (异常)")
            all_ok = False

    # 4. 整体布局检查
    print("\n4. 整体布局检查:")
    sidebar_visible = sidebar.is_displayed()
    sidebar_position = sidebar.location
    print(f"   侧边栏可见: {sidebar_visible}")
    print(f"   侧边栏位置: x={sidebar_position['x']}, y={sidebar_position['y']}")

    main_content = driver.find_element(By.CSS_SELECTOR, '.ant-layout-content')
    main_visible = main_content.is_displayed()
    print(f"   主内容区可见: {main_visible}")

    # 5. 总结
    print("\n" + "="*60)
    if not has_close_button and not has_menu_button and all_ok:
        print("✅ 所有修复成功！PC端导航栏显示正确。")
        print("   - 关闭按钮已隐藏")
        print("   - 菜单按钮已隐藏")
        print("   - 菜单无重复项")
    else:
        print("⚠️  部分问题仍存在，请检查上述结果")
    print("="*60)

    # 保存截图
    driver.save_screenshot('/tmp/final_pc_fix.png')
    print("\n截图已保存: /tmp/final_pc_fix.png")

finally:
    input("\n按 Enter 关闭浏览器...")
    driver.quit()
