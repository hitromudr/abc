Это Clear-домен — просто фикс.

**Diff для `src/vector_store.py`:**

```python
--- a/src/vector_store.py
+++ b/src/vector_store.py
@@ -1,4 +1,5 @@
+import hashlib
 import logging
 from typing import List, Dict, Any
 import numpy as np
@@ -67,7 +68,12 @@ class VectorStore:
         if not payloads:
             return
 
-        ids = [abs(hash(p.get('source_file', '') + p.get('text', ''))) for p in payloads]
+        def _deterministic_id(payload: Dict[str, Any]) -> int:
+            key = payload.get('source_file', '') + payload.get('text', '')
+            digest = hashlib.sha256(key.encode('utf-8')).digest()
+            return int.from_bytes(digest[:8], 'big') >> 1 or 1
+
+        ids = [_deterministic_id(p) for p in payloads]
 
         log.info(f"Upserting {len(payloads)} points to collection '{collection_name}' in batches.")
```

**Что делает:**
- `hashlib.sha256` — детерминистичен, не зависит от `PYTHONHASHSEED`
- `digest()[:8]` → 8 байт → `int.from_bytes(..., 'big')` → unsigned 64-bit
- `>> 1` — сдвиг вправо на 1 бит → гарантированно < 2^63 (положительный int64)
- `or 1` — страховка от нулевого ID (вероятность ~0, но контракт требует `> 0`)