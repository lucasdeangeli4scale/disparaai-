"""
Copy Generation Step

Handles AI-powered copy generation with structured output.
Creates 3 copy options with different styles and integrates image context if available.
"""

import logging
from typing import Dict, Any

from disparaai.models.copy_generation_request import CopyGenerationRequest
from disparaai.agents.copy_generation_agent import CopyGenerationAgent
from disparaai.agents.image_analysis_agent import ImageAnalysisAgent

logger = logging.getLogger(__name__)


class CopyGenerationStep:
    """Handle AI copy generation with contextual analysis."""
    
    def __init__(self):
        self.copy_agent_factory = CopyGenerationAgent()
        self.image_agent_factory = ImageAnalysisAgent()
    
    async def handle(self, request: CopyGenerationRequest) -> str:
        """Generate 3 copy options using structured output."""
        
        try:
            # Build structured context from request
            campaign_data = request.session_data["campaign_data"]
            stats = campaign_data["stats"]
            
            # VALIDATE: Context must exist for copy generation
            if not ("image_file_info" in campaign_data or "text_context" in campaign_data):
                return """❌ *Erro: Contexto Necessário*

Copy com IA sempre precisa de contexto para ser eficaz.

*Opções disponíveis:*
📸 Envie uma imagem do seu produto/serviço
📝 Digite uma descrição detalhada da sua campanha
📝 Digite *"personalizada"* para escrever sua própria mensagem

*Qual prefere?*"""
            
            # Generate campaign context
            context = self.copy_agent_factory.generate_campaign_context(stats)
            
            # Add specific context based on what exists
            image_context = None
            text_context = None
            context_type = None
            
            if "image_file_info" in campaign_data:
                image_context = self.image_agent_factory.analyze_image_for_copy(
                    campaign_data["image_file_info"]
                )
                context_type = "image"
            elif "text_context" in campaign_data:
                text_context = campaign_data["text_context"]
                context_type = "text"
            
            # Generate structured copy options with appropriate context
            copy_options_data = self.copy_agent_factory.generate_copy_options(
                context, image_context, text_context
            )
            
            # Store structured data in session
            request.session_data["campaign_data"]["copy_options"] = [
                option.message for option in copy_options_data.options
            ]
            request.session_data["campaign_data"]["copy_styles"] = [
                option.style for option in copy_options_data.options
            ]
            request.session_data["workflow_step"] = "copy_selection"
            
            # Format response for user with context-aware note
            context_note = ""
            if context_type == "image":
                context_note = " (baseadas na análise da sua imagem)"
            elif context_type == "text":
                context_note = " (baseadas na sua descrição)"
            
            formatted_response = f"""*3 opções para {stats['valid_numbers']} contatos:*

*1: {copy_options_data.options[0].style}*
{copy_options_data.options[0].message}
📤 *"enviar 1"* - Envio direto

*2: {copy_options_data.options[1].style}*
{copy_options_data.options[1].message}
📤 *"enviar 2"* - Envio direto

*3: {copy_options_data.options[2].style}*
{copy_options_data.options[2].message}
📤 *"enviar 3"* - Envio direto

*Ou digite: 1, 2, 3 para editar ou "personalizada"*"""
            
            return formatted_response
            
        except Exception as e:
            logger.error(f"Error in structured copy generation: {str(e)}", exc_info=True)
            # Fallback to retry options
            return """❌ *Erro na geração*

*Digite "personalizada" para continuar*"""
    
    def get_step_name(self) -> str:
        """Get step identifier."""
        return "generating_copy"