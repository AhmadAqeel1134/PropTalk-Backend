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
    try:
        df = pd.read_csv(
            StringIO(text),
            sep=delimiter,
            quotechar='"',
            escapechar='\\',
            on_bad_lines='skip',
            dtype=str,
            keep_default_na=False
        )
        return df
    except Exception:
        # Fallback: let pandas auto-detect
        return pd.read_csv(
            StringIO(text),
            sep=None,
            engine='python',
            dtype=str,
            keep_default_na=False
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
                # Safe get function that handles missing columns
                def get_val(col_name: str, default: str = "") -> str:
                    if col_name in df.columns:
                        val = row[col_name]
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

                # Parse fields
                price = parse_float(get_val("price"))
                bedrooms = parse_int(get_val("bedrooms"))
                bathrooms = parse_float(get_val("bathrooms"))
                square_feet = parse_int(get_val("square_feet"))
                
                # Get owner info
                owner_name = get_val("owner_name")
                owner_phone = get_val("owner_phone")
                owner_email = get_val("owner_email")
                
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
                    "property_type": get_val("property_type"),
                    "address": get_val("address"),
                    "city": get_val("city"),
                    "state": get_val("state"),
                    "zip_code": get_val("zip_code"),
                    "price": price,
                    "bedrooms": bedrooms,
                    "bathrooms": bathrooms,
                    "square_feet": square_feet,
                    "description": get_val("description"),
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
                        normalized_phone = ''.join(filter(str.isdigit, owner_phone))
                        if normalized_phone and normalized_phone not in contacts_dict:
                            contacts_dict[normalized_phone] = {
                                "name": owner_name,
                                "phone_number": normalized_phone,
                                "email": owner_email.lower() if owner_email else None,
                            }
                            
            except Exception as row_err:
                print(f"Warning: failed to parse CSV row {idx}: {row_err}")
                continue
        
        print(f"CSV Parser - Extracted {len(properties)} properties, {len(contacts_dict)} unique contacts")
        
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
