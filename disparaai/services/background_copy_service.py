"""
Background Copy Generation Service

Handles immediate background copy generation without waiting for user response.
Integrates with existing session management and Evolution API for result delivery.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from disparaai.models.copy_generation_request import CopyGenerationRequest
from disparaai.services.session_service import SessionService
from disparaai.integrations.evolution_api import EvolutionAPI
from disparaai.workflows.steps.copy_generation_step import CopyGenerationStep

logger = logging.getLogger(__name__)


class BackgroundCopyService:
    """Service for immediate background copy generation."""
    
    def __init__(self):
        self.session_service = SessionService()
        self.evolution_api = EvolutionAPI()
        self.copy_generation_step = CopyGenerationStep()
        
        # Track active generation tasks to prevent duplicates
        self.active_generations = set()
    
    async def trigger_background_copy_generation(
        self, 
        user_phone: str, 
        session: Dict[str, Any]
    ) -> None:
        """
        Trigger copy generation in background immediately after confirmation message.
        
        Args:
            user_phone: User's phone number
            session: Current session data
        """
        # Prevent duplicate generations for the same user
        if user_phone in self.active_generations:
            logger.info(f"Copy generation already in progress for {user_phone}")
            return
        
        # Mark as active
        self.active_generations.add(user_phone)
        
        try:
            # Create task for background generation
            task = asyncio.create_task(
                self._generate_and_deliver_copy(user_phone, session)
            )
            
            # Don't await - this runs in background
            logger.info(f"🔄 Started background copy generation for {user_phone}")
            
        except Exception as e:
            # Remove from active set on error
            self.active_generations.discard(user_phone)
            logger.error(f"Failed to start background copy generation for {user_phone}: {e}")
    
    async def _generate_and_deliver_copy(
        self, 
        user_phone: str, 
        session: Dict[str, Any]
    ) -> None:
        """
        Generate copy in background and deliver results to user.
        
        Args:
            user_phone: User's phone number
            session: Current session data
        """
        try:
            # Send immediate confirmation to user based on context type
            generation_request = CopyGenerationRequest.from_session(
                user_phone=user_phone,
                session=session,
                request_id=f"bg_{user_phone}_{int(datetime.utcnow().timestamp())}"
            )
            
            if generation_request.context_type == "image":
                confirmation_msg = """✅ *Imagem recebida!*

🤖 Analisando sua imagem e gerando copy personalizada...

*As opções serão enviadas em alguns segundos!*"""
            elif generation_request.context_type == "text":
                text_preview = generation_request.text_context[:80] if generation_request.text_context else "descrição"
                text_preview += "..." if generation_request.text_context and len(generation_request.text_context) > 80 else ""
                confirmation_msg = f"""✅ *Descrição recebida!*

🤖 Gerando copy personalizada: "{text_preview}"

*As 3 opções serão enviadas em alguns segundos!*"""
            else:
                # This covers existing context scenarios
                confirmation_msg = """✅ *Contexto encontrado!*

🤖 Gerando copy personalizada com base no contexto existente...

*As 3 opções serão enviadas em alguns segundos!*"""
            
            await self.evolution_api.send_text_message(user_phone, confirmation_msg)
            
            logger.info(f"🤖 Generating copy for {user_phone}...")
            
            # Get fresh session data to ensure we have latest state
            current_session = self.session_service.initialize_session(user_phone)
            
            # Verify we're still in the right state (user might have moved on)
            if current_session.get("workflow_step") != "generating_copy":
                logger.info(f"⏭️ User {user_phone} moved to different step, canceling background generation")
                return
            
            # Use the generation request we already created for confirmation
            # (we already created it above for the confirmation message)
            
            # Validate context before proceeding
            if not generation_request.has_valid_context():
                logger.warning(f"❌ No valid context found for {user_phone}: {generation_request.get_context_summary()}")
                raise ValueError("No valid context for copy generation")
                
            logger.info(f"📝 Context: {generation_request.get_context_summary()}")
            
            # Generate copy using DTO interface
            result = await self.copy_generation_step.handle(generation_request)
            
            # Update session state to copy_selection (this is done in the step)
            # The step handles setting workflow_step = "copy_selection"
            
            # Deliver results immediately to user
            await self.evolution_api.send_text_message(user_phone, result)
            
            logger.info(f"✅ Copy generation completed and delivered to {user_phone}")
            
        except Exception as e:
            logger.error(f"❌ Background copy generation failed for {user_phone}: {e}", exc_info=True)
            
            # Send error message to user
            try:
                error_message = """❌ *Erro na geração*

*Digite "personalizada" para continuar* ou tente novamente com:
🤖 *"gerar copy: [descrição]"* - Nova tentativa
📤 *"enviar direto"* - Mensagem simples"""
                
                await self.evolution_api.send_text_message(user_phone, error_message)
                
                # Reset workflow step to allow retry
                current_session = self.session_service.initialize_session(user_phone)
                self.session_service.update_workflow_step(current_session, "csv_processed")
                
            except Exception as delivery_error:
                logger.error(f"Failed to send error message to {user_phone}: {delivery_error}")
        
        finally:
            # Always remove from active set
            self.active_generations.discard(user_phone)
    
    async def close(self):
        """Clean up resources."""
        await self.evolution_api.close()