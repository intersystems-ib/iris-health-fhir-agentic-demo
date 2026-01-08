"""
Ingests clinical guidelines into IRIS Vector Database.

This script:
1. Reads clinical guideline documents from the guidelines/ directory
2. Chunks them appropriately for RAG
3. Generates embeddings using OpenAI
4. Stores them in IRIS Vector Search

Usage:
    python iris/vector/ingest_guidelines.py
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dotenv import load_dotenv

# Add clinical_ai to path to import iris_client
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "clinical_ai"))
from iris_client import IRISClient


# ==============================================================================
# Configuration
# ==============================================================================

CHUNK_SIZE = int(os.getenv("GUIDELINE_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("GUIDELINE_CHUNK_OVERLAP", "150"))
MAX_DOC_LENGTH = int(os.getenv("GUIDELINE_MAX_DOC_LENGTH", "50000"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "my-openai-config")


# ==============================================================================
# Document Loading
# ==============================================================================

def _read_guidelines_from_fs(guidelines_dir: Path) -> List[Dict[str, str]]:
    """
    Read guideline documents from the filesystem.

    Returns:
        List of dicts with keys: guideline_id, title, content
    """
    guidelines = []

    # Support .txt, .md, and .markdown files
    patterns = ["*.txt", "*.md", "*.markdown"]
    files = []
    for pattern in patterns:
        files.extend(guidelines_dir.glob(pattern))

    if not files:
        return []

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Use filename (without extension) as guideline_id
            guideline_id = filepath.stem

            # Try to extract title from first markdown header or use filename
            title = guideline_id
            lines = content.split("\n")
            for line in lines:
                if line.startswith("# "):
                    title = line.lstrip("# ").strip()
                    break

            # Truncate content if too long
            if len(content) > MAX_DOC_LENGTH:
                content = content[:MAX_DOC_LENGTH]
                print(f"  ⚠️  Truncated '{filepath.name}' to {MAX_DOC_LENGTH} chars")

            guidelines.append({
                "guideline_id": guideline_id,
                "title": title,
                "content": content
            })

            print(f"  ✓ Loaded: {filepath.name} ({len(content)} chars)")

        except Exception as e:
            print(f"  ✗ Error reading {filepath.name}: {e}")

    return guidelines


# ==============================================================================
# Chunking
# ==============================================================================

def make_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Tuple[int, int, str]]:
    """
    Split text into overlapping chunks.

    Args:
        text: The text to chunk
        chunk_size: Target size of each chunk in characters
        overlap: Number of characters to overlap between chunks

    Returns:
        List of tuples: (start_pos, end_pos, chunk_text)
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk_text = text[start:end]
        chunks.append((start, end, chunk_text))

        if end >= text_len:
            break

        start = end - overlap

    return chunks


# ==============================================================================
# Database Operations
# ==============================================================================

def upsert_guideline_chunks(
    client: IRISClient,
    guideline_id: str,
    chunks: List[Tuple[int, int, str]]
) -> int:
    """
    Insert or update guideline chunks in the database.

    Uses ChunkId as natural key (GuidelineId:ChunkIndex).
    Embeddings are generated separately using IRIS EMBEDDING() function.

    Args:
        client: IRIS database client
        guideline_id: Identifier for the guideline document
        chunks: List of (start_pos, end_pos, chunk_text) tuples

    Returns:
        Number of chunks upserted
    """
    count = 0

    for idx, (_, _, chunk_text) in enumerate(chunks):
        chunk_id = f"{guideline_id}:chunk-{idx}"

        # Try to insert first
        try:
            client.execute(
                """
                INSERT INTO clinicalai_data.GuidelineChunks
                (ChunkId, GuidelineId, ChunkText)
                VALUES (?, ?, ?)
                """,
                [chunk_id, guideline_id, chunk_text]
            )
            count += 1
        except Exception:
            # If insert fails (duplicate key), update instead
            try:
                client.execute(
                    """
                    UPDATE clinicalai_data.GuidelineChunks
                    SET ChunkText = ?, CreatedAt = CURRENT_TIMESTAMP
                    WHERE ChunkId = ?
                    """,
                    [chunk_text, chunk_id]
                )
                count += 1
            except Exception as e:
                print(f"    ✗ Error upserting chunk {chunk_id}: {e}")

    return count


def rebuild_guideline_vectors(client: IRISClient, embedding_model: str) -> int:
    """
    Rebuild vector embeddings for all guideline chunks using IRIS EMBEDDING() function.

    This uses IRIS's built-in EMBEDDING() SQL function to generate embeddings
    from the ChunkText column using the specified OpenAI model.

    Args:
        client: IRIS database client
        embedding_model: OpenAI embedding model name (e.g., 'text-embedding-3-small')

    Returns:
        Number of chunks updated
    """
    # First, check how many chunks we have
    result = client.query_one("SELECT COUNT(*) as cnt FROM clinicalai_data.GuidelineChunks")
    total = result["cnt"] if result else 0

    if total == 0:
        return 0

    print(f"  Generating embeddings for {total} chunks using IRIS EMBEDDING() function...")
    print(f"  Model: {embedding_model}")

    try:
        # Use IRIS EMBEDDING() function to generate embeddings from ChunkText
        # The EMBEDDING() function calls OpenAI API internally
        client.execute(
            f"""
            UPDATE clinicalai_data.GuidelineChunks
            SET Embedding = EMBEDDING(ChunkText, ?)
            WHERE Embedding IS NULL
            """,
            [embedding_model]
        )

        # Count how many chunks now have embeddings
        result = client.query_one(
            "SELECT COUNT(*) as cnt FROM clinicalai_data.GuidelineChunks WHERE Embedding IS NOT NULL"
        )
        embedded_count = result["cnt"] if result else 0

        print(f"  ✓ Successfully generated embeddings for {embedded_count} chunks")
        return embedded_count

    except Exception as e:
        print(f"  ✗ Error generating embeddings: {e}")
        print(f"\n  Note: Make sure IRIS is configured with OpenAI API credentials.")
        print(f"  You may need to configure the EMBEDDING model in IRIS settings.")
        return 0


# ==============================================================================
# Main
# ==============================================================================

def main():
    load_dotenv()

    print("📚 Clinical Guidelines Ingestion")
    print("=" * 70)

    # Configuration
    guidelines_dir = Path(__file__).parent / "guidelines"

    print(f"\n📁 Guidelines Directory: {guidelines_dir}")
    print(f"🔧 Chunk Size: {CHUNK_SIZE} chars")
    print(f"🔧 Chunk Overlap: {CHUNK_OVERLAP} chars")
    print(f"🔧 Embedding Model: {EMBEDDING_MODEL}")

    # Check directory exists
    if not guidelines_dir.exists():
        print(f"\n⚠️  Directory not found: {guidelines_dir}")
        print("Creating directory...")
        guidelines_dir.mkdir(parents=True, exist_ok=True)

    # Load guidelines
    print(f"\n📖 Loading guideline documents...")
    guidelines = _read_guidelines_from_fs(guidelines_dir)

    if not guidelines:
        print("\n⚠️  No guideline files found in iris/vector/guidelines/")
        print("\nSupported formats: .txt, .md, .markdown")
        print("\nTo use RAG functionality:")
        print("1. Add clinical guideline documents to iris/vector/guidelines/")
        print("2. Run this script to ingest them into IRIS Vector DB")
        print("\nExample guidelines to add:")
        print("  - KDIGO Clinical Practice Guideline for AKI")
        print("  - AHA/ACC Clinical Practice Guidelines")
        print("  - Other evidence-based clinical guidelines")
        return

    print(f"\n✓ Loaded {len(guidelines)} guideline(s)")

    # Process each guideline
    print(f"\n🔪 Chunking guidelines...")
    all_chunks = []

    for guideline in guidelines:
        chunks = make_chunks(guideline["content"], CHUNK_SIZE, CHUNK_OVERLAP)
        all_chunks.append((guideline["guideline_id"], chunks))
        print(f"  ✓ {guideline['guideline_id']}: {len(chunks)} chunks")

    # Connect to IRIS
    print(f"\n🔌 Connecting to IRIS...")
    try:
        with IRISClient() as client:
            print(f"  ✓ Connected to IRIS at {os.getenv('IRIS_HOST')}:{os.getenv('IRIS_PORT')}")

            # Upsert chunks (without embeddings initially)
            print(f"\n💾 Upserting chunks to database...")
            total_upserted = 0

            for guideline_id, chunks in all_chunks:
                count = upsert_guideline_chunks(client, guideline_id, chunks)
                print(f"  ✓ {guideline_id}: {count} chunks upserted")
                total_upserted += count

            # Generate embeddings using IRIS EMBEDDING() function
            print(f"\n🧮 Generating embeddings using IRIS EMBEDDING() function...")
            embedded_count = rebuild_guideline_vectors(client, EMBEDDING_MODEL)

            # Verify
            print(f"\n✅ Verification")
            result = client.query_one("SELECT COUNT(*) as cnt FROM clinicalai_data.GuidelineChunks")
            total_in_db = result["cnt"] if result else 0
            print(f"  Total chunks in database: {total_in_db}")

            result_embedded = client.query_one(
                "SELECT COUNT(*) as cnt FROM clinicalai_data.GuidelineChunks WHERE Embedding IS NOT NULL"
            )
            total_embedded = result_embedded["cnt"] if result_embedded else 0
            print(f"  Chunks with embeddings: {total_embedded}")

            print(f"\n✅ Ingestion complete!")
            print(f"  {len(guidelines)} guideline(s) processed")
            print(f"  {total_upserted} chunks stored")
            print(f"  {total_embedded} embeddings generated")

    except Exception as e:
        print(f"\n❌ Error connecting to IRIS: {e}")
        print("\nMake sure:")
        print("  - IRIS is running")
        print("  - Connection settings in .env are correct")
        print("  - Schema has been initialized (iris/init/schema.sql)")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
