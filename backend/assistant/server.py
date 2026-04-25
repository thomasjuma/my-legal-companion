"""
Legal Researcher Service - Legal Research Agent
"""

import os
import logging
from datetime import datetime, UTC
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agents import Agent, Runner, trace
from agents.extensions.models.litellm_model import LitellmModel

# Suppress LiteLLM warnings about optional dependencies
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)

# Import from our modules
from utilities import chunk_legal_documents
from context import get_agent_instructions, DEFAULT_RESEARCH_PROMPT
from mcp_servers import create_playwright_mcp_server
from tools import ingest_legal_document
from tools import ingest_batch_with_retries

# Load environment
load_dotenv(override=True)

app = FastAPI(title="Legal Researcher Service")


# Request model
class ResearchRequest(BaseModel):
    topic: Optional[str] = None  # Optional - if not provided, agent picks a topic


async def run_research_agent(topic: str = None) -> str:
    """Run the research agent to do legal research and identify relevant changes in laws and regulations."""

    # Prepare the user query
    if topic:
        query = f"Research this legal topic: {topic}"
    else:
        query = DEFAULT_RESEARCH_PROMPT

    # Please override these variables with the region you are using
    # Other choices: us-west-2 (for OpenAI OSS models) and eu-central-1
    # Match DEFAULT_AWS_REGION / App Runner when using regional inference profiles
    REGION = "eu-west-1"
    os.environ["AWS_REGION_NAME"] = REGION  # LiteLLM's preferred variable
    os.environ["AWS_REGION"] = REGION  # Boto3 standard
    os.environ["AWS_DEFAULT_REGION"] = REGION  # Fallback

    # Please override this variable with the model you are using
    # Common choices: bedrock/eu.amazon.nova-pro-v1:0 for EU and bedrock/us.amazon.nova-pro-v1:0 for US
    # or bedrock/amazon.nova-pro-v1:0 if you are not using inference profiles
    # bedrock/openai.gpt-oss-120b-1:0 for OpenAI OSS models
    # bedrock/converse/us.anthropic.claude-sonnet-4-20250514-v1:0 for Claude Sonnet 4
    # NOTE that nova-pro is needed to support tools and MCP servers; nova-lite is not enough - thank you Yuelin L.!
    MODEL = (os.getenv("RESEARCHER_MODEL") or "bedrock/eu.amazon.nova-pro-v1:0").strip()
    if not MODEL:
        logging.getLogger(__name__).warning(
            "RESEARCHER_MODEL is unset or empty; using default %s", MODEL
        )
    model = LitellmModel(model=MODEL)

    # Create and run the agent with MCP server
    with trace("Researcher"):
        async with create_playwright_mcp_server(timeout_seconds=60) as playwright_mcp:
            agent = Agent(
                name="Counsel, the Legal Researcher",
                instructions=get_agent_instructions(),
                model=model,
                tools=[ingest_legal_document],
                mcp_servers=[playwright_mcp],
            )

            result = await Runner.run(agent, input=query, max_turns=15)

    return result.final_output


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Legal Researcher",
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/research")
async def research(request: ResearchRequest) -> str:
    """
    Generate legal research and identify relevant changes in laws and regulations.

    The agent will:
    1. Browse current legal websites for data
    2. Analyze the information found
    3. Store the analysis in the legal knowledge base

    If no topic is provided, the agent will pick a trending topic.
    """
    try:
        response = await run_research_agent(request.topic)
        return response
    except Exception as e:
        print(f"Error in research endpoint: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Align with Counsel ingest Lambda BATCH_INGEST_MAX_ITEMS (default 32)
EMBED_AUTO_BATCH_SIZE = int(os.getenv("EMBED_AUTO_BATCH_SIZE", "32"))


@app.get("/embed")
def embed_auto():
    """
    Chunk Google Drive legal docs and ingest in bulk: one API request per batch
    (single SageMaker batch embed per request on the Lambda).
    """
    if not os.getenv("COUNSEL_API_ENDPOINT") or not os.getenv("COUNSEL_API_KEY"):
        return {
            "status": "error",
            "error": "Counsel API not configured",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    try:
        chunks = chunk_legal_documents()
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    if not chunks:
        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "No chunks to embed",
            "chunk_count": 0,
            "batches": [],
            "document_ids": [],
        }

    base_ts = datetime.now(UTC).isoformat()
    all_document_ids: list[str] = []
    batch_summaries: list[dict] = []

    for batch_start in range(0, len(chunks), EMBED_AUTO_BATCH_SIZE):
        window = chunks[batch_start : batch_start + EMBED_AUTO_BATCH_SIZE]
        items = [
            {
                "text": chunk.page_content,
                "metadata": {
                    **(chunk.metadata or {}),
                    "timestamp": base_ts,
                    "source": "embed_auto",
                    "chunk_index": batch_start + j,
                },
            }
            for j, chunk in enumerate(window)
        ]
        try:
            result = ingest_batch_with_retries(items)
            doc_ids = result.get("document_ids") or []
            all_document_ids.extend(doc_ids)
            batch_summaries.append(
                {
                    "start_index": batch_start,
                    "end_index": batch_start + len(window) - 1,
                    "ok": True,
                    "count": result.get("count", len(doc_ids)),
                    "document_ids": doc_ids,
                }
            )
        except Exception as e:
            batch_summaries.append(
                {
                    "start_index": batch_start,
                    "end_index": batch_start + len(window) - 1,
                    "ok": False,
                    "error": str(e),
                }
            )

    any_failed = any(not b.get("ok", False) for b in batch_summaries)
    if not any_failed:
        status = "success"
    elif all_document_ids:
        status = "partial"
    else:
        status = "error"

    first_text = chunks[0].page_content
    return {
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        "message": (
            "Automated embedding completed"
            if not any_failed
            else "Some batches failed; see batch summaries"
        ),
        "chunk_count": len(chunks),
        "batch_size": EMBED_AUTO_BATCH_SIZE,
        "batches": batch_summaries,
        "document_ids": all_document_ids,
        "preview": first_text[:200] + "..." if len(first_text) > 200 else first_text,
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    # Debug container detection
    container_indicators = {
        "dockerenv": os.path.exists("/.dockerenv"),
        "containerenv": os.path.exists("/run/.containerenv"),
        "aws_execution_env": os.environ.get("AWS_EXECUTION_ENV", ""),
        "ecs_container_metadata": os.environ.get("ECS_CONTAINER_METADATA_URI", ""),
        "kubernetes_service": os.environ.get("KUBERNETES_SERVICE_HOST", ""),
    }

    return {
        "service": "Legal Researcher",
        "status": "healthy",
        "counsel_api_configured": bool(os.getenv("COUNSEL_API_ENDPOINT") and os.getenv("COUNSEL_API_KEY")),
        "timestamp": datetime.now(UTC).isoformat(),
        "debug_container": container_indicators,
        "aws_region": os.environ.get("AWS_DEFAULT_REGION", "not set"),
        "bedrock_model": (os.getenv("RESEARCHER_MODEL") or "").strip()
    }


@app.get("/test-bedrock")
async def test_bedrock():
    """Test Bedrock connection directly."""
    try:
        import boto3

        # Set ALL region environment variables
        os.environ["AWS_REGION_NAME"] = "us-east-1"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        # Debug: Check what region boto3 is actually using
        session = boto3.Session()
        actual_region = session.region_name

        # Try to create Bedrock client explicitly in us-west-2
        client = boto3.client("bedrock-runtime", region_name="us-west-2")

        # Debug: Try to list models to verify connection
        try:
            bedrock_client = boto3.client("bedrock", region_name="us-west-2")
            models = bedrock_client.list_foundation_models()
            openai_models = [
                m["modelId"] for m in models["modelSummaries"] if "openai" in m["modelId"].lower()
            ]
        except Exception as list_error:
            openai_models = f"Error listing: {str(list_error)}"

        # Try basic model invocation with Nova Pro
        model = LitellmModel(model="bedrock/amazon.nova-pro-v1:0")

        agent = Agent(
            name="Test Agent",
            instructions="You are a helpful assistant. Be very brief.",
            model=model,
        )

        result = await Runner.run(agent, input="Say hello in 5 words or less", max_turns=1)

        return {
            "status": "success",
            "model": str(model.model),  # Use actual model from LitellmModel
            "region": actual_region,
            "response": result.final_output,
            "debug": {
                "boto3_session_region": actual_region,
                "available_openai_models": openai_models,
            },
        }
    except Exception as e:
        import traceback

        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "debug": {
                "boto3_session_region": session.region_name if "session" in locals() else "unknown",
                "env_vars": {
                    "AWS_REGION_NAME": os.environ.get("AWS_REGION_NAME"),
                    "AWS_REGION": os.environ.get("AWS_REGION"),
                    "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION"),
                },
            },
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
