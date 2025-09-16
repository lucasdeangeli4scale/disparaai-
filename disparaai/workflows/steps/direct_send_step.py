"""
Direct Send Step

Handles immediate message sending without approval process.
Follows the established step architecture pattern.
"""

import asyncio
import logging
from typing import Dict, Any

from disparaai.models.whatsapp import WhatsAppMessage
from disparaai.services.session_service import SessionService
from disparaai.services.campaign_service import CampaignService

logger = logging.getLogger(__name__)


class DirectSendStep:
    """Handle direct send without customization."""
    
    def __init__(self):
        self.session_service = SessionService()
        self.campaign_service = CampaignService()
    
    async def handle(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle direct message sending."""
        direct_message = (message.text or "").strip()
        
        if not direct_message:
            return "Por favor, digite a mensagem que deseja enviar diretamente:"
        
        # Store and proceed directly to execution
        self.session_service.store_campaign_data(session, "selected_copy", direct_message)
        self.session_service.update_workflow_step(session, "executing_campaign")
        
        # Create campaign in database
        campaign_id = await self.campaign_service.create_campaign(session)
        self.session_service.store_campaign_data(session, "campaign_id", campaign_id)
        
        # Start background execution
        asyncio.create_task(self.campaign_service.execute_bulk_campaign(session))
        
        campaign_data = self.session_service.get_campaign_data(session)
        stats = campaign_data.get("stats", {})
        
        return f"""✅ *Enviando para {stats.get('valid_numbers', 0)} contatos...*

"{direct_message}"

Digite "status" para acompanhar."""
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "direct_send"