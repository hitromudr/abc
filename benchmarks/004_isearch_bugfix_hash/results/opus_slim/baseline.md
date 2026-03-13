

```diff
--- a/src/vector_store.py
+++ b/src/vector_store.py
@@ -1,4 +1,5 @@
 import logging
+import hashlib
 from typing import List, Dict, Any
 import numpy as np
 from qdrant_client import QdrantClient, models
@@ -68,7 +69,10 @@
         if not payloads:
             return
 
-        ids = [abs(hash(p.get('source_file', '') + p.get('text', ''))) for p in payloads]
+        def _deterministic_id(p):
+            key = (p.get('source_file', '') + p.get('text', '')).encode('utf-8')
+            return int.from_bytes(hashlib.sha256(key).digest()[:8], 'big', signed=False) >> 1
+        ids = [_deterministic_id(p) for p in payloads]
 
         log.info(f"Upserting {len(payloads)} points to collection '{collection_name}' in batches.")
 
```

SHA-256 от контента → берём первые 8 байт → unsigned → сдвиг вправо на 1 бит гарантирует положительный int64 (< 2^63). Детерминистично между перезапусками.