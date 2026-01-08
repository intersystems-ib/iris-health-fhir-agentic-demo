"""
Tool for searching clinical guidelines using IRIS Vector Search (RAG).

This tool queries the IRIS Vector Database to find relevant guideline chunks
based on semantic similarity. Results include chunk IDs and similarity scores
for explainability and traceability.
"""

import os
import re
from crewai.tools import BaseTool
from typing import Type, List, Dict
from pydantic import BaseModel, Field, PrivateAttr
from ..iris_client import IRISClient


class SearchClinicalGuidelinesInput(BaseModel):
    """Input schema for SearchClinicalGuidelines tool."""
    query: str = Field(..., description="Search query for clinical guidelines")
    top_k: int = Field(default=5, description="Number of results to return (1-10)")


class SearchClinicalGuidelinesTool(BaseTool):
    name: str = "Search Clinical Guidelines"
    description: str = """
    Searches clinical practice guidelines stored in IRIS Vector Database.
    Uses semantic search (RAG) to find relevant guideline excerpts based on the query.

    Returns for each result:
    - guideline_id: Logical identifier (e.g., 'ckd_creatinine_demo')
    - chunk_id: Specific chunk identifier for traceability
    - similarity: Vector similarity score (0.0 to 1.0)
    - excerpt: Text excerpt from the guideline

    This enables explainability: every recommendation can be traced back to
    specific guideline text.
    """
    args_schema: Type[BaseModel] = SearchClinicalGuidelinesInput

    # Use PrivateAttr for instance attributes
    _schema: str = PrivateAttr()
    _table: str = PrivateAttr()

    def __init__(self, **kwargs):
        """Initialize vector search configuration."""
        super().__init__(**kwargs)
        # Table and schema configuration
        self._schema = os.getenv("IRIS_SCHEMA", "clinicalai_data")
        self._table = os.getenv("IRIS_GUIDELINES_TABLE", "GuidelineChunks")

    def _run(self, query: str, top_k: int = 5) -> str:
        """
        Execute the tool.

        Args:
            query: Search query
            top_k: Number of results (limited to 1-10)

        Returns:
            Formatted guideline excerpts with chunk IDs and similarity scores
        """
        # Validate and constrain top_k
        top_k = max(1, min(top_k, 10))

        results = self._search_guidelines(query, top_k)

        if not results:
            return "No relevant clinical guidelines found for this query."

        # Format output for agent consumption
        output = f"Clinical Guidelines Search Results (Top {len(results)}):\n\n"

        for i, result in enumerate(results, 1):
            guideline_id = result.get("guideline_id", "Unknown")
            chunk_id = result.get("chunk_id", "Unknown")
            text = result.get("chunk_text", "")
            score = result.get("similarity", 0.0)

            output += f"[{i}] Guideline: {guideline_id}\n"
            output += f"    Chunk ID: {chunk_id}\n"
            output += f"    Similarity: {score:.4f}\n"
            output += f"    Excerpt: {text[:500]}...\n\n"

        output += "\n**Important:** Include these chunk_id values in your output "
        output += "so recommendations can be traced back to specific guidelines.\n"

        return output

    def _search_guidelines(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search clinical guidelines using IRIS Vector Search.

        This method uses IRIS SQL functions for vector search:
        - VECTOR_DOT_PRODUCT() for similarity
        - Assumes embeddings are pre-computed and stored

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of guideline chunks with similarity scores
        """
        # Sanitize inputs
        query = query.strip()
        top_k = max(1, min(top_k, 50))

        # Get embedding model from environment
        embedding_model = os.getenv("EMBEDDING_MODEL", "my-openai-config")

        with IRISClient() as iris:
            try:
                # Use IRIS Vector Search with VECTOR_DOT_PRODUCT for semantic similarity
                # This requires:
                # 1. GuidelineChunks table with Embedding column (VECTOR type)
                # 2. IRIS configured with OpenAI embedding model
                # 3. Pre-computed embeddings in the Embedding column

                sql = f"""
                    SELECT TOP {top_k}
                        ChunkId,
                        GuidelineId,
                        ChunkText,
                        VECTOR_DOT_PRODUCT(Embedding, EMBEDDING(?, ?)) as similarity
                    FROM {self._schema}.{self._table}
                    WHERE Embedding IS NOT NULL
                    ORDER BY similarity DESC
                """

                # Log SQL query for debugging
                print(f"[IRIS Vector Search] Executing SQL:")
                print(f"  Query: {sql}")
                print(f"  Parameters: query='{query}', embedding_model='{embedding_model}'")

                # Execute query with search query and embedding model name
                results = iris.query(sql, [query, embedding_model])
                print(f"[IRIS Vector Search] Found {len(results)} results")

                # Format results
                formatted_results = []
                for row in results:
                    formatted_results.append({
                        "chunk_id": row.get("ChunkId", ""),
                        "guideline_id": row.get("GuidelineId", "unknown"),
                        "chunk_text": row.get("ChunkText", ""),
                        "similarity": float(row.get("similarity", 0.0))
                    })

                return formatted_results

            except Exception as e:
                print(f"[IRIS Vector] Error searching guidelines: {e}")
                return []
