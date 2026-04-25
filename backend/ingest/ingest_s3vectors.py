"""
Lambda function for ingesting text into S3 Vectors with embeddings.

Supports:
- Single document: {"text": "...", "metadata": {...}}
- Batch: {"items": [{"text": "...", "metadata": {...}}, ...]}
  (alias key "documents" is also accepted)
"""

import json
import os
import boto3
import datetime
import uuid

# Environment variables
VECTOR_BUCKET = os.environ.get("VECTOR_BUCKET", "counsel-vectors")
SAGEMAKER_ENDPOINT = os.environ.get("SAGEMAKER_ENDPOINT")
INDEX_NAME = os.environ.get("INDEX_NAME", "legal-research")
BATCH_INGEST_MAX_ITEMS = int(os.environ.get("BATCH_INGEST_MAX_ITEMS", "32"))
PUT_VECTORS_CHUNK_SIZE = int(os.environ.get("PUT_VECTORS_CHUNK_SIZE", "50"))

# Initialize AWS clients
sagemaker_runtime = boto3.client("sagemaker-runtime")
s3_vectors = boto3.client("s3vectors")


def parse_single_embedding(result):
    """
    Extract one embedding vector (list of floats) from HuggingFace
    feature-extraction JSON (handles common nested list shapes).
    """
    if not isinstance(result, list):
        raise ValueError(f"Expected list from embedding model, got {type(result).__name__}")

    cur = result
    while isinstance(cur, list) and len(cur) > 0:
        first = cur[0]
        if isinstance(first, (int, float)):
            return [float(x) for x in cur]
        cur = first

    raise ValueError("Could not parse embedding: empty or unrecognized nesting")


def parse_batch_embeddings(result, num_texts: int) -> list[list[float]]:
    """Turn SageMaker JSON body into a list of `num_texts` embedding vectors."""
    if num_texts == 0:
        return []
    if num_texts == 1:
        return [parse_single_embedding(result)]

    if not isinstance(result, list):
        raise ValueError(f"Expected list from embedding model, got {type(result).__name__}")

    if len(result) == num_texts:
        return [parse_single_embedding(elem) for elem in result]

    if (
        len(result) == 1
        and isinstance(result[0], list)
        and len(result[0]) == num_texts
    ):
        return [parse_single_embedding(elem) for elem in result[0]]

    raise ValueError(
        "Embedding batch size mismatch: expected "
        f"{num_texts} sequences in model output, got top-level length {len(result)}"
    )


def get_embedding(text: str) -> list[float]:
    """Get a single embedding from SageMaker (string input — legacy HF contract)."""
    if not SAGEMAKER_ENDPOINT:
        raise ValueError("SAGEMAKER_ENDPOINT is not configured")

    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType="application/json",
        Body=json.dumps({"inputs": text}),
    )

    result = json.loads(response["Body"].read().decode())
    return parse_single_embedding(result)


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Batch embedding: one SageMaker invoke with a list of strings.

    HuggingFace `feature-extraction` on SageMaker typically accepts
    {"inputs": ["a", "b", ...]} and returns one representation per input.
    """
    if not texts:
        return []
    if not SAGEMAKER_ENDPOINT:
        raise ValueError("SAGEMAKER_ENDPOINT is not configured")

    if len(texts) == 1:
        return [get_embedding(texts[0])]

    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType="application/json",
        Body=json.dumps({"inputs": texts}),
    )

    result = json.loads(response["Body"].read().decode())
    return parse_batch_embeddings(result, len(texts))


def put_vectors_in_chunks(vectors: list[dict]) -> None:
    """Write vectors to S3 Vectors in chunks within service limits."""
    for i in range(0, len(vectors), PUT_VECTORS_CHUNK_SIZE):
        chunk = vectors[i : i + PUT_VECTORS_CHUNK_SIZE]
        print(
            f"Putting vectors {i}-{i + len(chunk) - 1} to "
            f"bucket={VECTOR_BUCKET} index={INDEX_NAME}"
        )
        s3_vectors.put_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=INDEX_NAME,
            vectors=chunk,
        )


def _normalize_batch_items(raw_items: list) -> tuple[list[str], list[dict]]:
    """Validate batch payload; return parallel lists of texts and metadata dicts."""
    texts = []
    metas = []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            raise ValueError(f"items[{idx}] must be an object with 'text'")
        text = item.get("text")
        if not text or not isinstance(text, str):
            raise ValueError(
                f"items[{idx}].text is required and must be a non-empty string"
            )
        meta = item.get("metadata") or {}
        if not isinstance(meta, dict):
            raise ValueError(f"items[{idx}].metadata must be an object if present")
        texts.append(text)
        metas.append(meta)
    return texts, metas


def handle_batch_ingest(items: list) -> dict:
    """Embed all texts in one batch invoke, then put all vectors (chunked)."""
    if len(items) > BATCH_INGEST_MAX_ITEMS:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "error": (
                        f"Batch too large: max {BATCH_INGEST_MAX_ITEMS} items "
                        "(set BATCH_INGEST_MAX_ITEMS to raise the limit)."
                    )
                }
            ),
        }

    texts, metadatas = _normalize_batch_items(items)
    print(f"Batch inference for {len(texts)} texts (single SageMaker invoke)...")
    embeddings = get_embeddings_batch(texts)

    if len(embeddings) != len(texts):
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": (
                        f"Embedding count mismatch: got {len(embeddings)} vectors "
                        f"for {len(texts)} texts"
                    )
                }
            ),
        }

    ts = datetime.datetime.now(datetime.UTC).isoformat()
    document_ids = []
    vectors = []

    for text, meta, embedding in zip(texts, metadatas, embeddings):
        vector_id = str(uuid.uuid4())
        document_ids.append(vector_id)
        vectors.append(
            {
                "key": vector_id,
                "data": {"float32": embedding},
                "metadata": {
                    "text": text,
                    "timestamp": ts,
                    **meta,
                },
            }
        )

    put_vectors_in_chunks(vectors)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"{len(document_ids)} documents indexed successfully",
                "document_ids": document_ids,
                "count": len(document_ids),
            }
        ),
    }


def handle_single_ingest(text: str, metadata: dict) -> dict:
    """Legacy single-document path (unchanged behavior for callers)."""
    print(f"Getting embedding for text: {text[:100]}...")
    embedding = get_embedding(text)
    vector_id = str(uuid.uuid4())

    print(f"Storing vector in bucket: {VECTOR_BUCKET}, index: {INDEX_NAME}")
    s3_vectors.put_vectors(
        vectorBucketName=VECTOR_BUCKET,
        indexName=INDEX_NAME,
        vectors=[
            {
                "key": vector_id,
                "data": {"float32": embedding},
                "metadata": {
                    "text": text,
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    **metadata,
                },
            }
        ],
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Document indexed successfully",
                "document_id": vector_id,
            }
        ),
    }


def lambda_handler(event, context):
    """
    Single document body:
        {"text": "...", "metadata": {...}}

    Batch body (either key):
        {"items": [{"text": "...", "metadata": {...}}, ...]}
        {"documents": [...]}

    Environment:
        BATCH_INGEST_MAX_ITEMS (default 32), PUT_VECTORS_CHUNK_SIZE (default 50)
    """
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body") or {}

        items = body.get("items")
        if items is None:
            items = body.get("documents")

        if items is not None:
            if not isinstance(items, list):
                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {"error": "'items' (or 'documents') must be a JSON array"}
                    ),
                }
            if len(items) == 0:
                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {"error": "Batch array is empty; send at least one item"}
                    ),
                }
            return handle_batch_ingest(items)

        text = body.get("text")
        metadata = body.get("metadata") or {}
        if not isinstance(metadata, dict):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "metadata must be an object"}),
            }

        if not text:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "error": (
                            "Missing required field: text. "
                            "For batch ingest, send non-empty 'items': "
                            '[{"text":"...","metadata":{}}]'
                        )
                    }
                ),
            }

        return handle_single_ingest(text, metadata)

    except ValueError as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e)}),
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }