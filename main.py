"""
DisparaAI - WhatsApp Bulk Messaging System
Main application entry point using AGNO framework.
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from disparaai.workflows.bulk_messaging_workflow import BulkMessagingWorkflow
from disparaai.integrations.evolution_api import EvolutionAPI
from disparaai.models.whatsapp import WhatsAppWebhookEvent, WhatsAppMessage, WhatsAppUser, WhatsAppMedia
from disparaai.database.connection import init_database, get_db_session
from disparaai.utils.base64_file_handler import Base64FileHandler as FileHandler
from disparaai.utils.logger import get_logger, setup_logging

# Load environment variables
load_dotenv()

# Setup logging
setup_logging(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    log_file=os.getenv('LOG_FILE', 'disparaai.log')
)
logger = get_logger(__name__)

# Suppress noisy loggers that might expose sensitive data
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Global workflow instance
bulk_messaging_workflow = None
evolution_api = None
file_handler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global bulk_messaging_workflow, evolution_api, file_handler
    
    # Startup
    logger.info("🚀 Starting DisparaAI...")
    
    # Initialize database (skip if tables already exist)
    try:
        init_database()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization skipped: {e}")
        logger.info("✅ Assuming tables already exist from manual setup")
    
    # Initialize services
    bulk_messaging_workflow = BulkMessagingWorkflow()
    evolution_api = EvolutionAPI()
    file_handler = FileHandler()
    await file_handler.initialize()  # Initialize file handler
    
    # Set webhook (optional - can be done manually)
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        try:
            await evolution_api.set_webhook(
                webhook_url + "/webhook/evolution",
                events=["MESSAGES_UPSERT", "SEND_MESSAGE", "CONNECTION_UPDATE"]
            )
            logger.info(f"✅ Webhook configured: {webhook_url}/webhook/evolution")
        except Exception as e:
            logger.error(f"⚠️ Webhook setup failed: {e}")
    
    logger.info("✅ DisparaAI started successfully!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down DisparaAI...")
    if bulk_messaging_workflow:
        await bulk_messaging_workflow.close()
    if evolution_api:
        await evolution_api.close()
    if file_handler:
        await file_handler.close()
    logger.info("✅ Shutdown complete!")


# Initialize FastAPI app
app = FastAPI(
    title="DisparaAI - WhatsApp Bulk Messaging",
    description="AI-powered WhatsApp bulk messaging system built with AGNO framework",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "DisparaAI - WhatsApp Bulk Messaging System",
        "status": "healthy",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    try:
        # Check Evolution API connection
        status = await evolution_api.get_instance_status()
        
        return {
            "status": "healthy",
            "database": "connected",
            "evolution_api": "connected",
            "instance_status": status.get("state", "unknown")
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.post("/webhook/evolution")
async def evolution_webhook(request: Request):
    """
    Webhook endpoint for Evolution API events.
    Handles incoming messages and status updates.
    """
    try:
        # Verify webhook token (optional security)
        webhook_token = os.getenv("WHATSAPP_WEBHOOK_TOKEN")
        if webhook_token:
            auth_header = request.headers.get("authorization")
            if not auth_header or auth_header != f"Bearer {webhook_token}":
                raise HTTPException(status_code=401, detail="Invalid webhook token")
        
        # Parse webhook data
        webhook_data = await request.json()
        event = evolution_api.process_webhook_event(webhook_data)
        
        # Log webhook event received
        logger.info(f"🔄 Webhook event received: {event.event} from instance {event.instance}")
        
        # Handle different event types
        if event.event == "messages.upsert":
            await handle_incoming_message(event)
        elif event.event == "send.message":
            await handle_message_status_update(event)
        elif event.event == "connection.update":
            await handle_connection_update(event)
        else:
            logger.warning(f"⚠️ Unhandled webhook event type: {event.event}")
        
        return {"status": "success", "event": event.event}
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def handle_incoming_message(event: WhatsAppWebhookEvent):
    """Handle incoming WhatsApp messages."""
    try:
        # Handle direct message data from Evolution API webhook
        if "messages" in event.data:
            message_data = event.data["messages"][0]
        else:
            message_data = event.data  # Direct message data
        
        # Handle testing mode: only process messages from the owner phone number
        testing_mode = os.getenv("TESTING_MODE", "false").lower() == "true"
        owner_phone = os.getenv("TEST_OWNER_PHONE")
        is_from_me = message_data.get("key", {}).get("fromMe", False)
        
        # Extract phone number for testing mode filtering
        remote_jid = message_data.get("key", {}).get("remoteJid", "")
        phone_number = remote_jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
        
        logger.info(f"🔍 Message filtering - TESTING_MODE: {testing_mode}, phone: {phone_number}, owner: {owner_phone}, fromMe: {is_from_me}")
        
        if testing_mode:
            if not owner_phone:
                logger.warning("⚠️ TESTING_MODE enabled but TEST_OWNER_PHONE not configured")
                return
            # In testing mode, only accept messages from the owner phone number
            if phone_number != owner_phone:
                logger.info(f"⏭️ Skipping message from {phone_number} (testing mode - only accepting {owner_phone})")
                return
            logger.info(f"✅ Processing message from owner {phone_number} (testing mode)")
        else:
            # In normal mode, skip messages fromMe=true (sent by the bot)
            if is_from_me:
                logger.info("⏭️ Skipping message fromMe=true (normal mode)")
                return
            logger.info("✅ Processing message fromMe=false (normal mode)")
        
        # Debug: Log FULL webhook payload for debugging (with base64 sanitization)
        from disparaai.utils.logger import safe_json_dumps
        logger.info(f"🔍 FULL WEBHOOK PAYLOAD: {safe_json_dumps(message_data, indent=2)}")
        
        # Debug: Log media fields specifically for troubleshooting
        if message_data.get("message"):
            media_url = message_data.get("message", {}).get("mediaUrl")
            media_base64 = message_data.get("message", {}).get("base64")
            logger.info(f"🔍 Media debug - mediaUrl: {'Present' if media_url else 'None'}, base64: {'Present' if media_base64 else 'None'}")
            
            # Log message types for debugging
            message_content = message_data.get("message", {})
            msg_types = [key for key in message_content.keys() if key.endswith("Message")]
            if msg_types:
                logger.info(f"🔍 Message types detected: {msg_types}")
                
            # Log document message details if present
            if "documentMessage" in message_content:
                doc_msg = message_content["documentMessage"]
                logger.info(f"🔍 Document details - fileName: {doc_msg.get('fileName')}, mimetype: {doc_msg.get('mimetype')}")
                logger.info(f"🔍 Document has base64: {'Yes' if doc_msg.get('base64') else 'No'}")
        
        # Parse message
        try:
            whatsapp_message = parse_whatsapp_message(message_data)
        except ValueError as e:
            logger.error(f"⚠️ Skipping message with invalid phone number: {e}")
            return
        except Exception as e:
            logger.error(f"❌ Unexpected error parsing message: {e}")
            return
        
        # Log incoming message (especially for Instagram messages)
        logger.info(f"📱 Message received from {whatsapp_message.from_user.phone} ({whatsapp_message.from_user.name}): {whatsapp_message.text[:100] if whatsapp_message.text else 'Media message'}")
        
        # Process with bulk messaging workflow (AGNO Workflow architecture)
        response_text = await bulk_messaging_workflow.process_message(whatsapp_message)
        
        # Only send response if there is one (background services handle their own messaging)
        if response_text is not None:
            # Log response being sent
            logger.info(f"💬 Sending response to {whatsapp_message.from_user.phone}: {response_text[:100]}...")
            
            # Send response back
            await evolution_api.send_text_message(
                whatsapp_message.from_user.phone,
                response_text
            )
        else:
            # Background service is handling this message
            logger.info(f"🔄 Background service handling response for {whatsapp_message.from_user.phone}")
        
        logger.info(f"✅ Message processed successfully for {whatsapp_message.from_user.phone}")
        
    except Exception as e:
        logger.error(f"❌ Error handling incoming message: {str(e)}", exc_info=True)


async def handle_message_status_update(event: WhatsAppWebhookEvent):
    """Handle message delivery status updates."""
    try:
        # Update message status in database
        # Implementation would track delivery, read receipts, etc.
        logger.info(f"📊 Message status update: {event.data}")
        
    except Exception as e:
        logger.error(f"❌ Error handling status update: {str(e)}", exc_info=True)


async def handle_connection_update(event: WhatsAppWebhookEvent):
    """Handle WhatsApp connection status changes."""
    try:
        connection_state = event.data.get("state")
        logger.info(f"🔗 Connection state changed: {connection_state}")
        
        # Handle disconnections, QR code updates, etc.
        if connection_state == "close":
            logger.warning("⚠️ WhatsApp connection closed - may need to reconnect")
        elif connection_state == "open":
            logger.info("✅ WhatsApp connection established")
        
    except Exception as e:
        logger.error(f"❌ Error handling connection update: {str(e)}", exc_info=True)


def parse_whatsapp_message(message_data: dict) -> WhatsAppMessage:
    """Parse raw webhook message data into WhatsApp message model."""
    # Extract user info with validation
    remote_jid = message_data.get("key", {}).get("remoteJid", "")
    phone_number = remote_jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
    
    # Validate phone number is not empty
    if not phone_number.strip():
        raise ValueError(f"Invalid or empty phone number from remoteJid: {remote_jid}")
    
    user = WhatsAppUser(
        phone=phone_number,
        name=message_data.get("pushName")
    )
    
    # Extract message content
    message_content = message_data.get("message", {})
    text = None
    media = None
    message_type = "text"
    
    # Extract media URL or base64 from Evolution API webhook payload
    # Evolution API provides media via:
    # 1. message.mediaUrl (if external storage enabled)
    # 2. message.base64 (if webhookBase64 enabled)
    media_url = message_data.get("message", {}).get("mediaUrl")
    media_base64 = message_data.get("message", {}).get("base64")
    
    # Handle different message types
    if "conversation" in message_content:
        text = message_content["conversation"]
    elif "extendedTextMessage" in message_content:
        text = message_content["extendedTextMessage"].get("text")
    elif "documentMessage" in message_content:
        message_type = "document"
        doc_msg = message_content["documentMessage"]
        media = WhatsAppMedia(
            id=doc_msg.get("mediaKey", ""),
            mime_type=doc_msg.get("mimetype", ""),
            filename=doc_msg.get("fileName"),
            caption=doc_msg.get("caption"),
            url=media_url,
            base64=media_base64
        )
        text = doc_msg.get("caption")
    elif "imageMessage" in message_content:
        message_type = "image"
        img_msg = message_content["imageMessage"]
        media = WhatsAppMedia(
            id=img_msg.get("mediaKey", ""),
            mime_type=img_msg.get("mimetype", "image/jpeg"),
            filename="image.jpg",
            caption=img_msg.get("caption"),
            url=media_url,
            base64=media_base64
        )
        text = img_msg.get("caption")
    
    return WhatsAppMessage(
        id=message_data.get("key", {}).get("id", ""),
        from_user=user,
        message_type=message_type,
        text=text,
        media=media,
        timestamp=message_data.get("messageTimestamp", 0),
        is_from_me=message_data.get("key", {}).get("fromMe", False)
    )


# Optional: API endpoints for campaign management
@app.get("/campaigns")
async def list_campaigns(db=Depends(get_db_session)):
    """List all campaigns (for debugging/management)."""
    # Implementation would query campaigns from database
    return {"campaigns": []}


@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, db=Depends(get_db_session)):
    """Get specific campaign details."""
    # Implementation would fetch campaign details
    return {"campaign_id": campaign_id}


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )