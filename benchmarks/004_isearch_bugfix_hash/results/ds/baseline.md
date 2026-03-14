Я вижу проблему. В методе `upsert` класса `VectorStore` используется `abs(hash(...))` для генерации ID точек, что недетерминировано из-за рандомизации хеша в Python. Нужно заменить это на детерминистичную хеш-функцию.

Вот исправленный файл `src/vector_store.py`:

```python
import logging
import hashlib
from typing import Any, Dict, List

import numpy as np
from qdrant_client import QdrantClient, models

# Import the correct, unified configuration variable
from src.config import QDRANT_URL

log = logging.getLogger(__name__)


class VectorStore:
    """
    A wrapper class for the Qdrant client to abstract away the details of
    collection management and vector operations, optimized for float16.
    """

    def __init__(self):
        """
        Initializes the Qdrant client using the URL from the configuration.
        """
        log.info(f"Initializing Qdrant client with target: {QDRANT_URL}")
        try:
            if QDRANT_URL.startswith("http://") or QDRANT_URL.startswith("https://"):
                self.client = QdrantClient(
                    url=QDRANT_URL,
                    timeout=60.0,  # 60 second timeout for operations
                    prefer_grpc=False,  # Use HTTP for better timeout handling
                )
            else:
                self.client = QdrantClient(path=QDRANT_URL)
            # A simple health check to ensure the connection is valid
            self.client.get_collections()
            log.info("Successfully connected to Qdrant.")
        except Exception as e:
            log.critical(
                f"Failed to connect to Qdrant at {QDRANT_URL}. This is a fatal error. Exception: {e}",
                exc_info=True,
            )
            # Re-raise the exception to prevent the service from starting in a broken state
            raise

    def get_collection_info(self, collection_name: str) -> models.CollectionInfo:
        """Retrieves information about a specific collection."""
        return self.client.get_collection(collection_name=collection_name)

    def recreate_collection(self, collection_name: str, vector_size: int):
        """
        Creates a new collection configured for FLOAT16 vectors, deleting it
        first if it already exists.
        """
        log.warning(
            f"Recreating collection '{collection_name}' with vector size {vector_size} and FLOAT16 data type."
        )
        # `recreate_collection` is deprecated. The new way is to explicitly check, delete, and create.
        if self.client.collection_exists(collection_name=collection_name):
            self.client.delete_collection(collection_name=collection_name)

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
                datatype=models.Datatype.FLOAT16,  # Key change: Use 16-bit floats
            ),
        )

        # Create a payload index on `source_file` for efficient filtering and deletion
        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="source_file",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        # Create a payload index on `file_type` for efficient filtering
        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="file_type",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    def delete_collection(self, collection_name: str) -> bool:
        """
        Deletes a collection if it exists.
        Returns True if the collection was deleted, False otherwise.
        """
        if not self.client.collection_exists(collection_name=collection_name):
            log.warning(
                f"Attempted to delete non-existent collection '{collection_name}'."
            )
            return False

        log.info(f"Deleting collection '{collection_name}'.")
        self.client.delete_collection(collection_name=collection_name)
        return True

    def _generate_deterministic_id(self, source_file: str, text: str) -> int:
        """
        Generates a deterministic positive int64 ID from source_file and text.
        Uses SHA-256 hash and takes the first 8 bytes (64 bits) as integer.
        Ensures the ID is positive by masking with 0x7FFFFFFFFFFFFFFF.
        """
        # Create a unique string from source_file and text
        unique_string = f"{source_file}:{text}"
        
        # Generate SHA-256 hash
        hash_bytes = hashlib.sha256(unique_string.encode('utf-8')).digest()
        
        # Take first 8 bytes (64 bits) and convert to integer
        # Use bitwise AND with 0x7FFFFFFFFFFFFFFF to ensure positive (max int64 positive value)
        id_value = int.from_bytes(hash_bytes[:8], byteorder='big', signed=False)
        
        # Ensure positive by clearing the sign bit (bit 63)
        positive_id = id_value & 0x7FFFFFFFFFFFFFFF
        
        # Also ensure it's not zero (unlikely but possible)
        if positive_id == 0:
            positive_id = 1
            
        return positive_id

    def upsert(
        self, collection_name: str, vectors: np.ndarray, payloads: List[Dict[str, Any]]
    ):
        """
        Upserts (inserts or updates) a batch of vectors and their payloads.
        Uses a deterministic, POSITIVE hash of content for the point ID.
        """
        if not payloads:
            return

        # Use a deterministic, POSITIVE hash for the ID to prevent re-inserting the same chunk
        # and comply with Qdrant's unsigned integer ID format.
        ids = [
            self._generate_deterministic_id(
                p.get("source_file", ""), 
                p.get("text", "")
            ) 
            for p in payloads
        ]

        log.info(
            f"Upserting {len(payloads)} points to collection '{collection_name}' in batches."
        )

        # Process in smaller batches to avoid Qdrant timeouts
        batch_size = 500  # Safe batch size for Qdrant
        total_batches = (len(payloads) + batch_size - 1) // batch_size

        for i in range(0, len(payloads), batch_size):
            end_idx = min(i + batch_size, len(payloads))
            batch_ids = ids[i:end_idx]
            batch_vectors = vectors[i:end_idx]
            batch_payloads = payloads[i:end_idx]

            log.info(
                f"Upserting batch {i // batch_size + 1}/{total_batches} ({len(batch_payloads)} points)"
            )

            self.client.upsert(
                collection_name=collection_name,
                points=models.Batch(
                    ids=batch_ids,
                    vectors=batch_vectors.tolist(),  # .tolist() correctly handles float16
                    payloads=batch_payloads,
                ),
                wait=True,
            )

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        query_filter: models.Filter | None = None,
        limit: int = 10,
    ) -> List[models.ScoredPoint]:
        """
        Performs a vector search in a collection.
        """
        log_msg = f"Performing search in '{collection_name}' with limit={limit}."
        if query_filter:
            log_msg += f" Using filter: {query_filter}"
        log.info(log_msg)
        # The `search` method is deprecated. Using `query_points` instead.
        response = self.client.query_points(
            collection_name=collection_name,
            query=query_vector.tolist(),
            query_filter=query_filter,
            limit=limit,
        )
        return response.points

    def get_documents_by_source(
        self, collection_name: str, source_files: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        Retrieves all document payloads from a given list of source files,
        indexed by source_file.
        """
        if not source_files:
            return {}

        log.info(
            f"Fetching existing document metadata for {len(source_files)} files from '{collection_name}'."
        )

        all_docs = {}
        next_page_offset = None

        # Use scroll to iterate over all matching points
        while True:
            records, next_page_offset = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    should=[
                        models.FieldCondition(
                            key="source_file", match=models.MatchValue(value=file)
                        )
                        for file in source_files
                    ]
                ),
                limit=250,
                with_payload=True,
                with_vectors=False,  # We only need metadata
                offset=next_page_offset,
            )

            for record in records:
                source_file = record.payload.get("source_file")
                if source_file:
                    if source_file not in all_docs:
                        all_docs[source_file] = []
                    all_docs[source_file].append(record.payload)

            if next_page_offset is None:
                break

        log.info(
            f"Found {sum(len(v) for v in all_docs.values())} existing records across {len(all_docs)} files."
        )
        return all_docs

    def delete_points_by_source(self, collection_name: str, source_files: List[str]):
        """
        Deletes all points associated with a list of source files.
        """
        if not source_files:
            return

        log.warning(
            f"Deleting all points from {len(source_files)} source files in '{collection_name}'."
        )
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    should=[
                        models.FieldCondition(
                            key="source_file", match=models.MatchValue(value=file)
                        )
                        for file in source_files
                    ]
                )
            ),
            wait=True,
        )
```

**Ключевые изменения:**

1. **Добавлен метод `_generate_deterministic_id`**:
   - Использует SHA-256 для детерминированного хеширования
   - Берёт первые 8 байт (64 бита) хеша
   - Гарантирует положительное значение через маску `0x7FFFFFFFFFFFFFFF`
   - Обрабатывает крайний случай нулевого ID

2. **Обновлён метод `upsert`**:
   - Заменён `abs(hash(...))` на вызов `_generate_deterministic_id`
   - Сохраняет ту же логику генерации ID из `source_file` и `text`

**Преимущества решения:**
- ✅ Детерминировано между запусками процесса
- ✅ Гарантирует положительные int64 ID (совместимость с Qdrant)
- ✅ Минимальное изменение кода
- ✅ Не затрагивает другие методы класса
- ✅ Использует криптографически стойкий хеш

Тест `test_id_determinism_across_seeds` должен проходить успешно, так как ID теперь будут одинаковыми для одинаковых входных данных независимо от PYTHONHASHSEED.