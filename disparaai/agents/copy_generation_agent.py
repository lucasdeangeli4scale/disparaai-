"""
Copy Generation Agent

Specialized AGNO agent for creating AI-powered copy options for WhatsApp bulk messaging.
Generates structured copy with different styles: Professional, Friendly, and Promotional.
"""

import os
import logging
from typing import Dict, Any

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude

from disparaai.models.copy_generation import CopyOptions

logger = logging.getLogger(__name__)


class CopyGenerationAgent:
    """Specialized agent for generating marketing copy with structured output."""
    
    def __init__(self):
        self._agent = None
    
    def _get_ai_model(self):
        """Get AI model based on available API keys."""
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIChat(id="gpt-4o-mini")
        elif os.getenv("ANTHROPIC_API_KEY"):
            return Claude(id="claude-3-haiku-20240307")
        else:
            raise ValueError("No AI API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
    def create_agent(self) -> Agent:
        """Create specialized agent for copy generation with structured output."""
        if self._agent is None:
            self._agent = Agent(
                name="DisparaAI Copy Generator",
                agent_id="disparaai-copy-generator",
                role="AI copywriter specialist for WhatsApp bulk messaging",
                model=self._get_ai_model(),
                response_model=CopyOptions,  # Structured output
                instructions=[
                    "Você é um especialista em copywriting para WhatsApp",
                    "Gere sempre 3 opções distintas de mensagem",
                    "Use os estilos: Profissional, Amigável, e Promocional",
                    "Inclua sempre o placeholder {{name}} para personalização",
                    "Mantenha mensagens concisas e com call-to-action claro",
                    "Use formatação WhatsApp: *negrito*, _itálico_, não use ###",
                    "Baseie-se no contexto fornecido para relevância"
                ],
                show_tool_calls=False,
                markdown=False
            )
        return self._agent
    
    def generate_copy_options(self, context: str, image_context: str = None, text_context: str = None) -> CopyOptions:
        """Generate 3 copy options based on context and optional image/text analysis.
        
        Args:
            context: Campaign context (stats, audience info)
            image_context: Optional image analysis results
            text_context: Optional business/campaign description
        """
        try:
            agent = self.create_agent()
            
            # Build context prompt
            context_prompt = f"""Gere 3 opções de copy para campanha WhatsApp:

CONTEXTO DA CAMPANHA:
{context}

REQUISITOS:
- 3 estilos diferentes: Profissional, Amigável, Promocional
- Incluir placeholder {{{{name}}}} para personalização
- Call-to-action claro em cada mensagem
- Formatação WhatsApp compatível (*negrito*, _itálico_)
- Mensagens em português brasileiro"""

            # Add image context if available
            if image_context:
                context_prompt += f"\n\nCONTEXTO DA IMAGEM:\n{image_context}\n\nUse estas informações para criar mensagens mais relevantes e contextualizadas."
            
            # Add text context if available
            if text_context:
                context_prompt += f"\n\nDESCRIÇÃO DO NEGÓCIO/CAMPANHA:\n{text_context}\n\nUse esta descrição para criar mensagens altamente personalizadas e relevantes para o negócio."
            
            # Generate structured copy options
            response = agent.run(context_prompt)
            return response.content  # This is a CopyOptions object
            
        except Exception as e:
            logger.error(f"Error generating copy options: {str(e)}", exc_info=True)
            raise
    
    def generate_campaign_context(self, stats: Dict[str, Any]) -> str:
        """Generate campaign context string from statistics."""
        countries_text = ', '.join(stats['countries'].keys()) if stats['countries'] else 'Global'
        
        return f"""- Destinatários: {stats['valid_numbers']} contatos
- Países: {countries_text}"""