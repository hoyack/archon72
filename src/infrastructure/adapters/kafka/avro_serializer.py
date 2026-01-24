"""Avro serialization with Schema Registry integration.

Story 2.3: Implement Avro Serializer
ADR-001: Avro + Schema Registry for type-safe serialization
NFR-AVV-9 (R2): Schema Registry health required for publish

This module provides Avro serialization for Kafka messages with automatic
schema registration and validation against the Schema Registry.
"""

import json
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import fastavro
from fastavro.schema import load_schema

logger = logging.getLogger(__name__)

# Schema paths relative to project root
SCHEMA_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas" / "conclave" / "votes"


class SchemaRegistryError(Exception):
    """Error communicating with Schema Registry."""

    pass


class SchemaRegistryUnavailableError(SchemaRegistryError):
    """Schema Registry is not reachable (R2 violation)."""

    pass


class SerializationError(Exception):
    """Error serializing/deserializing Avro message."""

    pass


@dataclass
class SchemaInfo:
    """Cached schema information."""

    schema: dict[str, Any]
    parsed_schema: Any  # fastavro parsed schema
    schema_id: int | None = None  # ID from Schema Registry


class AvroSerializer:
    """Avro serializer with Schema Registry integration.

    Provides:
    - Local schema loading from .avsc files
    - Schema Registry registration (when available)
    - Serialization/deserialization with schema validation
    - Schema caching for performance

    Per R2: If Schema Registry is required but unavailable, raises
    SchemaRegistryUnavailableError to trigger sync fallback.
    """

    def __init__(
        self,
        schema_registry_url: str | None = None,
        require_registry: bool = False,
    ) -> None:
        """Initialize the serializer.

        Args:
            schema_registry_url: URL of Schema Registry (e.g., http://localhost:18081)
            require_registry: If True, raises error when registry unavailable (R2)
        """
        self._registry_url = schema_registry_url
        self._require_registry = require_registry
        self._schema_cache: dict[str, SchemaInfo] = {}
        self._registry_available: bool | None = None

        # Load all schemas at initialization
        self._load_local_schemas()

    def _load_local_schemas(self) -> None:
        """Load all Avro schemas from the schemas directory."""
        if not SCHEMA_DIR.exists():
            logger.warning("Schema directory not found: %s", SCHEMA_DIR)
            return

        for schema_file in SCHEMA_DIR.glob("*.avsc"):
            schema_name = schema_file.stem
            try:
                with open(schema_file) as f:
                    schema = json.load(f)

                # Parse schema for fastavro
                parsed = fastavro.parse_schema(schema)

                self._schema_cache[schema_name] = SchemaInfo(
                    schema=schema,
                    parsed_schema=parsed,
                )
                logger.debug("Loaded schema: %s", schema_name)

            except Exception as e:
                logger.error("Failed to load schema %s: %s", schema_file, e)

        logger.info("Loaded %d Avro schemas", len(self._schema_cache))

    def _check_registry_health(self) -> bool:
        """Check if Schema Registry is reachable.

        Returns:
            True if registry is healthy, False otherwise
        """
        if not self._registry_url:
            return False

        try:
            import httpx

            response = httpx.get(
                f"{self._registry_url}/subjects",
                timeout=5.0,
            )
            self._registry_available = response.status_code == 200
            return self._registry_available

        except Exception as e:
            logger.warning("Schema Registry health check failed: %s", e)
            self._registry_available = False
            return False

    def _ensure_registry_available(self) -> None:
        """Ensure Schema Registry is available if required.

        Raises:
            SchemaRegistryUnavailableError: If registry required but unavailable
        """
        if not self._require_registry:
            return

        if self._registry_available is None:
            self._check_registry_health()

        if not self._registry_available:
            raise SchemaRegistryUnavailableError(
                f"Schema Registry at {self._registry_url} is not available. "
                "Cannot publish votes - falling back to sync validation."
            )

    def serialize(
        self,
        schema_name: str,
        data: dict[str, Any],
    ) -> bytes:
        """Serialize data to Avro binary format.

        Args:
            schema_name: Name of the schema (e.g., 'pending_validation')
            data: Data to serialize

        Returns:
            Avro-encoded bytes

        Raises:
            SerializationError: If serialization fails
            SchemaRegistryUnavailableError: If registry required but unavailable
        """
        self._ensure_registry_available()

        schema_info = self._schema_cache.get(schema_name)
        if not schema_info:
            raise SerializationError(f"Unknown schema: {schema_name}")

        try:
            buffer = BytesIO()
            fastavro.schemaless_writer(buffer, schema_info.parsed_schema, data)
            return buffer.getvalue()

        except Exception as e:
            raise SerializationError(
                f"Failed to serialize with schema {schema_name}: {e}"
            ) from e

    def deserialize(
        self,
        schema_name: str,
        data: bytes,
    ) -> dict[str, Any]:
        """Deserialize Avro binary data.

        Args:
            schema_name: Name of the schema to use
            data: Avro-encoded bytes

        Returns:
            Deserialized data dictionary

        Raises:
            SerializationError: If deserialization fails
        """
        schema_info = self._schema_cache.get(schema_name)
        if not schema_info:
            raise SerializationError(f"Unknown schema: {schema_name}")

        try:
            buffer = BytesIO(data)
            return fastavro.schemaless_reader(buffer, schema_info.parsed_schema)

        except Exception as e:
            raise SerializationError(
                f"Failed to deserialize with schema {schema_name}: {e}"
            ) from e

    def get_schema(self, schema_name: str) -> dict[str, Any] | None:
        """Get a schema by name.

        Args:
            schema_name: Name of the schema

        Returns:
            Schema dictionary or None if not found
        """
        schema_info = self._schema_cache.get(schema_name)
        return schema_info.schema if schema_info else None

    def list_schemas(self) -> list[str]:
        """List all loaded schema names.

        Returns:
            List of schema names
        """
        return list(self._schema_cache.keys())

    @property
    def registry_available(self) -> bool:
        """Check if Schema Registry is currently available."""
        if self._registry_available is None:
            self._check_registry_health()
        return self._registry_available or False
