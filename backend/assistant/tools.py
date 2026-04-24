"""
Tools for the Legal Researcher agent
"""
import os
from typing import Dict, Any
from datetime import datetime, UTC
import httpx
from agents import function_tool
from tenacity import retry, stop_after_attempt, wait_exponential

# Configuration from environment
COUNSEL_API_ENDPOINT = os.getenv("COUNSEL_API_ENDPOINT")
COUNSEL_API_KEY = os.getenv("COUNSEL_API_KEY")


def _ingest(document: Dict[str, Any]) -> Dict[str, Any]:
    """Internal function to make the actual API call."""
    with httpx.Client() as client:
        response = client.post(
            COUNSEL_API_ENDPOINT,
            json=document,
            headers={"x-api-key": COUNSEL_API_KEY},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def ingest_with_retries(document: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest with retry logic for SageMaker cold starts."""
    return _ingest(document)


@function_tool
def ingest_legal_document(topic: str, analysis: str) -> Dict[str, Any]:
    """
    Ingest a legal document into the legal knowledge base.
    
    Args:
        topic: The topic or subject of the analysis (e.g., "Corporate Law", "Employment Law")
        analysis: Detailed analysis or advice with specific data and insights
    
    Returns:
        Dictionary with success status and document ID
    """
    if not COUNSEL_API_ENDPOINT or not COUNSEL_API_KEY:
        return {
            "success": False,
            "error": "Counsel API not configured. Running in local mode."
        }
    
    document = {
        "text": analysis,
        "metadata": {
            "topic": topic,
            "timestamp": datetime.now(UTC).isoformat()
        }
    }
    
    try:
        result = ingest_with_retries(document)
        return {
            "success": True,
            "document_id": result.get("document_id"),  # Changed from documentId
            "message": f"Successfully ingested analysis for {topic}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def _ingest_batch(items: list[dict]) -> Dict[str, Any]:
    with httpx.Client() as client:
        response = client.post(
            COUNSEL_API_ENDPOINT,
            json={"items": items},
            headers={"x-api-key": COUNSEL_API_KEY},
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def ingest_batch_with_retries(items: list[dict]) -> Dict[str, Any]:
    return _ingest_batch(items)
