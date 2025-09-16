"""
Post CSV Options Step

Handles user options after CSV processing with 3 flexible paths:
1. Custom message (user writes their own)
2. AI copy generation (3 options)
3. Direct send (immediate execution)

Follows the established step architecture pattern.
"""

import logging
from typing import Dict, Any

from disparaai.models.whatsapp import WhatsAppMessage
from disparaai.services.session_service import SessionService
from disparaai.services.file_processing_service import FileProcessingService
from disparaai.services.background_copy_service import BackgroundCopyService

logger = logging.getLogger(__name__)


class PostCSVOptionsStep:
    """Enhanced post-CSV handler with 3 flexible paths."""
    
    def __init__(self):
        self.session_service = SessionService()
        self.file_service = FileProcessingService()
        self.background_copy_service = BackgroundCopyService()
    
    def _is_custom_message_intent(self, text: str) -> bool:
        """Natural language intent detection for custom messages."""
        custom_keywords = ["personalizada", "minha mensagem", "escrever", "personalizar", "customizar"]
        return any(keyword in text for keyword in custom_keywords)

    def _is_direct_send_intent(self, text: str) -> bool:
        """Natural language intent detection for direct sending."""
        direct_keywords = ["enviar direto", "direto", "imediato", "sem personalização", "envio direto"]
        return any(keyword in text for keyword in direct_keywords)

    def _is_ai_copy_intent(self, text: str) -> bool:
        """Natural language intent detection for AI copy generation."""
        ai_keywords = ["gerar copy", "gerar", "ai", "inteligência artificial", "criar copy", "automático"]
        return any(keyword in text for keyword in ai_keywords)
    
    def _extract_context_from_command(self, text: str) -> str:
        """Extract context from 'gerar copy: [context]' format."""
        # Look for patterns like "gerar copy: context description"
        text_lower = text.lower()
        if "gerar copy:" in text_lower:
            # Extract everything after "gerar copy:"
            parts = text.split(":", 1)
            if len(parts) > 1:
                context = parts[1].strip()
                if len(context) > 5:  # Minimum viable context
                    return context
        return None
    
    def _has_inline_context(self, text: str) -> bool:
        """Check if text contains inline context for AI copy generation."""
        return self._extract_context_from_command(text) is not None
    
    def _has_context_for_ai_copy(self, session: Dict[str, Any]) -> bool:
        """Check if sufficient context exists for AI copy generation."""
        campaign_data = self.session_service.get_campaign_data(session)
        return ("image_file_info" in campaign_data or 
                "text_context" in campaign_data)
    
    def _request_context_for_ai_copy(self, session: Dict[str, Any]) -> str:
        """Request context for AI copy generation."""
        campaign_data = self.session_service.get_campaign_data(session)
        stats = campaign_data.get("stats", {})
        total_numbers = stats.get("valid_numbers", 0)
        
        return f"""🤖 *Geração de Copy com IA*

Para criar mensagens personalizadas e eficazes para seus {total_numbers} contatos, **PRECISO** de contexto sobre sua campanha.

*Escolha uma opção:*

📸 *Envie uma imagem* - Do seu produto, serviço ou promoção
📝 *Digite uma descrição* - Descreva seu negócio, produto ou objetivo da campanha

*Exemplo de descrição:*
"Sou dentista e quero promover limpeza dental com 20% desconto para novos pacientes"

*Sem contexto, não posso gerar copy eficaz. Se não quiser fornecer contexto, escolha uma das outras opções do menu anterior.*

*Envie sua imagem ou digite sua descrição:*"""
    
    async def handle(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle user options after spreadsheet processing."""
        text = (message.text or "").lower().strip()
        
        # Handle image upload for AI copy context
        if message.message_type == "image" and message.media:
            try:
                # Process image upload
                processed_image = await self.file_service.process_image_upload(message.media)
                
                # Store image data in session
                self.session_service.store_campaign_data(session, "image_file_info", processed_image.file_info)
                self.session_service.store_campaign_data(session, "context_type", "image")
                self.session_service.update_workflow_step(session, "generating_copy")
                
                # Get user phone for background generation
                user_phone = session.get("user_phone")
                
                # Trigger background copy generation immediately
                await self.background_copy_service.trigger_background_copy_generation(user_phone, session)
                
                # No immediate response - background service will handle all communication
                return None
                
            except Exception as e:
                logger.error(f"Error processing image: {str(e)}", exc_info=True)
                return f"""❌ *Erro ao processar imagem*

{str(e)}

*Opções:*
• Tente enviar a imagem novamente
• Ou digite uma descrição do seu produto/serviço"""
        
        # Smart intent detection (no regex)
        if self._is_custom_message_intent(text):
            self.session_service.update_workflow_step(session, "custom_message")
            return """📝 *Digite sua mensagem:*

*Use {{name}} para personalização*"""
        
        elif self._is_direct_send_intent(text):
            self.session_service.update_workflow_step(session, "direct_send") 
            return """📤 *Digite mensagem para envio direto:*"""
        
        elif self._is_ai_copy_intent(text):
            # Check for inline context first (smart detection)
            inline_context = self._extract_context_from_command(text)
            if inline_context:
                # Store inline context and proceed directly to copy generation
                self.session_service.store_campaign_data(session, "text_context", inline_context)
                self.session_service.store_campaign_data(session, "context_type", "text")
                self.session_service.update_workflow_step(session, "generating_copy")
                
                # Get user phone for background generation
                user_phone = session.get("user_phone")
                
                # Trigger background copy generation immediately
                await self.background_copy_service.trigger_background_copy_generation(user_phone, session)
                
                return f"""✅ *Contexto recebido!*

🤖 Gerando copy personalizada baseada em: "{inline_context[:80]}{'...' if len(inline_context) > 80 else ''}"

*As 3 opções serão enviadas em alguns segundos!*"""
            
            # Check if we already have context for AI copy generation
            elif self._has_context_for_ai_copy(session):
                # We have context, proceed to copy generation
                self.session_service.update_workflow_step(session, "generating_copy")
                
                # Get user phone for background generation
                user_phone = session.get("user_phone")
                
                # Trigger background copy generation immediately
                await self.background_copy_service.trigger_background_copy_generation(user_phone, session)
                
                # No immediate response - background service will handle all communication
                return None
            else:
                # No context, request it
                return self._request_context_for_ai_copy(session)
        
        # Handle text description for AI copy context
        elif text and len(text.strip()) > 10 and not any(cmd in text for cmd in ["status", "progress", "stats"]):
            # This looks like a text description for context
            self.session_service.store_campaign_data(session, "text_context", text)
            self.session_service.store_campaign_data(session, "context_type", "text")
            self.session_service.update_workflow_step(session, "generating_copy")
            
            # Get user phone for background generation
            user_phone = session.get("user_phone")
            
            # Trigger background copy generation immediately
            await self.background_copy_service.trigger_background_copy_generation(user_phone, session)
            
            # No immediate response - background service will handle all communication
            return None
        
        # Handle skip option - redirect to manual options instead of generic copy
        elif "pular" in text:
            return """⏭️ *Pular Copy com IA*

Se não quiser fornecer contexto, você tem outras opções:

📝 Digite *"personalizada"* - Escrever sua própria mensagem
📤 Digite *"enviar direto"* - Para envio imediato com mensagem simples

*Copy com IA SEMPRE precisa de contexto para ser eficaz.*

*O que prefere fazer?*"""
        
        
        # Handle status request
        elif any(cmd in text for cmd in ["status", "progress", "stats"]):
            campaign_data = self.session_service.get_campaign_data(session)
            stats = campaign_data.get("stats", {})
            return f"""*Status da Campanha:*

• Números válidos: {stats.get('valid_numbers', 0)}
• Países: {', '.join(stats.get('countries', {}).keys()) if stats.get('countries') else 'Nenhum'}
• Pronto para próximo passo

*Escolha uma opção:*
📝 Digite *"personalizada"* - Escrever sua própria mensagem
🤖 Digite *"gerar copy"* - Criar copy com IA (3 opções)  
📤 Digite *"enviar direto"* - Envio imediato sem personalização"""
        
        # Show enhanced options menu
        else:
            campaign_data = self.session_service.get_campaign_data(session)
            stats = campaign_data.get("stats", {})
            total_numbers = stats.get("valid_numbers", 0)
            
            return f"""✅ *{total_numbers} contatos carregados*

🤖 *"gerar copy: [descrição]"* - Copy personalizada com IA  
📤 *"enviar direto"* - Mensagem simples

*Ou envie uma imagem para copy automática*"""
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "post_csv_options"