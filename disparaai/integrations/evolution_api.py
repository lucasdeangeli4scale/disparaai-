"""Evolution API integration for WhatsApp messaging."""

import os
import json
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from disparaai.models.whatsapp import OutgoingMessage, WhatsAppWebhookEvent
from disparaai.utils.logger import safe_json_dumps

# Suppress httpx debug logging to prevent base64 data leakage
logging.getLogger("httpx").setLevel(logging.WARNING)


class EvolutionAPIError(Exception):
    """Evolution API specific error."""
    pass


class EvolutionAPI:
    """Evolution API client for WhatsApp integration."""
    
    def __init__(
        self, 
        api_url: str = None, 
        api_key: str = None, 
        instance_name: str = None
    ):
        """
        Initialize Evolution API client.
        
        Args:
            api_url: Evolution API base URL
            api_key: API authentication key
            instance_name: WhatsApp instance name
        """
        self.api_url = (api_url or os.getenv("EVOLUTION_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("EVOLUTION_API_KEY")
        self.instance_name = instance_name or os.getenv("EVOLUTION_INSTANCE_NAME")
        
        if not all([self.api_url, self.api_key, self.instance_name]):
            raise EvolutionAPIError(
                "Missing required Evolution API configuration: URL, API key, or instance name"
            )
        
        # HTTP client with default headers
        self.client = httpx.AsyncClient(
            headers={
                "apikey": self.api_key,
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def send_text_message(self, to: str, text: str) -> Dict[str, Any]:
        """
        Send text message via WhatsApp.
        
        Args:
            to: Recipient phone number (E.164 format)
            text: Message text
            
        Returns:
            API response data
        """
        url = f"{self.api_url}/message/sendText/{self.instance_name}"
        
        payload = {
            "number": to.replace("+", ""),
            "text": text
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise EvolutionAPIError(f"HTTP error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise EvolutionAPIError(f"Failed to send message: {str(e)}")
    
    async def send_media_message(
        self, 
        to: str, 
        media_data: str, 
        caption: str = None, 
        media_type: str = "image",
        filename: str = None,
        mimetype: str = None
    ) -> Dict[str, Any]:
        """
        Send media message via WhatsApp using Evolution API format.
        
        Args:
            to: Recipient phone number
            media_data: Base64 encoded media data or URL
            caption: Optional caption
            media_type: Type of media (image, video, audio, document)
            filename: Optional filename for the media
            mimetype: Optional MIME type (e.g., "image/jpeg", "image/png")
            
        Returns:
            API response data
        """
        url = f"{self.api_url}/message/sendMedia/{self.instance_name}"
        
        # Use official Evolution API v2.3.0 format (direct properties, not nested in mediaMessage)
        payload = {
            "number": to.replace("+", ""),
            "mediatype": media_type,  # Required: "image", "video", "document", "audio"
            "media": media_data,      # Base64 data or URL
            "mimetype": mimetype or self._get_default_mimetype(media_type, filename)
        }
        
        # Add optional fields
        if caption:
            payload["caption"] = caption
        if filename:
            payload["fileName"] = filename
        
        try:
            # Log request without sensitive data
            safe_payload = {k: f"<base64 data: {len(v)} chars>" if k == "media" and len(str(v)) > 100 else v 
                          for k, v in payload.items()}
            logging.getLogger(__name__).debug(f"Sending media message: {safe_json_dumps(safe_payload)}")
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Log success without sensitive data
            logging.getLogger(__name__).info(f"Media message sent successfully to {to}")
            return result
        except httpx.HTTPStatusError as e:
            raise EvolutionAPIError(f"HTTP error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise EvolutionAPIError(f"Failed to send media: {str(e)}")
    
    def _get_default_mimetype(self, media_type: str, filename: str = None) -> str:
        """Get default MIME type based on media type and optional filename.
        
        Follows Evolution API patterns: uses mime-types library approach
        with fallback defaults matching Evolution API's internal defaults.
        """
        if filename:
            # Try to determine from file extension (following Evolution API pattern)
            filename_lower = filename.lower()
            
            # Image extensions
            if filename_lower.endswith(('.jpg', '.jpeg')):
                return 'image/jpeg'
            elif filename_lower.endswith('.png'):
                return 'image/png'
            elif filename_lower.endswith('.gif'):
                return 'image/gif'
            elif filename_lower.endswith('.webp'):
                return 'image/webp'
            elif filename_lower.endswith('.bmp'):
                return 'image/bmp'
                
            # Document extensions  
            elif filename_lower.endswith('.pdf'):
                return 'application/pdf'
            elif filename_lower.endswith(('.doc', '.docx')):
                return 'application/msword'
            elif filename_lower.endswith(('.xls', '.xlsx')):
                return 'application/vnd.ms-excel'
            elif filename_lower.endswith(('.ppt', '.pptx')):
                return 'application/vnd.ms-powerpoint'
            elif filename_lower.endswith('.txt'):
                return 'text/plain'
                
            # Video extensions
            elif filename_lower.endswith('.mp4'):
                return 'video/mp4'
            elif filename_lower.endswith('.avi'):
                return 'video/avi'
            elif filename_lower.endswith('.mkv'):
                return 'video/mkv'
            elif filename_lower.endswith('.mov'):
                return 'video/quicktime'
                
            # Audio extensions (Evolution API supports MP3 and OGG primarily)
            elif filename_lower.endswith('.mp3'):
                return 'audio/mpeg'  # Standard MIME type for MP3
            elif filename_lower.endswith('.ogg'):
                return 'audio/ogg'
            elif filename_lower.endswith('.wav'):
                return 'audio/wav'
            elif filename_lower.endswith('.aac'):
                return 'audio/aac'
        
        # Default MIME types by media type (matching Evolution API internal defaults)
        defaults = {
            'image': 'image/png',        # Evolution API default
            'video': 'video/mp4',        # Evolution API default  
            'audio': 'audio/mp4',        # Evolution API default (processed audio)
            'document': 'application/pdf' # Evolution API default
        }
        return defaults.get(media_type, 'application/octet-stream')
    
    async def get_instance_status(self) -> Dict[str, Any]:
        """
        Get WhatsApp instance connection status.
        
        Returns:
            Instance status data
        """
        url = f"{self.api_url}/instance/connectionState/{self.instance_name}"
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise EvolutionAPIError(f"HTTP error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise EvolutionAPIError(f"Failed to get status: {str(e)}")
    
    async def set_webhook(self, webhook_url: str, events: List[str] = None) -> Dict[str, Any]:
        """
        Configure webhook for the instance.
        
        Args:
            webhook_url: URL to receive webhook events
            events: List of events to subscribe to
            
        Returns:
            Webhook configuration response
        """
        if events is None:
            events = [
                "MESSAGES_UPSERT",
                "MESSAGES_UPDATE", 
                "SEND_MESSAGE",
                "CONNECTION_UPDATE"
            ]
        
        url = f"{self.api_url}/webhook/set/{self.instance_name}"
        
        payload = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "webhook_by_events": False,
                "events": events
            }
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise EvolutionAPIError(f"HTTP error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise EvolutionAPIError(f"Failed to set webhook: {str(e)}")
    
    async def bulk_send_messages(self, messages: List[OutgoingMessage]) -> List[Dict[str, Any]]:
        """
        Send multiple messages with rate limiting.
        
        Args:
            messages: List of messages to send
            
        Returns:
            List of send results
        """
        results = []
        
        for message in messages:
            try:
                if message.media_url:
                    result = await self.send_media_message(
                        message.to, 
                        message.media_url, 
                        caption=message.caption or message.text
                    )
                else:
                    result = await self.send_text_message(message.to, message.text)
                
                results.append({
                    "recipient": message.to,
                    "success": True,
                    "data": result
                })
                
                # Rate limiting - wait 1 second between messages
                await asyncio.sleep(1)
                
            except Exception as e:
                results.append({
                    "recipient": message.to,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    def process_webhook_event(self, webhook_data: Dict[str, Any]) -> WhatsAppWebhookEvent:
        """
        Process incoming webhook event.
        
        Args:
            webhook_data: Raw webhook data from Evolution API
            
        Returns:
            Processed webhook event
        """
        return WhatsAppWebhookEvent(
            event=webhook_data.get("event", "unknown"),
            instance=webhook_data.get("instance", self.instance_name),
            data=webhook_data.get("data", {}),
            timestamp=datetime.utcnow()
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Import asyncio for sleep function
import asyncio