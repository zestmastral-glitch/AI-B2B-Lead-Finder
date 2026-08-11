import requests
from src.logger import get_logger

logger = get_logger(__name__)

def send_lead_notification(lead: dict, config: dict) -> bool:
    """
    Sends a Telegram message about a new lead.
    
    Args:
        lead: A dictionary containing 'business_name', 'website', and 'verified_emails'.
        config: Configuration dictionary.
        
    Returns:
        True on success, False on failure.
    """
    telegram_config = config.get('telegram', {})
    if not telegram_config.get('enabled', False):
        logger.info("Telegram notifications are disabled in config. Skipping lead notification.")
        return True

    bot_token = telegram_config.get('bot_token')
    chat_id = telegram_config.get('chat_id')
    
    if not bot_token or not chat_id:
        logger.warning("Telegram bot_token or chat_id missing in config.")
        return False

    business_name = lead.get('business_name', 'Unknown Business')
    website = lead.get('website', 'No Website')
    verified_emails = lead.get('verified_emails', 'None')

    message = f"""🔍 New Lead Found!
📋 {business_name}
🌐 {website}
📧 {verified_emails}"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Successfully sent lead notification for {business_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification for {business_name}: {e}")
        return False

def send_summary(stats: dict, config: dict) -> bool:
    """
    Sends an end-of-run summary via Telegram.
    
    Args:
        stats: Dictionary containing 'found', 'emailed', 'failed', 'skipped', 'verified', 'invalid'.
        config: Configuration dictionary.
        
    Returns:
        True on success, False on failure.
    """
    telegram_config = config.get('telegram', {})
    if not telegram_config.get('enabled', False):
        logger.info("Telegram notifications are disabled in config. Skipping summary.")
        return True

    bot_token = telegram_config.get('bot_token')
    chat_id = telegram_config.get('chat_id')
    
    if not bot_token or not chat_id:
        logger.warning("Telegram bot_token or chat_id missing in config.")
        return False

    message = f"""📊 Lead Bot Run Summary
─────────────────────
🔍 Found: {stats.get('found', 0)}
✅ Verified: {stats.get('verified', 0)}
❌ Invalid: {stats.get('invalid', 0)}
📧 Emailed: {stats.get('emailed', 0)}
⚠️ Failed: {stats.get('failed', 0)}
⏭️ Skipped: {stats.get('skipped', 0)}"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info("Successfully sent run summary notification.")
        return True
    except Exception as e:
        logger.warning(f"Failed to send Telegram summary notification: {e}")
        return False
