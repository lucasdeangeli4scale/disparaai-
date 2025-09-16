"""Phone number validation utilities."""

import phonenumbers
from phonenumbers import carrier, geocoder
from typing import List, Tuple, Iterator
import polars as pl
import io
import httpx
import re
from disparaai.models.campaign import PhoneNumber


class PhoneValidator:
    """Phone number validation and formatting utility with regional support."""
    
    def __init__(self, default_region: str = "BR"):
        """
        Initialize the phone validator.
        
        Args:
            default_region: Default region code for number parsing (BR, US, PT, etc.)
        """
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.default_region = default_region
        
        # Region-specific configuration for MVPs and WhatsApp compatibility
        self.region_config = {
            "BR": {
                "whatsapp_compatible": True,  # Accept legacy formats for WhatsApp
                "auto_fix_legacy": True,      # Try to fix legacy mobile numbers
                "legacy_mobile_patterns": [
                    # Brazilian legacy mobile patterns (8 digits after area code)
                    r"^(\+55\s?)?(\d{2})\s?(\d{4})-?(\d{4})$",  # +55 XX XXXX-XXXX
                ]
            },
            "US": {
                "whatsapp_compatible": False,
                "auto_fix_legacy": False,
                "legacy_mobile_patterns": []
            },
            "PT": {
                "whatsapp_compatible": False, 
                "auto_fix_legacy": False,
                "legacy_mobile_patterns": []
            }
        }
    
    def validate_phone_number(self, phone: str, default_region: str = None) -> PhoneNumber:
        """
        Validate and format a single phone number with regional enhancements.
        
        Args:
            phone: Raw phone number string
            default_region: Default country code if not provided (uses instance default)
            
        Returns:
            PhoneNumber object with validation results
        """
        region = default_region or self.default_region
        original_phone = phone
        
        try:
            # Clean the input
            cleaned_phone = self._clean_phone_number(phone)
            
            # Try standard parsing first
            parsed_number = phonenumbers.parse(cleaned_phone, region)
            is_valid = phonenumbers.is_valid_number(parsed_number)
            
            # If invalid and we have regional config, try legacy fixes
            if not is_valid and region in self.region_config:
                config = self.region_config[region]
                if config.get("whatsapp_compatible") and config.get("auto_fix_legacy"):
                    # Try to fix Brazilian legacy mobile numbers
                    if region == "BR":
                        fixed_phone = self._fix_brazilian_legacy_mobile(cleaned_phone)
                        if fixed_phone != cleaned_phone:
                            try:
                                parsed_number = phonenumbers.parse(fixed_phone, region)
                                is_valid = phonenumbers.is_valid_number(parsed_number)
                                if is_valid:
                                    cleaned_phone = fixed_phone
                            except:
                                pass  # Keep original if fix fails
            
            if is_valid:
                # Format to E.164
                formatted = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                
                # Get country code
                country_code = phonenumbers.region_code_for_number(parsed_number)
                
                return PhoneNumber(
                    raw=original_phone,
                    formatted=formatted,
                    country_code=country_code,
                    is_valid=True,
                    error_message=None
                )
            else:
                # For WhatsApp-compatible regions, check if it's a "possible" number
                # that might work even if not strictly valid
                if region in self.region_config and self.region_config[region].get("whatsapp_compatible"):
                    is_possible = phonenumbers.is_possible_number(parsed_number)
                    if is_possible:
                        # Accept as valid for WhatsApp compatibility
                        formatted = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                        country_code = phonenumbers.region_code_for_number(parsed_number)
                        
                        return PhoneNumber(
                            raw=original_phone,
                            formatted=formatted,
                            country_code=country_code,
                            is_valid=True,  # Mark as valid for WhatsApp compatibility
                            error_message=None
                        )
                
                return PhoneNumber(
                    raw=original_phone,
                    formatted=cleaned_phone,
                    country_code=None,
                    is_valid=False,
                    error_message="Invalid phone number format"
                )
                
        except phonenumbers.NumberParseException as e:
            return PhoneNumber(
                raw=original_phone,
                formatted=original_phone,
                country_code=None,
                is_valid=False,
                error_message=f"Parse error: {str(e)}"
            )
        except Exception as e:
            return PhoneNumber(
                raw=original_phone,
                formatted=original_phone,
                country_code=None,
                is_valid=False,
                error_message=f"Validation error: {str(e)}"
            )
    
    def validate_csv_phones_streaming(self, csv_file_path: str, phone_column: str = None, chunk_size: int = 1000) -> Iterator[Tuple[List[PhoneNumber], dict]]:
        """
        Process and validate phone numbers from CSV file using streaming for memory efficiency.
        
        Args:
            csv_file_path: Path to CSV file
            phone_column: Name of the column containing phone numbers (auto-detected if None)
            chunk_size: Number of rows to process per chunk
            
        Yields:
            Tuple of (validated_phone_numbers_chunk, chunk_statistics)
        """
        try:
            # Use Polars lazy frame for memory efficiency
            lazy_df = pl.scan_csv(csv_file_path)
            columns = lazy_df.columns
            
            # Auto-detect phone column if not specified
            if phone_column is None or phone_column not in columns:
                possible_columns = ['phone', 'number', 'telephone', 'mobile', 'celular', 'telefone', 'whatsapp', 'numero']
                phone_column = None
                
                for col in columns:
                    if col.lower() in possible_columns:
                        phone_column = col
                        break
                
                if not phone_column:
                    raise ValueError(f"Phone number column not found. Available columns: {columns}")
            
            # Get total rows for chunking
            total_rows = lazy_df.select(pl.len()).collect().item()
            
            # Process in chunks
            for offset in range(0, total_rows, chunk_size):
                chunk = lazy_df.slice(offset, chunk_size).select(phone_column).collect()
                
                # Vectorized validation using Polars expressions
                validated_phones = []
                phone_values = chunk[phone_column].drop_nulls().to_list()
                
                for phone_value in phone_values:
                    phone_str = str(phone_value).strip()
                    if phone_str and phone_str.lower() != 'nan':
                        validated_phone = self.validate_phone_number(phone_str)
                        validated_phones.append(validated_phone)
                
                # Calculate chunk statistics
                total_count = len(validated_phones)
                valid_count = sum(1 for p in validated_phones if p.is_valid)
                invalid_count = total_count - valid_count
                
                # Group by country (vectorized)
                country_stats = {}
                for phone in validated_phones:
                    if phone.is_valid and phone.country_code:
                        country_stats[phone.country_code] = country_stats.get(phone.country_code, 0) + 1
                
                chunk_stats = {
                    "total_numbers": total_count,
                    "valid_numbers": valid_count,
                    "invalid_numbers": invalid_count,
                    "success_rate": (valid_count / total_count * 100) if total_count > 0 else 0,
                    "countries": country_stats,
                    "column_used": phone_column,
                    "chunk_offset": offset
                }
                
                yield validated_phones, chunk_stats
                
        except Exception as e:
            raise ValueError(f"Error processing CSV: {str(e)}")
    
    def validate_csv_phones_batch(self, phone_numbers: List[str]) -> Tuple[List[PhoneNumber], dict]:
        """
        Validate a batch of phone numbers efficiently.
        
        Args:
            phone_numbers: List of phone number strings
            
        Returns:
            Tuple of (validated_phone_numbers, statistics)
        """
        validated_phones = []
        
        # Vectorized processing
        for phone_value in phone_numbers:
            if phone_value and str(phone_value).strip():
                validated_phone = self.validate_phone_number(str(phone_value).strip())
                validated_phones.append(validated_phone)
        
        # Calculate statistics
        total_count = len(validated_phones)
        valid_count = sum(1 for p in validated_phones if p.is_valid)
        invalid_count = total_count - valid_count
        
        # Group by country
        country_stats = {}
        for phone in validated_phones:
            if phone.is_valid and phone.country_code:
                country_stats[phone.country_code] = country_stats.get(phone.country_code, 0) + 1
        
        stats = {
            "total_numbers": total_count,
            "valid_numbers": valid_count,
            "invalid_numbers": invalid_count,
            "success_rate": (valid_count / total_count * 100) if total_count > 0 else 0,
            "countries": country_stats
        }
        
        return validated_phones, stats
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
    
    def validate_csv_phones(self, csv_content: str, phone_column: str = "phone") -> Tuple[List[PhoneNumber], dict]:
        """
        Process and validate phone numbers from CSV content (legacy method).
        Warning: This loads entire CSV into memory - use validate_csv_phones_streaming for large files.
        
        Args:
            csv_content: CSV file content as string
            phone_column: Name of the column containing phone numbers
            
        Returns:
            Tuple of (validated_phone_numbers, statistics)
        """
        try:
            # Read CSV using Polars
            df = pl.read_csv(io.StringIO(csv_content))
            
            if phone_column not in df.columns:
                # Try to find phone column automatically
                possible_columns = ['phone', 'number', 'telephone', 'mobile', 'celular', 'telefone']
                phone_column = None
                
                for col in df.columns:
                    if col.lower() in possible_columns:
                        phone_column = col
                        break
                
                if not phone_column:
                    raise ValueError(f"Phone number column not found. Available columns: {df.columns}")
            
            # Extract phone numbers using vectorized operations
            phone_values = df[phone_column].drop_nulls().to_list()
            return self.validate_csv_phones_batch(phone_values)
            
        except Exception as e:
            raise ValueError(f"Error processing CSV: {str(e)}")
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean phone number string."""
        if not phone:
            return ""
        
        # Remove common separators and spaces
        cleaned = phone.strip()
        cleaned = cleaned.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        cleaned = cleaned.replace(".", "").replace("/", "")
        
        # Handle Brazilian numbers with 9th digit
        if cleaned.startswith("55") and len(cleaned) == 13:
            # Brazilian mobile with country code
            return "+" + cleaned
        elif len(cleaned) == 11 and cleaned.startswith("1"):
            # Brazilian mobile without country code, add +55
            return "+55" + cleaned
        elif len(cleaned) == 10 and not cleaned.startswith("0"):
            # Brazilian mobile old format, add 9 and +55
            return "+55" + cleaned[0:2] + "9" + cleaned[2:]
        
        # Add + if not present and looks like international
        if not cleaned.startswith("+") and len(cleaned) > 10:
            cleaned = "+" + cleaned
            
        return cleaned
    
    def _fix_brazilian_legacy_mobile(self, phone: str) -> str:
        """
        Fix Brazilian legacy mobile numbers by adding the missing 9th digit.
        This handles numbers that were valid before the 9th digit requirement
        but are still accepted by WhatsApp.
        
        Args:
            phone: Cleaned phone number string
            
        Returns:
            Fixed phone number string if applicable, otherwise original
        """
        if not phone:
            return phone
            
        # Handle Brazilian numbers without the 9th digit
        # Pattern: +55 XX XXXX-XXXX (8 digits after area code)
        
        # Remove formatting for analysis
        clean = phone.replace("+", "").replace("-", "").replace(" ", "")
        
        # Check if it's a Brazilian number (starts with 55)
        if clean.startswith("55") and len(clean) == 12:
            # Extract parts: 55 + area_code (2 digits) + number (8 digits)
            area_code = clean[2:4]
            number = clean[4:]
            
            # Check if it's a mobile area code and has 8 digits
            mobile_area_codes = [
                '11', '12', '13', '14', '15', '16', '17', '18', '19',  # São Paulo
                '21', '22', '24',  # Rio de Janeiro
                '27', '28',        # Espírito Santo
                '31', '32', '33', '34', '35', '37', '38',  # Minas Gerais
                '41', '42', '43', '44', '45', '46',        # Paraná
                '47', '48', '49',  # Santa Catarina
                '51', '53', '54', '55',  # Rio Grande do Sul
                '61',              # Distrito Federal
                '62', '64',        # Goiás
                '63',              # Tocantins
                '65', '66',        # Mato Grosso
                '67',              # Mato Grosso do Sul
                '68',              # Acre
                '69',              # Rondônia
                '71', '73', '74', '75', '77',  # Bahia
                '79',              # Sergipe
                '81', '87',        # Pernambuco
                '82',              # Alagoas
                '83',              # Paraíba
                '84',              # Rio Grande do Norte
                '85', '88',        # Ceará
                '86', '89',        # Piauí
                '91', '93', '94',  # Pará
                '92', '97',        # Amazonas
                '95',              # Roraima
                '96',              # Amapá
                '98', '99'         # Maranhão
            ]
            
            if area_code in mobile_area_codes and len(number) == 8:
                # Check if it doesn't already start with 9
                if not number.startswith('9'):
                    # Add the 9th digit: +55 XX 9XXXX-XXXX
                    return f"+55{area_code}9{number}"
        
        return phone