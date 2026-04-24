# Divide into chunks using the RecursiveCharacterTextSplitter
# But first convert the documents to a list of langchain documents.
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def convert_to_langchain_documents(documents: dict) -> list[Document]:
    """Convert the documents to a list of langchain documents."""
    return [
        Document(page_content=content, metadata={"file_name": filename})
        for filename, content in documents.items()
    ]

def split_documents(langchain_documents: list[Document], chunk_size: int, chunk_overlap: int) -> list[Document]:
    """Split the documents into chunks."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = text_splitter.split_documents(langchain_documents)
    return chunks

def chunk_documents(documents: dict, chunk_size: int, chunk_overlap: int) -> list[Document]:
    """Chunk the documents into chunks."""
    langchain_documents = convert_to_langchain_documents(documents)
    chunks = split_documents(langchain_documents, chunk_size, chunk_overlap)
    print(f"Divided into {len(chunks)} chunks")
    print(f"First chunk:\n\n{chunks[0]}")
    return chunks