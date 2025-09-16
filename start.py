#!/usr/bin/env python3
"""
DisparaAI Startup Script
Simple script to start the DisparaAI application
"""

import os
import sys
import subprocess
from pathlib import Path
from disparaai.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Start the DisparaAI application."""
    logger.info("🚀 Starting DisparaAI - WhatsApp Bulk Messaging System")
    logger.info("=" * 60)
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Check if .env file exists
    if not Path(".env").exists():
        logger.error("❌ .env file not found!")
        logger.info("📝 Please create a .env file with your configuration:")
        logger.info("   cp .env.example .env")
        logger.info("   # Then edit .env with your API keys")
        sys.exit(1)
    
    # Check if virtual environment exists
    if not Path(".venv").exists():
        logger.error("❌ Virtual environment not found!")
        logger.info("📝 Please run: uv sync")
        sys.exit(1)
    
    logger.info("✅ Environment checks passed")
    logger.info("🌐 Starting web server on http://localhost:8000")
    logger.info("📱 Webhook endpoint: http://localhost:8000/webhook/evolution")
    logger.info("🔍 Health check: http://localhost:8000/health")
    logger.info("\n💡 Press Ctrl+C to stop the application")
    logger.info("=" * 60)
    
    try:
        # Start the application
        subprocess.run(["uv", "run", "python", "main.py"], check=True)
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Shutting down DisparaAI...")
        logger.info("✅ Application stopped successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"\n❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()