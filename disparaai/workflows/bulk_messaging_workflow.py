"""
DisparaAI Bulk Messaging Workflow using AGNO 2.0

Modern workflow implementation using AGNO's Workflow class with proper Step orchestration,
workflow_session_state management, and modular service integration.

Workflow Steps:
1. Welcome & CSV Upload
2. CSV Processing & Validation  
3. Optional Image Upload
4. AI Copy Generation (3 options)
5. User Copy Selection
6. Campaign Approval
7. Bulk Message Execution
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from agno.workflow.v2.workflow import Workflow

from disparaai.models.whatsapp import WhatsAppMessage, WhatsAppMedia
from disparaai.services.session_service import SessionService
from disparaai.services.file_processing_service import FileProcessingService
from disparaai.services.campaign_service import CampaignService
from disparaai.agents.conversational_agent import ConversationalAgent

logger = logging.getLogger(__name__)


class BulkMessagingWorkflow(Workflow):
    """
    AGNO 2.0 Workflow for WhatsApp bulk messaging with AI copywriting.
    
    Drop-in replacement for the original monolithic workflow with modern 
    AGNO patterns and modular architecture.
    """
    
    def __init__(self, **kwargs):
        """Initialize workflow with services and agents."""
        
        # Initialize services
        self.session_service = SessionService()
        self.file_service = FileProcessingService()
        self.campaign_service = CampaignService()
        
        # Initialize agents
        self.conversation_agent = ConversationalAgent()
        
        # Initialize AGNO Workflow
        super().__init__(
            name="DisparaAI Bulk Messaging Workflow",
            description="Complete workflow for WhatsApp bulk messaging campaigns with AI copywriting",
            workflow_session_state={},
            **kwargs
        )
    
    async def process_message(self, message: WhatsAppMessage) -> str:
        """
        Main entry point for processing WhatsApp messages.
        Maintains compatibility with original interface.
        """
        user_phone = message.from_user.phone
        
        try:
            # Initialize or get session
            session = self.session_service.initialize_session(user_phone)
            
            # Update workflow session state
            if user_phone not in self.workflow_session_state:
                self.workflow_session_state[user_phone] = session
            else:
                self.workflow_session_state[user_phone].update(session)
            
            # Add message to history
            self.session_service.add_message_to_history(
                session, message.text, message.message_type
            )
            
            # Route based on current workflow step
            current_step = session["workflow_step"]
            
            if current_step == "welcome":
                return await self._handle_welcome_step(message, session)
            elif current_step == "awaiting_csv":
                from disparaai.workflows.steps.csv_upload_step import CSVUploadStep
                step = CSVUploadStep()
                return await step.handle(message, session)
            elif current_step == "csv_processed":
                from disparaai.workflows.steps.post_csv_options_step import PostCSVOptionsStep
                step = PostCSVOptionsStep()
                return await step.handle(message, session)
            elif current_step == "generating_copy":
                # Check if background generation is in progress
                # If user sends message while generating, provide status
                return """🤖 *Gerando copy com IA...*

Sua solicitação está sendo processada em background.

*As opções personalizadas serão enviadas automaticamente em alguns segundos!*

*Aguarde ou digite "status" para mais informações.*"""
            elif current_step == "copy_selection":
                from disparaai.workflows.steps.copy_selection_step import CopySelectionStep
                step = CopySelectionStep()
                return await step.handle(message, session)
            elif current_step == "awaiting_approval":
                from disparaai.workflows.steps.approval_step import ApprovalStep
                step = ApprovalStep()
                return await step.handle(message, session)
            elif current_step == "executing_campaign":
                return await self._handle_execution_status(message, session)
            elif current_step == "custom_message":
                from disparaai.workflows.steps.custom_message_step import CustomMessageStep
                step = CustomMessageStep()
                return await step.handle(message, session)
            elif current_step == "direct_send":
                from disparaai.workflows.steps.direct_send_step import DirectSendStep
                step = DirectSendStep()
                return await step.handle(message, session)
            else:
                # Fallback to conversational agent
                agent = self.conversation_agent.create_agent()
                response = agent.run(message.text or "User sent media", user_id=user_phone)
                return response.content
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return "Desculpe, encontrei um erro técnico. Tente novamente."
    
    async def _handle_welcome_step(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle initial user contact and guide to CSV upload."""
        from disparaai.workflows.steps.welcome_step import WelcomeStep
        
        step = WelcomeStep()
        return await step.handle(message, session)
    
    
    async def _handle_execution_status(self, message: WhatsAppMessage, session: Dict[str, Any]) -> str:
        """Handle status requests during campaign execution."""
        text = (message.text or "").lower().strip()
        
        campaign_data = self.session_service.get_campaign_data(session)
        progress = campaign_data.get("progress", {})
        stats = campaign_data.get("stats", {})
        is_completed = progress.get('sent', 0) >= stats.get('valid_numbers', 0)
        
        if "status" in text:
            return f"""*Atualização do Status da Campanha:*

• Total de contatos: {stats.get('valid_numbers', 0)}
• Mensagens enviadas: {progress.get('sent', 0)}
• Mensagens entregues: {progress.get('delivered', 0)}
• Mensagens falharam: {progress.get('failed', 0)}

*Status:* {"Concluída" if is_completed else "Em Progresso"}

{("Campanha concluída! Você pode iniciar uma nova campanha agora." if is_completed else "A campanha está executando com intervalos de 1 segundo entre mensagens.")}"""
        
        elif is_completed:
            # Campaign is complete, reset for new conversation
            self.session_service.reset_workflow(session)
            return await self._handle_welcome_step(message, session)
        
        else:
            return """Sua campanha está executando atualmente.

Digite *"status"* para verificar o progresso a qualquer momento.

Vou te notificar quando a campanha for concluída!"""
    
    
    def get_workflow_status(self, user_phone: str) -> Dict[str, Any]:
        """Get workflow status for debugging."""
        return self.session_service.get_workflow_status(user_phone)
    
    async def close(self):
        """Clean up resources."""
        await self.file_service.close()
        await self.campaign_service.close()