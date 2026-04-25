"""
Test script for ingesting documents directly to S3 Vectors.
This bypasses API Gateway and tests the S3 Vectors service directly.
"""

import os
import json
import boto3
import uuid
import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

# Get configuration
VECTOR_BUCKET = os.getenv('VECTOR_BUCKET')
SAGEMAKER_ENDPOINT = os.getenv('SAGEMAKER_ENDPOINT', 'counsel-embedding-endpoint')
INDEX_NAME = 'legal-research'

if not VECTOR_BUCKET:
    print("Error: Please run Guide 3 Step 4 to save VECTOR_BUCKET to .env")
    exit(1)

# Initialize AWS clients
s3_vectors = boto3.client('s3vectors')
sagemaker_runtime = boto3.client('sagemaker-runtime')

def get_embedding(text):
    """Get embedding vector from SageMaker endpoint."""
    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType='application/json',
        Body=json.dumps({'inputs': text})
    )
    
    result = json.loads(response['Body'].read().decode())
    # HuggingFace returns nested array [[[embedding]]], extract the actual embedding
    if isinstance(result, list) and len(result) > 0:
        if isinstance(result[0], list) and len(result[0]) > 0:
            if isinstance(result[0][0], list):
                return result[0][0]  # Extract from [[[embedding]]]
            return result[0]  # Extract from [[embedding]]
    return result  # Return as-is if not nested

def ingest_document(text, metadata=None):
    """Ingest a document directly to S3 Vectors."""
    # Get embedding from SageMaker
    print(f"Getting embedding for text: {text[:100]}...")
    embedding = get_embedding(text)
    
    # Generate unique ID for the vector
    vector_id = str(uuid.uuid4())
    
    # Store in S3 Vectors
    print(f"Storing vector in bucket: {VECTOR_BUCKET}, index: {INDEX_NAME}")
    s3_vectors.put_vectors(
        vectorBucketName=VECTOR_BUCKET,
        indexName=INDEX_NAME,
        vectors=[{
            "key": vector_id,
            "data": {"float32": embedding},
            "metadata": {
                "text": text,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                **(metadata or {})  # Include any additional metadata
            }
        }]
    )
    
    return vector_id

def main():
    """Test direct ingestion to S3 Vectors."""
    
    print("Testing S3 Vectors Direct Ingestion")
    print("=" * 60)
    print(f"Bucket: {VECTOR_BUCKET}")
    print(f"Index: {INDEX_NAME}")
    print(f"Embedding Model: {SAGEMAKER_ENDPOINT}")
    print()
    
    # Test documents
    test_docs = [
        {
            "text": (
                "A valid contract requires mutual assent (offer and acceptance), consideration, "
                "parties with legal capacity, and a lawful purpose. Courts may refuse to enforce "
                "agreements procured by fraud, duress, or unconscionable terms."
            ),
            "metadata": {
                "doc_id": "contracts-basics-001",
                "title": "Contract formation (general principles)",
                "domain": "Contract law",
                "source": "legal_companion_sample",
            },
        },
        {
            "text": (
                "Attorney-client privilege protects confidential communications between a client and "
                "counsel made for the purpose of obtaining legal advice. The privilege generally belongs "
                "to the client and may be waived only by the client, subject to limited exceptions."
            ),
            "metadata": {
                "doc_id": "privilege-001",
                "title": "Attorney-client privilege overview",
                "domain": "Professional responsibility / evidence",
                "source": "legal_companion_sample",
            },
        },
        {
            "text": (
                "Summary judgment is appropriate when there is no genuine dispute as to any material fact "
                "and the movant is entitled to judgment as a matter of law. The court views the evidence "
                "in the light most favorable to the non-moving party."
            ),
            "metadata": {
                "doc_id": "civ-pro-summary-judgment-001",
                "title": "Standard for summary judgment",
                "domain": "Civil procedure",
                "source": "legal_companion_sample",
            },
        },
                {
            "text": (
                "Negligence requires a duty of care, breach of that duty, causation (actual and proximate), "
                "and damages. A defendant's conduct is often measured against the reasonable person standard "
                "unless a professional or heightened duty applies."
            ),
            "metadata": {
                "doc_id": "torts-negligence-001",
                "title": "Elements of negligence",
                "domain": "Torts",
                "source": "legal_companion_sample",
            },
        },
        {
            "text": (
                "The Fourth Amendment limits unreasonable searches and seizures; warrantless searches are "
                "presumptively unreasonable unless an established exception applies (for example, consent, "
                "exigent circumstances, or search incident to a lawful arrest), subject to judicial "
                "interpretation and fact-specific analysis."
            ),
            "metadata": {
                "doc_id": "crim-pro-4th-amend-001",
                "title": "Fourth Amendment and warrant exceptions (overview)",
                "domain": "Criminal procedure / constitutional law",
                "source": "legal_companion_sample",
            },
        },
    ]
    
    # Ingest each document
    for i, doc in enumerate(test_docs, 1):
        print(f"Ingesting document {i}: {doc['metadata'].get('doc_id', 'Unknown')}")
        try:
            doc_id = ingest_document(doc['text'], doc['metadata'])
            print(f"  ✓ Success! Document ID: {doc_id}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        print()
    
    print("Testing complete!")
    print("\nYour S3 Vectors knowledge base now contains information about:")
    for doc in test_docs:
        print(f"  - {doc['metadata']['title']} ({doc['metadata']['doc_id']})")
    
    print("\n⏱️  Note: S3 Vectors updates are available immediately.")
    print("   You can run test_search_s3vectors.py right away to search!")

if __name__ == "__main__":
    main()