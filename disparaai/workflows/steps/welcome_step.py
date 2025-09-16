"""
Welcome Step

Handles initial user contact and guides users to start a new campaign.
Provides instructions for CSV upload and system introduction.
"""

import logging
from typing import Dict, Any

from disparaai.models.whatsapp import WhatsAppMessage

logger = logging.getLogger(__name__)


class WelcomeStep:
    """Handle welcome and initial campaign setup."""
    
    async def handle(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle initial user contact and guide to CSV upload."""
        text = (message.text or "").lower().strip()
        
        # Check for campaign start commands
        start_keywords = [
            "hi", "hello", "start", "campaign", "bulk", "begin", "new",
            "oi", "olá", "iniciar", "campanha", "comecar", "começar", "novo", "nova"
        ]
        
        if any(cmd in text for cmd in start_keywords):
            session["workflow_step"] = "awaiting_csv"
            
            return """Olá! Sou a DisparaAI, sua assistente para mensagens em massa.

Para começar, envie uma planilha com sua lista de contatos.

*Requisitos da planilha:*
• Deve conter números de telefone (coluna: 'phone', 'number', 'telefone', etc.)
• Formatos aceitos: Excel ou planilha comum
• Tamanho máximo: 10MB

Envie seu arquivo quando estiver pronto!"""
        
        # Handle direct CSV upload without greeting
        elif message.message_type == "document" and message.media:
            session["workflow_step"] = "awaiting_csv"
            # Import here to avoid circular imports
            from .csv_upload_step import CSVUploadStep
            csv_step = CSVUploadStep()
            return await csv_step.handle(message, session)
        
        # Default welcome message
        else:
            return """Olá! Sou a DisparaAI, sua assistente para mensagens em massa.

Posso ajudar você a enviar mensagens personalizadas do WhatsApp para múltiplos contatos.

Digite 'iniciar campanha' ou envie uma planilha para começar!"""
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "welcome"