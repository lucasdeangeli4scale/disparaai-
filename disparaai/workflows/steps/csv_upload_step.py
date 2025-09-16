"""
CSV Upload Step

Handles spreadsheet file upload, validation, and phone number extraction.
Processes CSV/Excel files and provides statistics about extracted contacts.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from disparaai.models.whatsapp import WhatsAppMessage
from disparaai.services.file_processing_service import FileProcessingService

logger = logging.getLogger(__name__)


class CSVUploadStep:
    """Handle CSV/Excel file upload and processing."""
    
    def __init__(self):
        self.file_service = FileProcessingService()
    
    async def handle(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle spreadsheet file upload using base64 from Evolution API webhook."""
        
        if message.message_type != "document" or not message.media:
            return """Por favor, envie uma planilha com números de telefone.

*Requisitos:*
• Formatos aceitos: Excel ou planilha comum
• Deve conter números de telefone
• Tamanho máximo: 10MB

Envie seu arquivo para continuar!"""
        
        try:
            # Process CSV upload
            processed_csv = await self.file_service.process_csv_upload(message.media)
            
            # Store campaign data in session
            session["campaign_data"] = {
                "csv_file_info": processed_csv.file_info,
                "phone_numbers": processed_csv.phone_numbers,  
                "stats": processed_csv.stats,
                "created_at": datetime.utcnow().isoformat()
            }
            session["workflow_step"] = "csv_processed"
            
            # Generate response with statistics
            stats_summary = self.file_service.get_file_stats_summary(processed_csv.stats)
            
            total_numbers = processed_csv.stats.get("valid_numbers", 0)
            
            response = f"""✅ *{total_numbers} contatos carregados*

🤖 *"gerar copy: [descrição]"* - Copy personalizada com IA  
📤 *"enviar direto"* - Mensagem simples

*Ou envie uma imagem para copy automática*"""
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}", exc_info=True)
            return f"Erro ao processar planilha: {str(e)}\n\nTente enviar o arquivo novamente."
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "awaiting_csv"