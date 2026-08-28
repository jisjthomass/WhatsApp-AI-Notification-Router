import httpx
import logging
from router.config import META_ACCESS_TOKEN, META_PHONE_NUMBER_ID

logger = logging.getLogger(__name__)

async def send_whatsapp_message(to_phone_number: str, text: str) -> bool:
    """Send a text message back to a user via the WhatsApp Cloud API.
    
    Args:
        to_phone_number: The recipient's phone number (wa_id).
        text: The message body to send.
        
    Returns:
        True if successful, False otherwise.
    """
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        logger.warning("META_ACCESS_TOKEN or META_PHONE_NUMBER_ID is not set. Skipping outbound message.")
        return False
        
    url = f"https://graph.facebook.com/v17.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "text",
        "text": {
            "body": text
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info("Successfully sent WhatsApp reply to %s", to_phone_number)
            return True
    except httpx.HTTPStatusError as e:
        logger.error("Failed to send WhatsApp message. Status: %s, Response: %s", e.response.status_code, e.response.text)
        return False
    except Exception as e:
        logger.error("Error sending WhatsApp message: %s", e)
        return False
