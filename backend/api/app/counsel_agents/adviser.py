import os
import json
import logging
import boto3
from dotenv import load_dotenv

from agents import Agent, function_tool
from agents.extensions.models.litellm_model import LitellmModel

load_dotenv()
logger = logging.getLogger(__name__)

INSTRUCTIONS = """You are a knowledgable and a qualified lawyer to whom individuals can seek legal guidance and advice. 
They may be facing a legal issue, need help navigating complex laws or want to prevent potential legal challenges. Your 
goal is to provide clear, practical and actionable advice to help them understand their legal options and make informed decisions.

You will be given a detailed description of the legal issue or question and your task is to analyze the situation, identify 
the relevant laws and regulations, and provide a step-by-step plan for addressing the issue.

You will also be given a list of relevant laws and regulations that may be applicable to the situation.

You will also be given a list of relevant legal precedents that may be applicable to the situation.

You will also be given a list of relevant legal cases that may be applicable to the situation.

Please ask two to three follow-up questions in a conversational manner to better understand the situation and the legal issue if 
needed. Do not ask more than three follow-up questions. Only ask follow-up questions if the user has not provided enough information.

Also, you are provided with a tool to retrieve legal references from a S3 Vectors knowledge base. Based on the legal issue, 
formulate a query to use this tool to retrieve relevant information from the knowledge base. Use the retrieved information to 
provide a detailed and comprehensive advice to the user.
"""

ANTHROPIC_MODEL_ID = os.getenv("ANTHROPIC_MODEL_ID", "claude-sonnet-4-20250514")
ANTHROPIC_MODEL = f"anthropic/{ANTHROPIC_MODEL_ID}"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

OPENAI_MODEL = f"openai/{OPENAI_MODEL}"

class AdviserAgent:
    def __init__(self):
        self.adviser_model = LitellmModel(model=OPENAI_MODEL)
        

    def get_adviser_agent(self):
        return Agent(
            name="Adviser",
            instructions=INSTRUCTIONS,
            tools=self.get_adviser_tools(),
            model=self.adviser_model,
        )

    def get_adviser_tools(self):
        return [get_legal_references]   

@function_tool
async def get_legal_references(legal_issue: str = "The legal issue to get references for") -> str:
    """
    Retrieve legal references from S3 Vectors knowledge base. The knowledge base base contains the constitution and other 
    legislative acts.

    Args:
        legal_issue: The legal issue to get references for (default: "The legal issue to get references for")

    Returns:
        Relevant articles and sections from the constitution and other legislative acts
    """
    try:
        # Get account ID
        sts = boto3.client("sts")
        account_id = sts.get_caller_identity()["Account"]
        bucket = f"counsel-vectors-{account_id}"

        # Get embeddings
        sagemaker_region = os.getenv("DEFAULT_AWS_REGION", "eu-west-1")
        sagemaker = boto3.client("sagemaker-runtime", region_name=sagemaker_region)
        endpoint_name = os.getenv("SAGEMAKER_ENDPOINT", "counsel-embedding-endpoint")
        query = f"legal references {legal_issue}"

        response = sagemaker.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps({"inputs": query}),
        )

        result = json.loads(response["Body"].read().decode())
        # Extract embedding (handle nested arrays)
        if isinstance(result, list) and result:
            embedding = result[0][0] if isinstance(result[0], list) else result[0]
        else:
            embedding = result

        # Search vectors
        s3v = boto3.client("s3vectors", region_name=sagemaker_region)
        response = s3v.query_vectors(
            vectorBucketName=bucket,
            indexName="legal-research",
            queryVector={"float32": embedding},
            topK=3,
            returnMetadata=True,
        )

        # Format references
        references = []
        for vector in response.get("vectors", []):
            metadata = vector.get("metadata", {})
            text = metadata.get("text", "")[:200]
            if text:
                legal_reference = metadata.get("legal_reference", "")
                prefix = f"{legal_reference}: " if legal_reference else "- "
                references.append(f"{prefix}{text}...")

        if references:
            return "Legal References:\n" + "\n".join(references)
        else:
            return "Legal references unavailable - proceeding with standard advice."

    except Exception as e:
        logger.warning(f"Adviser: Could not retrieve legal references: {e}")
        return "Legal references unavailable - proceeding with standard advice."
