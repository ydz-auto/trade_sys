from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

# Setup Chrome options - disable web security for dev
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--user-data-dir=/tmp/chrome-test")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--no-sandbox")

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Opening http://localhost:3002/")
    driver.get("http://localhost:3002/")

    # Wait for network to be idle
    print("Waiting for network idle...")
    time.sleep(5)

    print(f"\nPage Title: {driver.title}")

    # Get console logs
    print("\n=== Console Logs ===")
    logs = driver.get_log('browser')
    if logs:
        for log in logs:
            print(f"[{log['level']}] {log['message']}")
    else:
        print("No browser console logs")

    # Check for errors
    print("\n=== Page Errors ===")
    errors = driver.get_log('driver')
    if errors:
        for error in errors:
            print(f"[{error['level']}] {error['message']}")

    # Get page source
    html = driver.page_source
    print(f"\nPage source length: {len(html)} characters")

    # Check what's in the root
    root_content = driver.find_element(By.ID, 'root').get_attribute('innerHTML')
    print(f"\nRoot element innerHTML length: {len(root_content)}")
    print(f"Root content preview: {root_content[:500]}")

    # Try waiting for specific ant components
    print("\n=== Trying to wait for ant-menu ===")
    try:
        menu = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-menu"))
        )
        print(f"Found menu: {menu}")
    except Exception as e:
        print(f"No ant-menu found: {e}")

    # Try getting all text content
    print("\n=== All text content ===")
    body_text = driver.find_element(By.TAG_NAME, 'body').text
    print(body_text[:500] if body_text else "Empty body text")

finally:
    input("Press Enter to close browser...")
    driver.quit()
