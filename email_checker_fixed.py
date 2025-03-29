import imaplib
import requests
import json
import os
import re
import ssl
import logging
import time
import base64
from email.utils import parsedate_to_datetime
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration files
try:
    with open('Inbox/config.json', 'r') as config_file:
        config = json.load(config_file)
    with open('Inbox/custom_checks.json', 'r') as custom_file:
        custom_checks = json.load(custom_file)
except Exception as e:
    logger.error(f"Failed to load config files: {e}")
    raise

# Default Checks
check_roblox = config["default_checks"]["roblox"]
check_steam = config["default_checks"]["steam"]
check_discord = config["default_checks"]["discord"]
check_reddit = config["default_checks"]["reddit"]
check_epicgames = config["default_checks"]["epicgames"]
check_riot = config["default_checks"]["riotgames"]
check_rockstar = config["default_checks"]["rockstargames"]

discord_webhook = config["discord_webhook"]

def parsedate(date_str):
    try:
        return parsedate_to_datetime(date_str)
    except Exception as e:
        logger.warning(f"Error parsing date: {e}")
        return None

def fetch_emails(imap, query):
    try:
        result, data = imap.uid("search", None, query)
        if result == "OK":
            return data[0].split()
        return []
    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        return []

def fetch_email_date(imap, uid):
    try:
        result, data = imap.uid("fetch", uid, "(BODY[HEADER.FIELDS (DATE)])")
        if result == "OK":
            date_str = data[0][1].decode().strip()
            return parsedate(date_str)
        return None
    except Exception as e:
        logger.error(f"Error fetching email date: {e}")
        return None

def connect_imap(server, email, password):
    for attempt in range(3):  # Try up to 3 times
        try:
            # Create SSL context with modern security settings
            ssl_context = ssl.create_default_context()
            
            # Adjust SSL settings based on provider
            if 'outlook' in server or 'office365' in server:
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            elif 'gmail' in server:
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            logger.info(f"Attempt {attempt + 1}: Connecting to {server}...")
            
            # Set timeout and enable debug for troubleshooting
            imap = imaplib.IMAP4_SSL(
                host=server,
                port=993,
                timeout=45,
                ssl_context=ssl_context
            )
            imap.debug = 4  # Enable verbose debug output
            
            # Try standard login first
            try:
                logger.info("Attempting standard login...")
                result, response = imap.login(email, password)
                if result == "OK":
                    logger.info("Login successful")
                    return imap
            except imaplib.IMAP4.error:
                logger.info("Standard login failed, trying basic AUTHENTICATE...")
                try:
                    creds = f"{email}\x00{password}"
                    encoded = base64.b64encode(creds.encode()).decode()
                    result, response = imap._simple_command('AUTHENTICATE', 'PLAIN', encoded)
                    if result == "OK":
                        logger.info("Basic authentication successful")
                        return imap
                except Exception as e:
                    logger.error(f"Basic authentication failed: {e}")
            
            logger.error(f"Login failed: {response}")
            time.sleep(3)  # Wait before retrying
            
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP protocol error: {str(e)}")
            if "AUTHENTICATIONFAILED" in str(e):
                logger.error("Authentication failed. Please verify credentials.")
            elif "Too many login attempts" in str(e):
                logger.error("Too many login attempts. Try again later.")
            time.sleep(5)  # Longer wait for rate-limited errors
        except ssl.SSLError as e:
            logger.error(f"SSL error: {str(e)}")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            time.sleep(3)
    
    logger.error("All connection attempts failed")
    return None

# Rest of the original functions remain unchanged...
[Rest of file content truncated for brevity]