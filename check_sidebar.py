from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('http://localhost:3000/')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Take screenshot
    page.screenshot(path='/tmp/sidebar_check.png', full_page=False)
    print("Screenshot saved to /tmp/sidebar_check.png")

    # Check for navigation elements
    print("\n=== Checking for navigation elements ===")

    # Check for ant-layout-sider (AppSidebar)
    siders = page.locator('.ant-layout-sider').all()
    print(f"Found {len(siders)} ant-layout-sider elements")

    # Check for ant-menu
    menus = page.locator('.ant-menu').all()
    print(f"Found {len(menus)} ant-menu elements")

    # Check for Drawer
    drawers = page.locator('.ant-drawer').all()
    print(f"Found {len(drawers)} ant-drawer elements")

    # Get all navigation-related elements
    print("\n=== All elements with 'sidebar' or 'nav' in class ===")
    all_html = page.content()

    # Count sidebar-related divs
    sidebar_divs = page.locator('[class*="sidebar"], [class*="Sidebar"], [class*="sider"]').all()
    print(f"Found {len(sidebar_divs)} sidebar/sider related elements")

    # Look for menu items
    menu_items = page.locator('.ant-menu-item').all()
    print(f"\nFound {len(menu_items)} menu items:")
    for i, item in enumerate(menu_items[:10]):
        text = item.inner_text()
        print(f"  {i+1}. {text}")

    # Check page structure
    print("\n=== Page Structure (Layout elements) ===")
    layout_elements = page.locator('[class*="ant-layout"]').all()
    print(f"Found {len(layout_elements)} ant-layout elements")

    # Print visible drawer states
    visible_drawers = page.locator('.ant-drawer-open, .ant-drawer:visible').all()
    print(f"\nVisible drawers: {len(visible_drawers)}")

    # Check for any overlay or portal elements
    overlays = page.locator('.ant-drawer-mask, .ant-modal-mask').all()
    print(f"Overlay masks found: {len(overlays)}")

    browser.close()
