"""
Approval Step

Handles campaign approval, editing, and execution initiation.
"""

import asyncio
import logging
from typing import Dict, Any

from disparaai.models.whatsapp import WhatsAppMessage
from disparaai.services.session_service import SessionService
from disparaai.services.campaign_service import CampaignService

logger = logging.getLogger(__name__)


class ApprovalStep:
    """Handle campaign approval and execution."""
    
    def __init__(self):
        self.session_service = SessionService()
        self.campaign_service = CampaignService()
    
    async def handle(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle campaign approval and execution."""
        text = (message.text or "").lower().strip()
        
        if text in ["send", "enviar", "enviar agora"]:
            # Start campaign execution
            self.session_service.update_workflow_step(session, "executing_campaign")
            
            # Create campaign in database
            campaign_id = await self.campaign_service.create_campaign(session)
            self.session_service.store_campaign_data(session, "campaign_id", campaign_id)
            
            # Start background execution
            asyncio.create_task(self.campaign_service.execute_bulk_campaign(session))
            
            campaign_data = self.session_service.get_campaign_data(session)
            stats = campaign_data.get("stats", {})
            
            return f"""✅ *Enviando para {stats.get('valid_numbers', 0)} contatos...*

Digite "status" para acompanhar."""
        
        elif text in ["edit", "editar"]:
            # Check if we have copy options to edit or if this came from custom message
            campaign_data = self.session_service.get_campaign_data(session)
            has_copy_options = "copy_options" in campaign_data and campaign_data["copy_options"]
            
            if has_copy_options:
                # User has AI-generated options, go to copy selection
                self.session_service.update_workflow_step(session, "copy_selection")
                return """*Escolha uma opção:*

1, 2, 3 - Selecionar copy gerada
"personalizada" - Nova mensagem personalizada
"gerar copy: [descrição]" - Gerar novas opções"""
            else:
                # No copy options, go back to post-CSV options
                self.session_service.update_workflow_step(session, "csv_processed")
                stats = campaign_data.get("stats", {})
                total_numbers = stats.get("valid_numbers", 0)
                
                return f"""*Editando campanha para {total_numbers} contatos:*

🤖 *"gerar copy: [descrição]"* - Copy personalizada com IA
📤 *"enviar direto"* - Mensagem simples

*Ou envie uma imagem para copy automática*"""
        
        else:
            return """Por favor, confirme sua escolha:

Digite *"ENVIAR"* para iniciar a campanha
Digite *"EDITAR"* para modificar a mensagem

O que gostaria de fazer?"""
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "awaiting_approval"