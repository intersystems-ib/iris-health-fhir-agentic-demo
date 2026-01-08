"""
Minimal wrapper around InterSystems IRIS DB-API connection.

This module provides a simple interface to IRIS SQL operations.
FHIR-specific logic is implemented in individual tools.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, List, Dict, Optional

# InterSystems IRIS Python DB-API (PEP 249)
# Docs: https://docs.intersystems.com/iris20252/csp/docbook/DocBook.UI.Page.cls?KEY=BPYNAT_pyapi
import iris


# Get connection settings from environment
_HOST: str = os.getenv("IRIS_HOST", "localhost")
_PORT: int = int(os.getenv("IRIS_PORT", "1972"))
_NAMESPACE: str = os.getenv("IRIS_NAMESPACE", "INTEROP")
_USERNAME: str = os.getenv("IRIS_USERNAME", "_SYSTEM")
_PASSWORD: str = os.getenv("IRIS_PASSWORD", "SYS")


class IRISClient:
    """
    Minimal wrapper around InterSystems IRIS DB-API connection.

    - Uses iris.connect(host, port, namespace, username, password)
    - Autocommit is enabled
    - Param placeholders are '?', e.g.: "SELECT * FROM T WHERE id = ?"
    """

    def __init__(
        self,
        host: str = _HOST,
        port: int = _PORT,
        namespace: str = _NAMESPACE,
        username: str = _USERNAME,
        password: str = _PASSWORD,
        autocommit: bool = True,
    ) -> None:
        """Initialize connection to IRIS."""
        self._conn = iris.connect(host, port, namespace, username, password)
        self._conn.autocommit = autocommit

    def __enter__(self) -> "IRISClient":
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Context manager cleanup."""
        self.close()

    def query(self, sql: str, params: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
        """
        Run a SELECT and return rows as a list of dicts.
        Use '?' placeholders in SQL and pass params as a sequence.

        Example:
            results = client.query("SELECT * FROM table WHERE id = ?", [123])
        """
        cur = self._conn.cursor()
        try:
            cur.execute(sql, tuple(params or ()))
            cols = [c[0] for c in (cur.description or [])]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            cur.close()

    def query_one(self, sql: str, params: Optional[Iterable[Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Run a SELECT and return a single row as dict (or None).

        Example:
            row = client.query_one("SELECT * FROM table WHERE id = ?", [123])
        """
        cur = self._conn.cursor()
        try:
            cur.execute(sql, tuple(params or ()))
            cols = [c[0] for c in (cur.description or [])]
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None
        finally:
            cur.close()

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> int:
        """
        Run INSERT/UPDATE/DELETE. Returns rowcount.

        Example:
            rows_affected = client.execute("INSERT INTO table (col) VALUES (?)", ["test"])
        """
        cur = self._conn.cursor()
        try:
            cur.execute(sql, tuple(params or ()))
            return cur.rowcount if cur.rowcount is not None else 0
        finally:
            cur.close()

    def close(self) -> None:
        """Close database connection."""
        try:
            self._conn.close()
        except Exception:
            pass
