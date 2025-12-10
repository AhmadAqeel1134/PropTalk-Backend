import pandas as pd
import PyPDF2
from docx import Document
from io import BytesIO, StringIO
from typing import List, Dict
import csv
import re


def detect_and_parse_csv(file_content: bytes) -> pd.DataFrame:
    """
    Detect delimiter and parse CSV robustly.
    Handles:
    - Comma-separated files
    - Tab-separated files
    - Quoted fields containing the delimiter
    - Phone numbers in scientific notation (preserves as string)
    """
    text = file_content.decode('utf-8', errors='replace')
    
    # Try to detect delimiter from first line
    first_line = text.split('\n')[0]
    
    # Count potential delimiters in header
    tab_count = first_line.count('\t')
    comma_count = first_line.count(',')
    
    # Choose delimiter based on which appears more in header
    if tab_count > comma_count:
        delimiter = '\t'
    else:
        delimiter = ','
    
    # Parse with detected delimiter and proper quoting
    # CRITICAL: Use dtype=str for ALL columns to prevent Excel from converting phone numbers to scientific notation
    try:
        df = pd.read_csv(
            StringIO(text),
            sep=delimiter,
            quotechar='"',
            escapechar='\\',
            on_bad_lines='skip',
            dtype=str,  # Force all columns to string to preserve phone numbers
            keep_default_na=False,
            na_filter=False  # Don't convert anything to NaN
        )
        return df
    except Exception:
        # Fallback: let pandas auto-detect
        return pd.read_csv(
            StringIO(text),
            sep=None,
            engine='python',
            dtype=str,  # Force all columns to string
            keep_default_na=False,
            na_filter=False
        )


async def parse_csv(file_content: bytes) -> Dict:
    """
    Parse CSV file and extract property data and contacts.
    Returns: {"properties": [...], "contacts": [...]}
    
    Handles various CSV formats:
    - Comma or tab separated
    - Quoted fields with delimiters inside
    - Various price formats ($, commas)
    - Flexible column name matching
    """
    try:
        df = detect_and_parse_csv(file_content)
        
        # Normalize column names (lowercase, strip whitespace)
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # Debug: print detected columns
        print(f"CSV Parser - Detected columns: {list(df.columns)}")
        print(f"CSV Parser - Row count: {len(df)}")
        
        properties: List[Dict] = []
        contacts_dict: Dict[str, Dict] = {}

        for idx, row in df.iterrows():
            try:
                # Safe get function that handles missing columns and alternative names
                def get_val(col_name: str, default: str = "", alternatives: List[str] = None) -> str:
                    # Try primary column name
                    if col_name in df.columns:
                        val = row[col_name]
                        if pd.isna(val) or val is None:
                            return default
                        return str(val).strip()
                    
                    # Try alternative column names
                    if alternatives:
                        for alt in alternatives:
                            if alt in df.columns:
                                val = row[alt]
                                if pd.isna(val) or val is None:
                                    return default
                                return str(val).strip()
                    
                    return default
                
                # Helper: safe numeric parsing
                def parse_int(value: str) -> int:
                    if not value:
                        return None
                    try:
                        # Remove $, commas, spaces
                        cleaned = re.sub(r'[$,\s]', '', value)
                        return int(float(cleaned))
                    except Exception:
                        return None

                def parse_float(value: str) -> float:
                    if not value:
                        return None
                    try:
                        cleaned = re.sub(r'[$,\s]', '', value)
                        return float(cleaned)
                    except Exception:
                        return None

                # Parse fields (handle alternative column names)
                price = parse_float(get_val("price"))
                bedrooms = parse_int(get_val("bedrooms"))
                bathrooms = parse_float(get_val("bathrooms"))
                square_feet = parse_int(get_val("square_feet", alternatives=["square_fe"]))
                
                # Get owner info (handle truncated column names: owner_na, owner_ph, owner_em)
                owner_name = get_val("owner_name", alternatives=["owner_na"])
                owner_phone_raw = get_val("owner_phone", alternatives=["owner_ph"])
                owner_email = get_val("owner_email", alternatives=["owner_em"])
                
                # Handle scientific notation phone numbers (e.g., 9.23E+11 -> 923000000000)
                # IMPORTANT: If CSV was saved in Excel, phone numbers may already be in scientific notation
                # We need to detect and convert them, but we've lost precision if they were converted by Excel
                def parse_phone_number(phone_str: str) -> str:
                    if not phone_str:
                        return ""
                    phone_str = str(phone_str).strip()
                    
                    # Check if it's in scientific notation (e.g., "9.23E+11" or "9.23e+11")
                    if 'E+' in phone_str.upper() or 'E-' in phone_str.upper() or ('E' in phone_str.upper() and ('+' in phone_str or '-' in phone_str)):
                        try:
                            # Convert scientific notation to integer, then to string
                            # WARNING: This loses precision! 923036398319 becomes 923000000000
                            phone_num = int(float(phone_str))
                            phone_str = str(phone_num)
                            print(f"    ⚠️ WARNING: Phone in scientific notation converted (precision may be lost): {phone_str}")
                            print(f"    💡 TIP: Save CSV with phone numbers as TEXT in Excel to preserve full numbers")
                        except (ValueError, OverflowError) as e:
                            print(f"    ⚠️ Failed to parse phone {phone_str}: {e}")
                            return ""
                    
                    # If it looks like a number but is too short (less than 10 digits), might be truncated
                    # Remove any non-digit characters for normalization
                    digits_only = ''.join(filter(str.isdigit, phone_str))
                    
                    # If we have a valid phone number length (10-15 digits), return it
                    if len(digits_only) >= 10:
                        return digits_only
                    elif phone_str and len(digits_only) < 10:
                        print(f"    ⚠️ Phone number too short: {phone_str} (only {len(digits_only)} digits)")
                        return ""
                    
                    return phone_str
                
                owner_phone = parse_phone_number(owner_phone_raw)
                
                # Debug: log if phone is missing
                if not owner_phone:
                    print(f"    ⚠️ Row {idx}: Missing or invalid phone number (owner: {owner_name})")
                
                # Normalize is_available
                is_avail_raw = get_val("is_available", "true").lower()
                is_available = "true" if is_avail_raw in ("true", "1", "yes", "y", "available") else "false"
                
                # Clean amenities - remove quotes and normalize separators
                amenities_raw = get_val("amenities")
                # Remove surrounding quotes if present
                amenities_raw = amenities_raw.strip('"\'')
                # Replace tabs with commas for consistency
                amenities_clean = amenities_raw.replace('\t', ', ')

                # Build property data
                property_data = {
                    "property_type": get_val("property_type", alternatives=["property_t"]),
                    "address": get_val("address"),
                    "city": get_val("city"),
                    "state": get_val("state"),
                    "zip_code": get_val("zip_code"),
                    "price": price,
                    "bedrooms": bedrooms,
                    "bathrooms": bathrooms,
                    "square_feet": square_feet,
                    "description": get_val("description", alternatives=["descriptior"]),
                    "amenities": amenities_clean,
                    "owner_name": owner_name,
                    "owner_phone": owner_phone,
                    "is_available": is_available,
                }
                
                # Only add property if it has an address (basic validation)
                if property_data["address"]:
                    properties.append(property_data)
                    
                    # Extract contact data (deduplicate by phone)
                    if owner_name and owner_phone:
                        # Normalize phone for deduplication (digits only)
                        normalized_phone_digits = ''.join(filter(str.isdigit, owner_phone))
                        
                        # Convert to E.164 format if it's a Pakistani number (starts with 92)
                        normalized_phone_e164 = normalized_phone_digits
                        if normalized_phone_digits and len(normalized_phone_digits) >= 10:
                            # If it starts with 92 (Pakistan country code without +), add +
                            if normalized_phone_digits.startswith('92') and len(normalized_phone_digits) >= 11:
                                normalized_phone_e164 = '+' + normalized_phone_digits
                            # If it's 10 digits and starts with 0, convert to +92 format
                            elif len(normalized_phone_digits) == 10 and normalized_phone_digits.startswith('0'):
                                normalized_phone_e164 = '+92' + normalized_phone_digits[1:]
                            # If it's 10 digits without country code, assume Pakistan
                            elif len(normalized_phone_digits) == 10:
                                normalized_phone_e164 = '+92' + normalized_phone_digits
                        
                        # Use normalized digits as key for deduplication (consistent with lookup)
                        # But store E.164 format in the contact data
                        if normalized_phone_digits and normalized_phone_digits not in contacts_dict:
                            # Clean email - handle truncated emails
                            clean_email = None
                            if owner_email:
                                email_clean = owner_email.lower().strip()
                                # If email doesn't have @domain, try to fix common truncations
                                if '@' not in email_clean:
                                    # If it looks like a name, add @email.com
                                    if email_clean and '.' in email_clean:
                                        clean_email = email_clean + "@email.com"
                                    else:
                                        clean_email = None
                                else:
                                    clean_email = email_clean
                            
                            contacts_dict[normalized_phone_digits] = {
                                "name": owner_name,
                                "phone_number": normalized_phone_e164,  # Store E.164 format
                                "email": clean_email,
                            }
                            print(f"  📇 Extracted contact: {owner_name} - {normalized_phone_e164} ({normalized_phone_digits})")
                        else:
                            print(f"  ⏭️ Skipped duplicate contact: {owner_name} - {normalized_phone_digits}")
                    else:
                        if not owner_name:
                            print(f"  ⚠️ Row {idx}: Missing owner name")
                        if not owner_phone:
                            print(f"  ⚠️ Row {idx}: Missing owner phone")
                            
            except Exception as row_err:
                print(f"⚠️ Warning: failed to parse CSV row {idx}: {row_err}")
                import traceback
                print(f"   Traceback: {traceback.format_exc()}")
                continue
        
        print(f"CSV Parser - Extracted {len(properties)} properties, {len(contacts_dict)} unique contacts")
        
        # Check if all phone numbers are the same (indicates Excel scientific notation issue)
        if len(contacts_dict) == 1 and len(properties) > 1:
            sample_phone = list(contacts_dict.keys())[0]
            # Check if phone ends with many zeros (likely lost precision from scientific notation)
            if sample_phone.endswith('0000000') and len(sample_phone) >= 11:
                print(f"\n{'='*60}")
                print(f"⚠️  WARNING: PHONE NUMBER PRECISION LOSS DETECTED")
                print(f"{'='*60}")
                print(f"All phone numbers appear to be the same: {sample_phone}")
                print(f"This usually happens when Excel converts phone numbers to scientific notation.")
                print(f"\n💡 SOLUTION:")
                print(f"1. Open your CSV in Excel")
                print(f"2. Select the phone number column(s)")
                print(f"3. Right-click → Format Cells → Text")
                print(f"4. Re-enter the phone numbers (or paste them)")
                print(f"5. Save the CSV again")
                print(f"6. Re-upload the CSV")
                print(f"\nAlternatively, use a text editor to edit the CSV directly.")
                print(f"{'='*60}\n")
        
        return {
            "properties": properties,
            "contacts": list(contacts_dict.values())
        }
    except Exception as e:
        print(f"CSV Parser Error: {str(e)}")
        raise ValueError(f"Failed to parse CSV: {str(e)}")


async def parse_pdf(file_content: bytes) -> List[Dict]:
    """Parse PDF file and extract property data"""
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
        text_content = ""
        
        for page in pdf_reader.pages:
            text_content += page.extract_text()
        
        return [{
            "property_type": "",
            "address": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "price": None,
            "bedrooms": None,
            "bathrooms": None,
            "square_feet": None,
            "description": text_content[:1000],
            "amenities": "",
            "owner_name": "",
            "owner_phone": "",
            "is_available": "true",
        }]
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")


async def parse_docx(file_content: bytes) -> List[Dict]:
    """Parse DOCX file and extract property data"""
    try:
        doc = Document(BytesIO(file_content))
        text_content = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        
        return [{
            "property_type": "",
            "address": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "price": None,
            "bedrooms": None,
            "bathrooms": None,
            "square_feet": None,
            "description": text_content[:1000],
            "amenities": "",
            "owner_name": "",
            "owner_phone": "",
            "is_available": "true",
        }]
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX: {str(e)}")


async def parse_document(file_content: bytes, file_type: str) -> Dict:
    """
    Parse document based on file type
    Returns: {"properties": [...], "contacts": [...]}
    For CSV: extracts both properties and contacts
    For PDF/DOCX: returns properties only (contacts empty)
    """
    if file_type == "csv":
        return await parse_csv(file_content)
    elif file_type == "pdf":
        parsed_props = await parse_pdf(file_content)
        return {"properties": parsed_props, "contacts": []}
    elif file_type == "docx":
        parsed_props = await parse_docx(file_content)
        return {"properties": parsed_props, "contacts": []}
    else:
        raise ValueError(f"Unsupported file type: {file_type}")
