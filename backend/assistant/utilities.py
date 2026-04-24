import os
from langchain_core.documents import Document
from dotenv import load_dotenv
from pathlib import Path
from google_drive_client import GoogleDriveClient
from chunking import chunk_documents

# Load environment variables from project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path, override=True)

google_drive_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
# OAuth client JSON (preferred in containers / App Runner). Same content as the downloaded client secret file.
google_drive_credentials_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON")


def _load_google_drive_credentials_json() -> str | None:
    """Resolve OAuth client config as a JSON string (env or legacy file path)."""
    if google_drive_credentials_json and google_drive_credentials_json.strip():
        return google_drive_credentials_json
    if google_drive_credentials_path:
        path = Path(google_drive_credentials_path)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


_credentials_source = (
    "GOOGLE_DRIVE_CREDENTIALS_JSON"
    if google_drive_credentials_json and google_drive_credentials_json.strip()
    else (
        f"file:{google_drive_credentials_path}"
        if google_drive_credentials_path
        else "none"
    )
)
print(f"Google Drive credentials source: {_credentials_source}")
print(f"Google Drive Folder ID: {google_drive_folder_id}")


def fetch_legal_documents():
    """Fetch legal documents from Google Drive."""
    credentials_json = _load_google_drive_credentials_json()
    if not credentials_json:
        raise ValueError(
            "Set GOOGLE_DRIVE_CREDENTIALS_JSON to the OAuth client JSON string, "
            "or set GOOGLE_APPLICATION_CREDENTIALS to a path to that JSON file."
        )
    if not google_drive_folder_id:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID is not set")

    collector = GoogleDriveClient(credentials_json, google_drive_folder_id)
    collector.collect_files()

    # Files from a Google Drive folder in markdown format.
    documents = collector.get_collection()

    # Entire knowledge base
    entire_knowledge_base = collector.entire_knowledge_base

    print(f"Found {len(documents)} files in the knowledge base")
    return documents


def chunk_legal_documents(chunk_size: int = 1000, chunk_overlap: int = 200) -> list[Document]:
    """Chunk legal documents."""
    documents = fetch_legal_documents()
    return chunk_documents(documents, chunk_size, chunk_overlap)