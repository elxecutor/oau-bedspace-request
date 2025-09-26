from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor
import threading
from time import sleep
import random
import json
import os
import logging

# Shared lock for resource-sensitive operations

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler('bedspace.log'), logging.StreamHandler()]
)

print_lock = threading.Lock()

def human_delay(min=0.3, max=1.2):
    sleep(random.uniform(min, max))

def is_strong_password(password):
    # Basic password strength check
    import re
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[@$!%*?&#]', password):
        return False
    return True

def worker(credentials, max_retries=3):
    user_id = credentials.get('user_id')
    password = credentials.get('password')
    if not user_id or not password:
        logging.error(f"Missing credentials for entry: {credentials}")
        return False
    if not is_strong_password(password):
        logging.warning(f"Weak password detected for {user_id}")
        return False

    for attempt in range(max_retries):
        try:
            with sync_playwright() as p:
                # Configure browser per thread
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    viewport={'width': 1366, 'height': 768}
                )
                page = context.new_page()

                try:
                    # Navigate to login
                    page.goto('https://eportal.oauife.edu.ng/login.php', timeout=15000)
                    human_delay()

                    # Fill credentials
                    page.fill('input[name="user_id"]', credentials['user_id'])
                    human_delay(0.5, 1)

                    page.fill('input[name="pswd"]', credentials['password'])
                    human_delay(0.3, 0.8)

                    # Select session/semester
                    page.select_option('select[name="SessionF"]', '2024')
                    page.select_option('select[name="SemesterF"]', '1')
                    human_delay()

                    # Submit form
                    with page.expect_navigation():
                        page.click('input[name="Submit"]')

                    # Verify login success
                    if not page.locator('text="Welcome"').first.is_visible(timeout=10000):
                        raise Exception("Login verification failed")

                    with print_lock:
                        logging.info(f"✓ Login successful for {user_id}")

                    # Navigate to bedspace allocation
                    bedspace_url = 'https://eportal.oauife.edu.ng/bedspaceallocationyear31.php'
                    page.goto(bedspace_url, timeout=15000)

                    # Verify bedspace page
                    if 'bedspaceallocationyear31' not in page.url:
                        raise Exception("Bedspace page redirection failed")

                    if not page.locator('h1:has-text("Bed Space")').first.is_visible():
                        raise Exception("Bedspace content verification failed")

                    with print_lock:
                        logging.info(f"✓ Bedspace access for {user_id}")

                    # Perform bedspace operations here
                    # Select male gender
                    page.select_option('select[name="gender"]', 'male')
                    human_delay()

                    # Click apply button
                    page.click('input[type="submit"][value="Apply"]')
                    human_delay()

                    with print_lock:
                        logging.info(f"✓ Bedspace request submitted for {user_id}")

                    return True

                except Exception as e:
                    with print_lock:
                        logging.warning(f"Attempt {attempt+1} failed for {user_id}: {str(e)}")
                    page.screenshot(path=f'error_{credentials["user_id"]}_{attempt}.png')
                    continue

                finally:
                    browser.close()

        except Exception as e:
            with print_lock:
                logging.error(f"Critical error for {user_id}: {str(e)}")
            continue

    return False

if __name__ == "__main__":
    # Load credentials from external JSON file
    cred_file = 'credentials.json'
    if not os.path.exists(cred_file):
        logging.error(f"Credentials file '{cred_file}' not found.")
        exit(1)
    with open(cred_file, 'r') as f:
        credentials_list = json.load(f)
    if not isinstance(credentials_list, list):
        logging.error("Credentials file must contain a list of credential objects.")
        exit(1)

    # Configure thread pool
    max_workers = min(5, len(credentials_list))  # Adjust based on system capabilities
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, creds) for creds in credentials_list]
        results = [f.result() for f in futures]

    success_rate = sum(results)/len(results) if results else 0
    logging.info(f"Completed with {success_rate*100:.1f}% success rate")
