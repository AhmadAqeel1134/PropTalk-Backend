import pandas as pd
import PyPDF2
from docx import Document
from io import BytesIO
from typing import List, Dict
import json


async def parse_csv(file_content: bytes) -> List[Dict]:
    """Parse CSV file and extract property data"""
    try:
        df = pd.read_csv(BytesIO(file_content))
        
        properties = []
        for _, row in df.iterrows():
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
        
        return properties
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


async def parse_document(file_content: bytes, file_type: str) -> List[Dict]:
    """Parse document based on file type"""
    if file_type == "csv":
        return await parse_csv(file_content)
    elif file_type == "pdf":
        return await parse_pdf(file_content)
    elif file_type == "docx":
        return await parse_docx(file_content)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

