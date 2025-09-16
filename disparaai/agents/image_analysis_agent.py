"""
Image Analysis Agent

Specialized AGNO agent for analyzing images to generate contextual copy.
Uses vision-capable models to extract marketing-relevant information from images.
"""

import base64
import logging
from typing import Dict, Any

from agno.agent import Agent
from agno.media import Image
from agno.models.openai import OpenAIChat

logger = logging.getLogger(__name__)


class ImageAnalysisAgent:
    """Specialized agent for analyzing images to provide copy context."""
    
    def __init__(self):
        self._agent = None
    
    def create_agent(self) -> Agent:
        """Create vision-capable agent for image analysis."""
        if self._agent is None:
            self._agent = Agent(
                name="DisparaAI Image Analyzer",
                agent_id="disparaai-image-analyzer",
                role="Image analysis specialist for marketing copy generation",
                model=OpenAIChat(id="gpt-4o-mini"),  # Vision-capable model
                instructions=[
                    "Você é um especialista em análise de imagens para criação de copy de marketing.",
                    "Analise a imagem fornecida e descreva detalhadamente em português brasileiro:",
                    "- Produtos ou serviços mostrados",
                    "- Público-alvo aparente da imagem",
                    "- Mood e atmosfera visual",
                    "- Cores predominantes e estilo",
                    "- Elementos que podem ser usados em copy de marketing",
                    "- Benefícios ou características visíveis",
                    "- Contexto ou cenário da imagem",
                    "Seja específico e detalhado para ajudar na criação de mensagens relevantes e contextualizadas."
                ],
                markdown=False
            )
        return self._agent
    
    def analyze_image_for_copy(self, image_file_info: Dict[str, Any]) -> str:
        """Analyze uploaded image to generate contextual copy using AGNO vision capabilities."""
        try:
            # Get image data
            image_data = image_file_info.get("file_data")
            if not image_data:
                return "Nenhuma informação específica da imagem disponível."
            
            # Convert image data to bytes if needed
            if isinstance(image_data, str):
                # Assume it's base64 encoded
                image_bytes = base64.b64decode(image_data)
            elif isinstance(image_data, bytes):
                image_bytes = image_data
            else:
                return "Formato de imagem não suportado para análise."
            
            # Create AGNO Image object with bytes content
            image_format = image_file_info.get("image_format", "jpeg").lower()
            agno_image = Image(content=image_bytes, format=image_format)
            
            # Analyze image using AGNO's native vision capabilities
            agent = self.create_agent()
            analysis_prompt = ("Analise esta imagem detalhadamente para criação de copy de marketing. "
                             "Forneça informações específicas e úteis que possam ser usadas para criar "
                             "mensagens de marketing personalizadas e relevantes.")
            
            response = agent.run(
                analysis_prompt,
                images=[agno_image]
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error analyzing image for copy: {str(e)}", exc_info=True)
            return "Erro ao analisar a imagem. Gerando copy sem contexto visual."
    
    def validate_image_support(self) -> bool:
        """Check if image analysis is supported (requires OpenAI with vision)."""
        try:
            import os
            return bool(os.getenv("OPENAI_API_KEY"))
        except Exception as e:
            logger.error(f"Error checking image support: {str(e)}")
            return False