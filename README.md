# QuadStore

A simple, lightweight, highly-indexed in-memory quadstore (knowledge graph database) implemented entirely in Python.

It stores data as quadruples in the format `(subject, predicate, object, context)` and utilizes integer ID mapping internally to drastically reduce memory footprint. This makes it ideal for managing large-scale knowledge graphs without the overhead of external database dependencies.

## Features

- **4-Way SPOC Indexing**: Internally indexes quads across four distinct dictionary variants (`spoc`, `pocs`, `ocsp`, `cspo`) allowing for instantaneous $O(1)$ querying along any combination of dimensions.
- **Memory Optimized**: Maps raw strings to unique integer IDs upon insertion. This prevents string duplication across the heavily nested indices, avoiding memory exhaustion on large datasets.
- **Streaming I/O**: Serializes database state to and from disk using `.jsonl` (JSON Lines). This allows datasets containing millions of quads to be iteratively loaded and saved without hitting `MemoryError` limitations.
- **LRU Caching**: Wraps retrieval logic in a smart LRU cache that automatically purges stale data whenever graph mutations occur.

## Basic Usage

The store is self-contained. Simply drop `quadstore.py` into your project and import the class.

```python
from quadstore import QuadStore

# Initialize
qs = QuadStore()

# Add Quads of the format (subject, predicate, object, context)
qs.add("LeBron James", "scored", "27.4", "2019")
qs.add("Kevin Durant", "scored", "26.0", "2019")

# Add multiple at once
qs.batch_add([
    ("LeBron James", "scored", "25.3", "2020"),
    ("Stephen Curry", "scored", "32.0", "2020")
])

# Querying, empty fields act as wildcards
results_by_subject = qs.query(subject="LeBron James")
results_by_context = qs.query(context="2020")
complex_query = qs.query(predicate="scored", context="2019")

print(complex_query)
# [('LeBron James', 'scored', '27.4', '2019'), ('Kevin Durant', 'scored', '26.0', '2019')]

# Serialization
qs.save_to_file("my_graph.jsonl")

# Loading
loaded_qs = QuadStore.load_from_file("my_graph.jsonl")
```

## Running Tests

If you are modifying the store, you can run the included unit tests `test_quadstore.py` to ensure indexing integrity and memory mapping stability.

```bash
python -m unittest test_quadstore.py
```
