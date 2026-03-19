"""Phase 2 — Embedder: populates ChromaDB microsoft_docs collection.
Uses ChromaDB's built-in sentence-transformer embeddings.
"""
import os
import sys
import json

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from knowledge.scraper import get_chunks
from knowledge.issue_catalog import get_chromadb_chunks


def embed_knowledge(chromadb_path='./chroma_db'):
    """Embed all knowledge chunks + 500 issue catalog into ChromaDB microsoft_docs collection."""
    if not CHROMA_AVAILABLE:
        print('ERROR: chromadb not installed. Run: pip install chromadb', file=sys.stderr)
        return 0

    doc_chunks = get_chunks()
    issue_chunks = get_chromadb_chunks()
    chunks = doc_chunks + issue_chunks
    print(f'Embedding {len(doc_chunks)} doc chunks + {len(issue_chunks)} issue chunks = {len(chunks)} total')
    client = chromadb.PersistentClient(path=chromadb_path)

    # Delete existing collection if it exists, then recreate
    try:
        client.delete_collection('microsoft_docs')
    except Exception:
        pass

    collection = client.create_collection(
        name='microsoft_docs',
        metadata={'description': 'Microsoft Fabric Data Agent documentation chunks'},
    )

    # Batch add all chunks
    ids = [c['id'] for c in chunks]
    documents = [f"{c['title']}\n\n{c['content']}" for c in chunks]
    metadatas = [{'title': c['title'], 'topic': c['topic']} for c in chunks]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    # Also create past_findings collection (empty)
    try:
        client.delete_collection('past_findings')
    except Exception:
        pass
    client.create_collection(
        name='past_findings',
        metadata={'description': 'Past analysis findings for cross-session patterns'},
    )

    count = collection.count()
    print(f'Embedded {count} chunks into microsoft_docs collection')
    print(f'ChromaDB path: {chromadb_path}')

    # Verification query
    results = collection.query(
        query_texts=['fabric data agent instruction limit'],
        n_results=3,
    )
    print(f'Verification query returned {len(results["documents"][0])} results')

    return count


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else './chroma_db'
    count = embed_knowledge(path)
    print(f'Total chunks embedded: {count}')
