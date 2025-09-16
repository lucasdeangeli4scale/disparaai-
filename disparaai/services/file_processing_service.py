"""
File Processing Service

Business logic for handling CSV and image file uploads, validation, and processing.
Coordinates between file handlers and phone validators.
"""

import logging
from typing import Dict, Any, Tuple, List
from datetime import datetime

from disparaai.models.whatsapp import WhatsAppMedia
from disparaai.models.campaign import PhoneNumber
from disparaai.utils.base64_file_handler import Base64FileHandler as FileHandler
from disparaai.utils.phone_validator import PhoneValidator

logger = logging.getLogger(__name__)


class ProcessedCSV:
    """Data class for processed CSV results."""
    def __init__(self, file_info: Dict[str, Any], phone_numbers: List[PhoneNumber], stats: Dict[str, Any]):
        self.file_info = file_info
        self.phone_numbers = phone_numbers
        self.stats = stats


class ProcessedImage:
    """Data class for processed image results."""
    def __init__(self, file_info: Dict[str, Any]):
        self.file_info = file_info


class FileProcessingService:
    """Business service for file processing coordination."""
    
    def __init__(self):
        self.file_handler = FileHandler()
        self.phone_validator = PhoneValidator()
    
    async def process_csv_upload(self, media: WhatsAppMedia) -> ProcessedCSV:
        """Process CSV/spreadsheet upload and extract phone numbers."""
        try:
            # Ensure handler initialization
            await self.file_handler.initialize()
            
            # Validate base64 content
            if not media.base64:
                raise ValueError("No file content received")
            
            # Process base64 file
            file_info = self.file_handler.process_base64_file(
                media.base64,
                media.filename or "upload.csv",
                "csv"
            )
            
            # Extract phone numbers from spreadsheet data
            phone_objects, stats = await self.file_handler.extract_phone_numbers_from_csv(
                file_info['file_data'],
                file_info['filename']
            )
            
            # Extract raw phone strings for validation
            phone_strings = [phone.raw for phone in phone_objects]
            
            # Validate phone numbers
            validated_phones, updated_stats = self.phone_validator.validate_csv_phones_batch(phone_strings)
            
            return ProcessedCSV(
                file_info=file_info,
                phone_numbers=validated_phones,
                stats=updated_stats
            )
            
        except Exception as e:
            logger.error(f"Error processing CSV upload: {str(e)}", exc_info=True)
            raise
    
    async def process_image_upload(self, media: WhatsAppMedia) -> ProcessedImage:
        """Process image upload for contextual copy generation."""
        try:
            # Validate base64 content
            if not media.base64:
                raise ValueError("No image content received")
            
            # Process base64 image
            image_info = self.file_handler.process_base64_file(
                media.base64,
                media.filename or "image.jpg",
                "image"
            )
            
            return ProcessedImage(file_info=image_info)
            
        except Exception as e:
            logger.error(f"Error processing image upload: {str(e)}", exc_info=True)
            raise
    
    def validate_csv_requirements(self, filename: str) -> bool:
        """Validate CSV file meets requirements."""
        if not filename:
            return False
        
        # Check file extension
        valid_extensions = ['.csv', '.xlsx', '.xls']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)
    
    def validate_image_requirements(self, filename: str) -> bool:
        """Validate image file meets requirements."""
        if not filename:
            return False
        
        # Check file extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)
    
    def get_file_stats_summary(self, stats: Dict[str, Any]) -> str:
        """Generate human-readable stats summary."""
        countries_text = ', '.join(stats['countries'].keys()) if stats['countries'] else 'None detected'
        
        return f"""*Estatísticas:*
• Total: {stats['total_numbers']} números
• Válidos: {stats['valid_numbers']}
• Inválidos: {stats['invalid_numbers']}
• Países: {countries_text}"""
    
    async def close(self):
        """Clean up resources."""
        await self.file_handler.close()
        await self.phone_validator.close()