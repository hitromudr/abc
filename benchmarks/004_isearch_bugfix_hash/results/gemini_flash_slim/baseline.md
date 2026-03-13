Для исправления бага с недетерминистичными ID необходимо заменить `hash()` на детерминированную хеш-функцию, например, SHA-256. Полученный хеш нужно преобразовать в положительное 64-битное целое число, которое будет стабильно между перезапусками процесса и соответствовать требованию `ID < 2**63` из падающего теста.

Минимальный патч будет внесен в файл `src/vector_store.py`.

```diff
--- a/src/vector_store.py
+++ b/src/vector_store.py
@@ -3,6 +3,7 @@
 from typing import List, Dict, Any
 import numpy as np
 from qdrant_client import QdrantClient, models
+import hashlib
 
 # Import the correct, unified configuration variable
 from src.config import QDRANT_URL
@@ -79,8 +80,18 @@
         """
         if not payloads:
             return
-
-        # Use a deterministic, POSITIVE hash for the ID to prevent re-inserting the same chunk
-        # and comply with Qdrant's unsigned integer ID format.
-        ids = [abs(hash(p.get('source_file', '') + p.get('text', ''))) for p in payloads]
+        
+        ids = []
+        for p in payloads:
+            # Конкатенируем значимые поля для создания уникальной строки,
+            # которая будет использоваться для генерации детерминированного ID.
+            unique_string = p.get('source_file', '') + p.get('text', '')
+            
+            # Используем SHA-256 для детерминированного хеширования.
+            hasher = hashlib.sha256()
+            hasher.update(unique_string.encode('utf-8'))
+            # Берем первые 8 байт (64 бита) хеша.
+            digest_bytes = hasher.digest()[:8]
+            # Преобразуем байты в положительное целое число.
+            # Маскируем значение, чтобы оно было строго меньше 2^63, что удовлетворяет требованию теста на int64.
+            point_id = int.from_bytes(digest_bytes, 'big') & 0x7FFFFFFFFFFFFFFF
+            ids.append(point_id)
 
         log.info(f"Upserting {len(payloads)} points to collection '{collection_name}' in batches.")
 

```