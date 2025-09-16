#!/usr/bin/env python3
"""
DisparaAI Database Setup Script

This script helps set up the PostgreSQL database for DisparaAI.
It handles database creation and table initialization.
"""

import os
import subprocess
import sys
from pathlib import Path
from disparaai.utils.logger import get_logger

logger = get_logger(__name__)

def check_postgresql():
    """Check if PostgreSQL is installed and running."""
    logger.info("🔍 Checking PostgreSQL installation...")
    
    try:
        # Check if psql is available
        result = subprocess.run(["psql", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ PostgreSQL found: {result.stdout.strip()}")
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        logger.error("❌ PostgreSQL not found!")
        logger.info("\n📥 Install PostgreSQL:")
        logger.info("   Ubuntu/Debian: sudo apt install postgresql postgresql-contrib")
        logger.info("   macOS: brew install postgresql")
        logger.info("   Then restart this script.")
        return False
    
    # Check if PostgreSQL service is running
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "postgresql"], 
            capture_output=True, text=True
        )
        if result.returncode == 0 and "active" in result.stdout:
            logger.info("✅ PostgreSQL service is running")
        else:
            logger.warning("⚠️  PostgreSQL service not running")
            logger.info("📦 Starting PostgreSQL...")
            start_result = subprocess.run(
                ["sudo", "systemctl", "start", "postgresql"],
                capture_output=True, text=True
            )
            if start_result.returncode == 0:
                logger.info("✅ PostgreSQL service started")
            else:
                logger.error("❌ Failed to start PostgreSQL service")
                logger.info("Please start PostgreSQL manually:")
                logger.info("   sudo systemctl start postgresql")
                return False
    except subprocess.CalledProcessError:
        logger.warning("⚠️  Cannot check PostgreSQL service status")
    
    return True


def setup_database_user():
    """Set up database user and permissions."""
    logger.info("\n🔑 Setting up database user...")
    
    try:
        # Create user with password and database creation permissions
        create_user_cmd = [
            "sudo", "-u", "postgres", "psql", "-c",
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'disparaai') THEN
                    CREATE USER disparaai WITH PASSWORD 'disparaai123';
                    ALTER USER disparaai CREATEDB;
                    RAISE NOTICE 'User disparaai created successfully';
                ELSE
                    ALTER USER disparaai WITH PASSWORD 'disparaai123';
                    ALTER USER disparaai CREATEDB;
                    RAISE NOTICE 'User disparaai already exists, updated permissions';
                END IF;
            END
            $$;
            """
        ]
        
        result = subprocess.run(create_user_cmd, capture_output=True, text=True, check=True)
        logger.info("✅ Database user 'disparaai' configured successfully")
        
        # Grant privileges on database if it exists
        grant_privileges_cmd = [
            "sudo", "-u", "postgres", "psql", "-c",
            "GRANT ALL PRIVILEGES ON DATABASE disparaai TO disparaai;"
        ]
        subprocess.run(grant_privileges_cmd, capture_output=True, text=True)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to configure database user: {e}")
        logger.warning("⚠️  Continuing with existing configuration...")
    
    return True


def create_env_file():
    """Create .env file with database configuration."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        logger.info("✅ .env file already exists")
        return
    
    if env_example.exists():
        logger.info("🔧 Creating .env file from template...")
        with open(env_example, "r") as src, open(env_file, "w") as dst:
            content = src.read()
            # Update database URL
            content = content.replace(
                "postgresql+psycopg://user:password@localhost:5432/disparaai",
                "postgresql+psycopg://disparaai:disparaai123@localhost:5432/disparaai"
            )
            dst.write(content)
        logger.info("✅ .env file created")
    else:
        logger.warning("⚠️  .env.example not found, creating basic .env...")
        with open(env_file, "w") as f:
            f.write("""# Database Configuration
DATABASE_URL=postgresql+psycopg://disparaai:disparaai123@localhost:5432/disparaai

# Evolution API Configuration (update these)
EVOLUTION_API_URL=https://your-evolution-api.com
EVOLUTION_API_KEY=your-evolution-api-key
EVOLUTION_INSTANCE_NAME=disparaai-instance
WHATSAPP_WEBHOOK_TOKEN=your-webhook-verification-token

# AI Service API Keys (add your keys)
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Application Configuration
DEBUG=true
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=10
""")
        logger.info("✅ Basic .env file created")


def main():
    """Main setup function."""
    logger.info("🚀 DisparaAI Database Setup\n")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Step 1: Check PostgreSQL
    if not check_postgresql():
        sys.exit(1)
    
    # Step 2: Set up database user
    if not setup_database_user():
        logger.warning("⚠️  Continuing with default postgres user...")
    
    # Step 3: Create .env file
    create_env_file()
    
    # Step 4: Initialize database
    logger.info("\n🔨 Initializing database...")
    try:
        result = subprocess.run([
            "uv", "run", "python", "-m", "disparaai.database.init"
        ], check=True)
        logger.info("✅ Database initialization completed!")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.info("\n🔧 Manual steps:")
        logger.info("   1. Make sure PostgreSQL is running")
        logger.info("   2. Update DATABASE_URL in .env file")
        logger.info("   3. Run: uv run python -m disparaai.database.init")
        sys.exit(1)
    
    logger.info(f"\n🎉 Setup completed successfully!")
    logger.info(f"\n📝 Next steps:")
    logger.info(f"   1. Update API keys in .env file")
    logger.info(f"   2. Configure Evolution API settings")
    logger.info(f"   3. Run: uv run python main.py")


if __name__ == "__main__":
    main()