"""
Campaign Service

Business logic for managing WhatsApp bulk messaging campaigns.
Handles campaign creation, execution coordination, and status tracking.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from disparaai.models.campaign import CampaignStatus, PhoneNumber
from disparaai.database.connection import db_manager
from disparaai.database.models import Campaign as DBCampaign, PhoneNumber as DBPhoneNumber
from disparaai.integrations.evolution_api import EvolutionAPI

logger = logging.getLogger(__name__)


class CampaignService:
    """Business service for campaign management."""
    
    def __init__(self):
        self.evolution_api = EvolutionAPI()
    
    async def create_campaign(self, session_data: Dict[str, Any]) -> str:
        """Create campaign record in database."""
        try:
            campaign_data = session_data["campaign_data"]
            user_phone = session_data.get("user_phone", "unknown")
            
            with db_manager.get_session() as db_session:
                # Get file info (no URLs needed - store data directly)
                csv_file_info = campaign_data.get("csv_file_info", {})
                image_file_info = campaign_data.get("image_file_info", {})
                
                # Create campaign with direct file storage
                campaign = DBCampaign(
                    user_phone=user_phone,
                    status=CampaignStatus.PROCESSING,
                    message_content=campaign_data.get("selected_copy"),
                    
                    # CSV file storage (base64 data stored directly)  
                    csv_file_data=csv_file_info.get("file_data"),
                    csv_filename=csv_file_info.get("filename"),
                    csv_mime_type=csv_file_info.get("mime_type"),
                    csv_size_bytes=csv_file_info.get("size_bytes"),
                    
                    # Image file storage (base64 data stored directly)
                    image_file_data=image_file_info.get("file_data"),
                    image_filename=image_file_info.get("filename"),
                    image_mime_type=image_file_info.get("mime_type"),
                    image_size_bytes=image_file_info.get("size_bytes"),
                    image_width=image_file_info.get("image_width"),
                    image_height=image_file_info.get("image_height"),
                    
                    total_recipients=campaign_data["stats"]["valid_numbers"]
                )
                db_session.add(campaign)
                db_session.flush()
                
                # Add phone numbers
                for phone in campaign_data["phone_numbers"]:
                    if phone.is_valid:
                        db_phone = DBPhoneNumber(
                            campaign_id=campaign.id,
                            raw=phone.raw,
                            formatted=phone.formatted,
                            country_code=phone.country_code,
                            is_valid=phone.is_valid
                        )
                        db_session.add(db_phone)
                
                db_session.commit()
                return str(campaign.id)
                
        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}", exc_info=True)
            return "temp_campaign_id"
    
    async def execute_bulk_campaign(self, session_data: Dict[str, Any]) -> None:
        """Execute bulk message sending with progress updates."""
        try:
            campaign_data = session_data["campaign_data"]
            phone_numbers = [p for p in campaign_data["phone_numbers"] if p.is_valid]
            message_content = campaign_data["selected_copy"]
            
            # Initialize progress tracking
            progress = {"sent": 0, "delivered": 0, "failed": 0}
            campaign_data["progress"] = progress
            
            # Check if campaign has image
            has_image = "image_file_info" in campaign_data
            image_data = None
            image_filename = None
            image_file_info = None
            
            if has_image:
                image_file_info = campaign_data["image_file_info"]
                raw_image_data = image_file_info.get("file_data")  # Could be bytes or base64
                image_filename = image_file_info.get("filename", "image.jpg")
                
                # Ensure image_data is base64 string (Evolution API expects string)
                if isinstance(raw_image_data, bytes):
                    import base64
                    image_data = base64.b64encode(raw_image_data).decode('utf-8')
                elif isinstance(raw_image_data, str):
                    image_data = raw_image_data
                else:
                    logger.warning(f"Unexpected image data type: {type(raw_image_data)}")
                    has_image = False
            
            # Send messages with rate limiting
            for i, phone in enumerate(phone_numbers):
                try:
                    # Personalize message
                    personalized_message = message_content.replace("{{name}}", phone.raw)
                    
                    # Send message (with image if available)
                    if has_image and image_data:
                        await self.evolution_api.send_media_message(
                            phone.formatted,
                            media_data=image_data,
                            caption=personalized_message,
                            media_type="image",
                            filename=image_filename,
                            mimetype=image_file_info.get("image_mime_type", "image/jpeg")
                        )
                    else:
                        await self.evolution_api.send_text_message(
                            phone.formatted, 
                            personalized_message
                        )
                    
                    progress["sent"] += 1
                    progress["delivered"] += 1  # Assume delivered for now
                    
                    # Rate limiting: 1 second between messages
                    if i < len(phone_numbers) - 1:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(f"Failed to send to {phone.formatted}: {str(e)}")
                    progress["failed"] += 1
            
            # Campaign complete
            logger.info(f"Campaign completed: {progress}")
            
        except Exception as e:
            logger.error(f"Error in bulk execution: {str(e)}", exc_info=True)
    
    def get_campaign_status(self, campaign_id: str) -> Dict[str, Any]:
        """Get campaign status information."""
        try:
            with db_manager.get_session() as db_session:
                campaign = db_session.query(DBCampaign).filter_by(id=campaign_id).first()
                if campaign:
                    return {
                        "id": campaign.id,
                        "status": campaign.status,
                        "total_recipients": campaign.total_recipients,
                        "created_at": campaign.created_at,
                        "user_phone": campaign.user_phone
                    }
                return {"error": "Campaign not found"}
        except Exception as e:
            logger.error(f"Error getting campaign status: {str(e)}")
            return {"error": str(e)}
    
    async def close(self):
        """Clean up resources."""
        await self.evolution_api.close()