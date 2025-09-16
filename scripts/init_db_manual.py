#!/usr/bin/env python3
"""
Manual database initialization script for when password auth fails.
This script uses sudo to run PostgreSQL commands directly.
"""

import subprocess
import sys
from pathlib import Path
from disparaai.utils.logger import get_logger

logger = get_logger(__name__)

def run_sql_command(sql_command: str, database: str = "disparaai") -> bool:
    """Run SQL command using sudo postgres user."""
    try:
        cmd = ["sudo", "-u", "postgres", "psql", "-d", database, "-c", sql_command]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ SQL Error: {e.stderr}")
        return False

def create_tables_manually():
    """Create database tables manually using SQL commands."""
    logger.info("🔨 Creating database tables manually...")
    
    # SQL for creating all tables
    tables_sql = """
    -- Enable UUID extension
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    -- Create campaigns table
    CREATE TABLE IF NOT EXISTS campaigns (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_phone VARCHAR(20) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        message_text TEXT,
        total_recipients INTEGER DEFAULT 0,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP WITH TIME ZONE
    );
    
    CREATE INDEX IF NOT EXISTS idx_campaigns_user_phone ON campaigns(user_phone);
    CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
    
    -- Create phone_numbers table
    CREATE TABLE IF NOT EXISTS phone_numbers (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
        phone_number VARCHAR(20) NOT NULL,
        formatted_number VARCHAR(25) NOT NULL,
        is_valid BOOLEAN NOT NULL DEFAULT true,
        country_code VARCHAR(3),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_phone_numbers_campaign_id ON phone_numbers(campaign_id);
    
    -- Create messages table
    CREATE TABLE IF NOT EXISTS messages (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
        phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
        message_text TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        whatsapp_message_id VARCHAR(255),
        sent_at TIMESTAMP WITH TIME ZONE,
        delivered_at TIMESTAMP WITH TIME ZONE,
        failed_at TIMESTAMP WITH TIME ZONE,
        error_message TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_messages_campaign_id ON messages(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
    
    -- Create user_sessions table
    CREATE TABLE IF NOT EXISTS user_sessions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_phone VARCHAR(20) NOT NULL,
        session_data JSONB,
        last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_user_sessions_user_phone ON user_sessions(user_phone);
    
    -- Create webhook_events table
    CREATE TABLE IF NOT EXISTS webhook_events (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        event_type VARCHAR(50) NOT NULL,
        event_data JSONB NOT NULL,
        processed BOOLEAN DEFAULT false,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_webhook_events_processed ON webhook_events(processed);
    CREATE INDEX IF NOT EXISTS idx_webhook_events_event_type ON webhook_events(event_type);
    
    -- Create agent_sessions table for AGNO
    CREATE TABLE IF NOT EXISTS agent_sessions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        session_id VARCHAR(255) NOT NULL UNIQUE,
        agent_id VARCHAR(255) NOT NULL,
        user_id VARCHAR(255) NOT NULL,
        session_data JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_agent_sessions_session_id ON agent_sessions(session_id);
    CREATE INDEX IF NOT EXISTS idx_agent_sessions_user_id ON agent_sessions(user_id);
    """
    
    if run_sql_command(tables_sql):
        logger.info("✅ Database tables created successfully!")
        
        # List created tables
        list_tables_sql = "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
        logger.info("\n📋 Created tables:")
        try:
            cmd = ["sudo", "-u", "postgres", "psql", "-d", "disparaai", "-t", "-c", list_tables_sql]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    logger.info(f"   • {line.strip()}")
        except:
            logger.warning("   • (Unable to list tables, but creation likely succeeded)")
        
        return True
    else:
        return False

def main():
    """Main function."""
    logger.info("🔧 Manual Database Initialization for DisparaAI\n")
    
    # Change to project root
    script_dir = Path(__file__).parent.parent
    logger.info(f"📁 Working directory: {script_dir}")
    
    if create_tables_manually():
        logger.info("\n🎉 Manual database initialization completed!")
        logger.info("\n📝 Next steps:")
        logger.info("   1. Test the application: uv run python main.py")
        logger.info("   2. Check database connection in your application")
    else:
        logger.error("\n💥 Manual database initialization failed!")
        logger.info("\n🔧 Troubleshooting:")
        logger.info("   1. Ensure PostgreSQL is running: sudo systemctl start postgresql")
        logger.info("   2. Ensure database 'disparaai' exists: sudo -u postgres createdb disparaai")
        logger.info("   3. Try running this script again")
        sys.exit(1)

if __name__ == "__main__":
    main()