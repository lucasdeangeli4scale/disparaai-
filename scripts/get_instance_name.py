#!/usr/bin/env python3
"""
Get the correct instance name from Evolution API
This script will help identify the proper instance name to use in .env
"""

import os
import requests
import json
from dotenv import load_dotenv
from disparaai.utils.logger import get_logger

logger = get_logger(__name__)

def get_instance_name():
    """Get the correct instance name from Evolution API."""
    
    # Load environment variables
    load_dotenv()
    
    evolution_url = os.getenv("EVOLUTION_API_URL")
    evolution_key = os.getenv("EVOLUTION_API_KEY")
    
    logger.info("🔍 Fetching Evolution API instances...\n")
    logger.info(f"API URL: {evolution_url}")
    logger.info(f"API Key: {evolution_key[:10]}...{evolution_key[-10:] if len(evolution_key) > 20 else evolution_key}")
    
    try:
        headers = {"apikey": evolution_key}
        response = requests.get(
            f"{evolution_url}/instance/fetchInstances",
            headers=headers,
            timeout=10
        )
        
        logger.info(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            instances = response.json()
            logger.info(f"✅ Found {len(instances)} instance(s)\n")
            
            if not instances:
                logger.error("❌ No instances found!")
                logger.info("💡 You may need to create an instance first in Evolution API")
                return
            
            logger.info("📋 Available instances:")
            logger.info("-" * 60)
            
            for i, instance in enumerate(instances, 1):
                logger.info(f"{i}. Instance Details:")
                
                # Try different possible field names
                instance_name = (
                    instance.get("instanceName") or 
                    instance.get("name") or 
                    instance.get("instance") or
                    "unknown"
                )
                
                instance_id = (
                    instance.get("instanceId") or
                    instance.get("id") or
                    "unknown"
                )
                
                state = instance.get("state", "unknown")
                status = instance.get("connectionStatus", "unknown")
                
                logger.info(f"   Name: '{instance_name}'")
                logger.info(f"   ID: {instance_id}")
                logger.info(f"   State: {state}")
                logger.info(f"   Status: {status}")
                
                # Show all available fields for debugging
                logger.debug(f"   All fields: {list(instance.keys())}")
                
                # Check if this matches our webhook URL UUID
                webhook_uuid = "1dee6f78-6bfc-4a5c-9947-8d64c0ef4ce9"
                if webhook_uuid in str(instance_id) or webhook_uuid in str(instance_name):
                    logger.info(f"🎯 This instance matches your webhook URL!")
                    logger.info(f"✅ Use this instance name in .env: EVOLUTION_INSTANCE_NAME={instance_name}")
                    
                    # Update .env file suggestion
                    logger.info("📝 To update your .env file, run:")
                    logger.info(f"   sed -i 's/EVOLUTION_INSTANCE_NAME=.*/EVOLUTION_INSTANCE_NAME={instance_name}/' .env")
                    
                    return instance_name
            
            # If no exact match, show all names
            logger.info("🔧 Available instance names for .env:")
            for i, instance in enumerate(instances, 1):
                instance_name = (
                    instance.get("instanceName") or 
                    instance.get("name") or 
                    instance.get("instance") or
                    f"instance_{i}"
                )
                logger.info(f"   EVOLUTION_INSTANCE_NAME={instance_name}")
                
        else:
            logger.error(f"❌ HTTP Error {response.status_code}")
            logger.error(f"Response: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        logger.info("\n🔧 Troubleshooting:")
        logger.info("1. Check if Evolution API is running on http://localhost:8080")
        logger.info("2. Verify your API key is correct")
        logger.info("3. Make sure the instance exists in Evolution API")

if __name__ == "__main__":
    get_instance_name()