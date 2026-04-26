import os
import json
import logging
from agents import function_tool
import boto3
logger = logging.getLogger(__name__)


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
