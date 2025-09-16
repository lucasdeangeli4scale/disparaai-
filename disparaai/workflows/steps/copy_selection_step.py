"""
Copy Selection Step

Handles user selection of AI-generated copy options with direct send functionality.
"""

import asyncio
import logging
from typing import Dict, Any

from disparaai.models.whatsapp import WhatsAppMessage
from disparaai.services.session_service import SessionService
from disparaai.services.campaign_service import CampaignService

logger = logging.getLogger(__name__)


class CopySelectionStep:
    """Handle copy selection with direct send and edit options."""
    
    def __init__(self):
        self.session_service = SessionService()
        self.campaign_service = CampaignService()
    
    async def handle(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle user copy selection with direct send capability."""
        text = (message.text or "").strip()
        
        # Handle direct send commands (enviar 1, enviar 2, enviar 3)
        if text.lower().startswith("enviar ") and len(text.split()) == 2:
            try:
                option_num = text.split()[1]
                if option_num in ["1", "2", "3"]:
                    selected_index = int(option_num) - 1
                    campaign_data = self.session_service.get_campaign_data(session)
                    copy_options = campaign_data.get("copy_options", [])
                    
                    if selected_index < len(copy_options):
                        selected_copy = copy_options[selected_index]
                        self.session_service.store_campaign_data(session, "selected_copy", selected_copy)
                        
                        # Skip approval step - go directly to execution
                        self.session_service.update_workflow_step(session, "executing_campaign")
                        
                        # Create campaign in database
                        campaign_id = await self.campaign_service.create_campaign(session)
                        self.session_service.store_campaign_data(session, "campaign_id", campaign_id)
                        
                        # Start background execution
                        asyncio.create_task(self.campaign_service.execute_bulk_campaign(session))
                        
                        stats = campaign_data.get("stats", {})
                        
                        return f"""✅ *Campanha iniciada!*

Enviando para {stats.get('valid_numbers', 0)} contatos...

Digite "status" para acompanhar o progresso."""
            except:
                pass  # Fall through to regular handling
        
        # Handle regular selection (for editing)
        elif text in ["1", "2", "3"]:
            selected_index = int(text) - 1
            campaign_data = self.session_service.get_campaign_data(session)
            copy_options = campaign_data.get("copy_options", [])
            
            if selected_index < len(copy_options):
                selected_copy = copy_options[selected_index]
                self.session_service.store_campaign_data(session, "selected_copy", selected_copy)
                self.session_service.update_workflow_step(session, "awaiting_approval")
                
                return f"""*Opção {text} selecionada para edição:*

"{selected_copy}"

*Digite "ENVIAR" ou "EDITAR"*"""
        
        elif text.lower() in ["custom", "personalizada", "personalizado"]:
            self.session_service.update_workflow_step(session, "custom_message")
            return """📝 *Digite sua mensagem:*

*Use {{name}} para personalização*"""
        
        # Handle "gerar copy" from copy selection (redirect to post-CSV with context request)
        elif "gerar copy" in text.lower():
            self.session_service.update_workflow_step(session, "csv_processed")
            return """🤖 *Copy com IA precisa de contexto:*

*Digite:* "gerar copy: [descrição do seu negócio/produto]"
*Ou envie uma imagem* para copy automática

*Exemplo:* "gerar copy: sou dentista e ofereco 20% desconto em limpeza"""
        
        else:
            campaign_data = self.session_service.get_campaign_data(session)
            has_copy_options = "copy_options" in campaign_data and campaign_data["copy_options"]
            
            if has_copy_options:
                return """*Escolha uma opção:*

1, 2, 3 - Selecionar copy gerada
"personalizada" - Nova mensagem personalizada  
"gerar copy: [descrição]" - Gerar novas opções"""
            else:
                return """*Opções disponíveis:*

"personalizada" - Digite sua mensagem
"gerar copy: [descrição]" - Copy com IA"""
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "copy_selection"