"""
Custom Message Step

Handles user-provided custom message input for campaigns.
Follows the established step architecture pattern.
"""

import logging
from typing import Dict, Any

from disparaai.models.whatsapp import WhatsAppMessage
from disparaai.services.session_service import SessionService

logger = logging.getLogger(__name__)


class CustomMessageStep:
    """Handle custom message input following AGNO session state patterns."""
    
    def __init__(self):
        self.session_service = SessionService()
    
    async def handle(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle custom message input."""
        custom_message = (message.text or "").strip()
        
        if not custom_message:
            return """Por favor, digite sua mensagem personalizada:
            
*Lembre-se de incluir {{name}} se quiser personalizar por nome*"""
        
        # Store in workflow session state (AGNO pattern)
        self.session_service.store_campaign_data(session, "selected_copy", custom_message)
        self.session_service.update_workflow_step(session, "awaiting_approval")
        
        campaign_data = self.session_service.get_campaign_data(session)
        stats = campaign_data.get("stats", {})
        total_numbers = stats.get("valid_numbers", 0)
        
        return f"""✅ *Mensagem definida para {total_numbers} contatos:*

"{custom_message}"

📤 *"enviar agora"* - Envio direto
✏️ *"ENVIAR"* ou *"EDITAR"* - Revisar primeiro"""
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "custom_message"