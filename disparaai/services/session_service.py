"""
Session Service

Business logic for managing user session state and workflow progression.
Handles session initialization, state updates, and conversation history.
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionService:
    """Business service for session state management (Singleton)."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.user_sessions: Dict[str, Dict[str, Any]] = {}
            SessionService._initialized = True
    
    def initialize_session(self, user_phone: str) -> Dict[str, Any]:
        """Initialize or get existing user session."""
        if user_phone not in self.user_sessions:
            self.user_sessions[user_phone] = {
                "user_phone": user_phone,
                "workflow_step": "welcome",
                "campaign_data": {},
                "conversation_history": [],
                "last_interaction": datetime.utcnow()
            }
        
        # Update last interaction time
        self.user_sessions[user_phone]["last_interaction"] = datetime.utcnow()
        return self.user_sessions[user_phone]
    
    def get_session_data(self, user_phone: str) -> Dict[str, Any]:
        """Get session data for user."""
        return self.user_sessions.get(user_phone, {})
    
    def update_workflow_step(self, session: Dict[str, Any], step: str) -> None:
        """Update the current workflow step."""
        session["workflow_step"] = step
        session["last_interaction"] = datetime.utcnow()
    
    def add_message_to_history(self, session: Dict[str, Any], message_text: str, message_type: str) -> None:
        """Add message to conversation history."""
        session["conversation_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "user_message": message_text or "[Media]",
            "message_type": message_type
        })
    
    def store_campaign_data(self, session: Dict[str, Any], key: str, value: Any) -> None:
        """Store data in campaign_data section."""
        if "campaign_data" not in session:
            session["campaign_data"] = {}
        session["campaign_data"][key] = value
    
    def get_campaign_data(self, session: Dict[str, Any], key: str = None) -> Any:
        """Get campaign data by key or entire campaign_data."""
        campaign_data = session.get("campaign_data", {})
        if key:
            return campaign_data.get(key)
        return campaign_data
    
    def clear_session(self, user_phone: str) -> None:
        """Clear user session data."""
        if user_phone in self.user_sessions:
            del self.user_sessions[user_phone]
    
    def reset_workflow(self, session: Dict[str, Any]) -> None:
        """Reset workflow to welcome step for new campaigns."""
        session["workflow_step"] = "welcome"
        session["campaign_data"] = {}
        session["last_interaction"] = datetime.utcnow()
    
    def get_workflow_status(self, user_phone: str) -> Dict[str, Any]:
        """Get workflow status for debugging."""
        session = self.user_sessions.get(user_phone, {})
        return {
            "user_phone": user_phone,
            "workflow_step": session.get("workflow_step", "welcome"),
            "campaign_data": session.get("campaign_data", {}),
            "last_interaction": session.get("last_interaction"),
            "has_conversation_history": len(session.get("conversation_history", [])) > 0
        }
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up sessions older than max_age_hours."""
        cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        sessions_to_remove = []
        
        for user_phone, session in self.user_sessions.items():
            last_interaction = session.get("last_interaction")
            if last_interaction and last_interaction.timestamp() < cutoff_time:
                sessions_to_remove.append(user_phone)
        
        for user_phone in sessions_to_remove:
            del self.user_sessions[user_phone]
        
        logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
        return len(sessions_to_remove)