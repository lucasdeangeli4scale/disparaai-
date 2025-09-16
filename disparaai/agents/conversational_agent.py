"""
Conversational Agent

Main conversational AGNO agent for DisparaAI workflow orchestration.
Handles general conversation and user guidance throughout the workflow.
"""

import os
import logging

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.storage.sqlite import SqliteStorage

logger = logging.getLogger(__name__)


class ConversationalAgent:
    """Main conversational agent for workflow guidance."""
    
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
        """Create main conversational agent."""
        if self._agent is None:
            self._agent = Agent(
                name="DisparaAI Assistant",
                agent_id="disparaai-conversation",
                role="WhatsApp bulk messaging assistant with AI copywriting",
                model=self._get_ai_model(),
                storage=SqliteStorage(
                    table_name="workflow_sessions",
                    db_file="./agno_workflow_sessions.db"
                ),
                instructions=[
                    "Você é a DisparaAI, uma assistente inteligente para mensagens em massa no WhatsApp.",
                    "Guie os usuários através do processo completo de criação de campanha passo a passo.",
                    "Sempre seja conversacional, amigável e forneça orientação clara em português brasileiro.",
                    "Forneça ajuda geral e orientação sobre o processo de campanha.",
                    "Sempre confirme ações antes de executar operações em massa.",
                    "IMPORTANTE: Use SOMENTE formatação suportada pelo WhatsApp:",
                    "- *texto* para negrito (asterisco antes e depois)",
                    "- _texto_ para itálico (underscore antes e depois)",
                    "- ~texto~ para tachado (til antes e depois)",
                    "- ```texto``` para monoespaçado (três acentos graves)",
                    "- - item para lista com hífen",
                    "- 1. item para lista numerada",
                    "- > texto para citação de bloco",
                    "- `código` para código embutido",
                    "NUNCA use ### para títulos, use *texto* em negrito. NUNCA use ** para negrito, use *texto*.",
                    "Seja conciso e evite formatação excessiva. Foque na clareza da comunicação.",
                    "NUNCA gere copy de marketing - isso é responsabilidade de agentes especializados."
                ],
                show_tool_calls=False,
                markdown=False,
                add_history_to_messages=True,
            )
        return self._agent
    
    def generate_response(self, message: str, user_id: str) -> str:
        """Generate conversational response."""
        try:
            agent = self.create_agent()
            response = agent.run(message, user_id=user_id)
            return response.content
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return "Desculpe, encontrei um erro técnico. Tente novamente."