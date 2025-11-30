import pandas as pd
import PyPDF2
from docx import Document
from io import BytesIO
from typing import List, Dict
import json


async def parse_csv(file_content: bytes) -> Dict:
    """
    Parse CSV file and extract property data and contacts
    Returns: {"properties": [...], "contacts": [...]}
    """
    try:
        df = pd.read_csv(BytesIO(file_content))
        
        properties = []
        contacts_dict = {}  # Use dict to deduplicate contacts by phone
        
        for _, row in df.iterrows():
            # Extract property data
            property_data = {
                "property_type": str(row.get("property_type", "")),
                "address": str(row.get("address", "")),
                "city": str(row.get("city", "")),
                "state": str(row.get("state", "")),
                "zip_code": str(row.get("zip_code", "")),
                "price": float(row.get("price", 0)) if pd.notna(row.get("price")) else None,
                "bedrooms": int(row.get("bedrooms", 0)) if pd.notna(row.get("bedrooms")) else None,
                "bathrooms": int(row.get("bathrooms", 0)) if pd.notna(row.get("bathrooms")) else None,
                "square_feet": int(row.get("square_feet", 0)) if pd.notna(row.get("square_feet")) else None,
                "description": str(row.get("description", "")),
                "amenities": str(row.get("amenities", "")),
                "owner_name": str(row.get("owner_name", "")),
                "owner_phone": str(row.get("owner_phone", "")),
                "is_available": str(row.get("is_available", "true")).lower(),
            }
            properties.append(property_data)
            
            # Extract contact data (deduplicate by phone)
            owner_name = str(row.get("owner_name", "")).strip()
            owner_phone = str(row.get("owner_phone", "")).strip()
            owner_email = str(row.get("owner_email", "")).strip() if pd.notna(row.get("owner_email", None)) else None
            
            if owner_name and owner_phone:
                # Normalize phone for deduplication
                normalized_phone = ''.join(filter(str.isdigit, owner_phone))
                if normalized_phone and normalized_phone not in contacts_dict:
                    contacts_dict[normalized_phone] = {
                        "name": owner_name,
                        "phone_number": normalized_phone,
                        "email": owner_email.lower() if owner_email else None,
                    }
        
        return {
            "properties": properties,
            "contacts": list(contacts_dict.values())
        }
    except Exception as e:
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

