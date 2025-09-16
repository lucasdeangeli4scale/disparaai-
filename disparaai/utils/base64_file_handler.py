"""
Base64 File Handler - Uses Evolution API webhookBase64 + Database Storage
Completely eliminates external storage dependencies.
"""

import io
import logging
import base64
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import polars as pl
from PIL import Image

from disparaai.models.campaign import PhoneNumber

logger = logging.getLogger(__name__)


class Base64FileHandler:
    """File handler using Evolution API base64 webhooks and database storage."""
    
    def __init__(self, max_file_size_mb: int = 10):
        """Initialize base64 file handler."""
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        
        # Allowed file types
        self.allowed_csv_extensions = {'.csv', '.xlsx', '.xls'}
        self.allowed_image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        self.csv_mime_types = {
            'text/csv',
            'application/vnd.ms-excel', 
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        self.image_mime_types = {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp'
        }
        
        logger.info("Base64FileHandler initialized (Evolution API webhookBase64 + Database)")
    
    async def initialize(self):
        """Initialize handler - no external services needed."""
        logger.info("✅ Base64FileHandler ready - no external storage required")
    
    def validate_file(self, filename: str, file_size: int, mime_type: str) -> Tuple[bool, str, Optional[str]]:
        """Validate file size and type."""
        # Check file size
        if file_size > self.max_file_size_bytes:
            size_mb = file_size / 1024 / 1024
            max_mb = self.max_file_size_bytes / 1024 / 1024
            return False, "", f"File size ({size_mb:.1f}MB) exceeds maximum ({max_mb}MB)"
        
        # Check file type
        file_path = Path(filename.lower())
        extension = file_path.suffix
        
        if extension in self.allowed_csv_extensions or mime_type in self.csv_mime_types:
            return True, "csv", None
        elif extension in self.allowed_image_extensions or mime_type in self.image_mime_types:
            return True, "image", None
        else:
            return False, "", f"Unsupported file type: {extension} (MIME: {mime_type})"
    
    def process_base64_file(self, base64_data: str, filename: str, file_type: str) -> Dict[str, Any]:
        """
        Process base64 file data directly from Evolution API webhook.
        
        Args:
            base64_data: Base64-encoded file from webhook
            filename: Original filename
            file_type: "csv" or "image"
            
        Returns:
            Dictionary with file info and binary data for database storage
        """
        try:
            # Decode base64 to binary
            file_data = base64.b64decode(base64_data)
            file_size = len(file_data)
            
            # Basic file metadata
            file_info = {
                'filename': filename,
                'file_data': file_data,
                'size_bytes': file_size,
                'mime_type': self._guess_mime_type(filename, file_type)
            }
            
            # Add type-specific metadata
            if file_type == "image":
                image_metadata = self._extract_image_metadata(file_data)
                file_info.update(image_metadata)
            
            logger.info(f"Processed {file_type}: {filename} ({file_size} bytes)")
            return file_info
            
        except Exception as e:
            logger.error(f"Error processing base64 file {filename}: {str(e)}")
            raise ValueError(f"Failed to process {file_type} file: {str(e)}")
    
    async def extract_phone_numbers_from_csv(self, file_data: bytes, filename: str) -> Tuple[List[PhoneNumber], Dict[str, Any]]:
        """
        Extract and validate phone numbers from CSV data.
        
        Args:
            file_data: Binary CSV data
            filename: Filename for logging
            
        Returns:
            Tuple of (phone_numbers_list, statistics)
        """
        try:
            # Use Polars for efficient CSV processing
            csv_buffer = io.BytesIO(file_data)
            
            # Read CSV
            df = pl.read_csv(csv_buffer, ignore_errors=True)
            
            # Find phone number columns
            phone_columns = self._find_phone_columns(df.columns)
            if not phone_columns:
                phone_columns = [df.columns[0]]  # Use first column as fallback
                logger.warning(f"No phone column found, using: {phone_columns[0]}")
            
            # Extract unique phone numbers
            raw_phones = []
            for col in phone_columns:
                phones = df[col].drop_nulls().to_list()
                raw_phones.extend([str(phone).strip() for phone in phones if str(phone).strip()])
            
            # Remove duplicates while preserving order  
            unique_phones = list(dict.fromkeys(raw_phones))
            
            # Convert to PhoneNumber objects (validation will be done separately)
            phone_numbers = []
            for phone in unique_phones:
                phone_numbers.append(PhoneNumber(
                    raw=phone,
                    formatted=phone,  # Will be updated during validation
                    is_valid=False    # Will be updated during validation
                ))
            
            # Generate statistics
            stats = {
                'total_numbers': len(unique_phones),
                'valid_numbers': 0,      # Will be updated after validation
                'invalid_numbers': 0,    # Will be updated after validation
                'success_rate': 0.0,     # Will be updated after validation
                'countries': {}          # Will be updated after validation
            }
            
            logger.info(f"Extracted {len(unique_phones)} phone numbers from {filename}")
            return phone_numbers, stats
            
        except Exception as e:
            logger.error(f"Error extracting phones from {filename}: {str(e)}")
            # Try fallback parsing
            return self._fallback_phone_extraction(file_data, filename)
    
    def _find_phone_columns(self, columns: List[str]) -> List[str]:
        """Find columns that likely contain phone numbers."""
        phone_keywords = ['phone', 'telefone', 'numero', 'number', 'cel', 'mobile', 'whatsapp']
        phone_columns = []
        
        for col in columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in phone_keywords):
                phone_columns.append(col)
                
        return phone_columns
    
    def _fallback_phone_extraction(self, file_data: bytes, filename: str) -> Tuple[List[PhoneNumber], Dict[str, Any]]:
        """Fallback phone extraction using simple text processing."""
        try:
            # Try different encodings
            text_content = None
            for encoding in ['utf-8', 'latin1', 'cp1252']:
                try:
                    text_content = file_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not text_content:
                raise ValueError("Could not decode file")
            
            # Simple CSV parsing
            lines = text_content.strip().split('\n')
            phone_numbers = []
            
            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.replace(';', ',').split(',')
                    if parts and parts[0].strip():
                        phone = parts[0].strip().replace('"', '')
                        phone_numbers.append(PhoneNumber(
                            raw=phone,
                            formatted=phone,
                            is_valid=False
                        ))
            
            stats = {
                'total_numbers': len(phone_numbers),
                'valid_numbers': 0,
                'invalid_numbers': 0, 
                'success_rate': 0.0,
                'countries': {}
            }
            
            logger.info(f"Fallback extraction: {len(phone_numbers)} phones from {filename}")
            return phone_numbers, stats
            
        except Exception as e:
            logger.error(f"Fallback extraction failed for {filename}: {str(e)}")
            return [], {'total_numbers': 0, 'valid_numbers': 0, 'invalid_numbers': 0, 'success_rate': 0.0, 'countries': {}}
    
    def _extract_image_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """Extract image dimensions and format."""
        try:
            with Image.open(io.BytesIO(file_data)) as img:
                return {
                    'image_width': img.width,
                    'image_height': img.height,
                    'image_format': img.format.lower() if img.format else 'unknown'
                }
        except Exception as e:
            logger.warning(f"Could not extract image metadata: {str(e)}")
            return {
                'image_width': None,
                'image_height': None,
                'image_format': 'unknown'
            }
    
    def _guess_mime_type(self, filename: str, file_type: str) -> str:
        """Guess MIME type from filename."""
        extension = Path(filename.lower()).suffix
        
        if file_type == "csv":
            mime_map = {
                '.csv': 'text/csv',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.xls': 'application/vnd.ms-excel'
            }
            return mime_map.get(extension, 'text/csv')
        
        elif file_type == "image":
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png', 
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            return mime_map.get(extension, 'image/jpeg')
        
        return 'application/octet-stream'
    
    async def close(self):
        """Cleanup resources."""
        logger.info("Base64FileHandler closed")


# Export for compatibility
FileHandler = Base64FileHandler