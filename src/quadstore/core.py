"""
This module provides a simple in-memory quadstore (a type of knowledge graph database).
It stores quadruples in the format (subject, predicate, object, context) and maps
strings to integer IDs internally to dramatically reduce memory footprint. It allows
for efficient cross-indexing and complex querying along any combination of the four dimensions.

Typical use cases include knowledge graphs and retrieval-augmented generation (RAG) pipelines.
"""

import json
import os
from collections import defaultdict
from functools import lru_cache


class QuadStore:
    """
    An in-memory, highly-indexed storage engine for quadruples (SPOC).
    Utilizes integer ID mapping to prevent string duplication and out-of-memory errors.
    """
    def __init__(self):
        """Initializes an empty QuadStore object with four-way SPOC index mappings."""
        self.quads = set()
        self._str_to_id = {}
        self._id_to_str = {}
        self._next_id = 0
        
        self.indices = {
            'spoc': defaultdict(lambda: defaultdict(lambda: defaultdict(set))),
            'pocs': defaultdict(lambda: defaultdict(lambda: defaultdict(set))),
            'ocsp': defaultdict(lambda: defaultdict(lambda: defaultdict(set))),
            'cspo': defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        }

    def _get_id(self, string_val):
        """Helper to convert a string to its integer ID, cataloguing it if new."""
        if string_val not in self._str_to_id:
            self._str_to_id[string_val] = self._next_id
            self._id_to_str[self._next_id] = string_val
            self._next_id += 1
        return self._str_to_id[string_val]

    def _get_str(self, id_val):
        """Helper to retrieve original string by its integer ID."""
        return self._id_to_str[id_val]

    def _to_str_quad(self, quad_id):
        """Converts a quad tuple of integer IDs back to a quad of strings."""
        return (self._get_str(quad_id[0]), self._get_str(quad_id[1]), 
                self._get_str(quad_id[2]), self._get_str(quad_id[3]))

    def add(self, subject, predicate, object, context):
        """
        Inserts a new quad into the store and updates all SPOC indices.
        Automatically invalidates the query cache.
        """
        s_id = self._get_id(subject)
        p_id = self._get_id(predicate)
        o_id = self._get_id(object)
        c_id = self._get_id(context)
        quad_id = (s_id, p_id, o_id, c_id)
        if quad_id not in self.quads:
            self.quads.add(quad_id)
            self._add_to_indices(quad_id)
            if hasattr(self.query, 'cache_clear'):
                self.query.cache_clear()

    def _add_to_indices(self, quad_id):
        """Internal helper to add a quad ID to the four-way lookup dictionaries."""
        s, p, o, c = quad_id
        self.indices['spoc'][s][p][o].add(c)
        self.indices['pocs'][p][o][c].add(s)
        self.indices['ocsp'][o][c][s].add(p)
        self.indices['cspo'][c][s][p].add(o)

    def remove(self, subject, predicate, object, context):
        """
        Removes an existing quad from the store and its indices.
        """
        if subject not in self._str_to_id or predicate not in self._str_to_id or \
           object not in self._str_to_id or context not in self._str_to_id:
            return
        quad_id = (self._get_id(subject), self._get_id(predicate), 
                   self._get_id(object), self._get_id(context))
        if quad_id in self.quads:
            self.quads.remove(quad_id)
            self._remove_from_indices(quad_id)
            if hasattr(self.query, 'cache_clear'):
                self.query.cache_clear()

    def _remove_from_indices(self, quad_id):
        """Internal helper to remove a quad ID from the lookup dictionaries."""
        s, p, o, c = quad_id
        self.indices['spoc'][s][p][o].remove(c)
        self.indices['pocs'][p][o][c].remove(s)
        self.indices['ocsp'][o][c][s].remove(p)
        self.indices['cspo'][c][s][p].remove(o)

    def update(self, subject, predicate, old_object, new_object, context):
        """Updates the object value of an existing quad by replacing it."""
        self.remove(subject, predicate, old_object, context)
        self.add(subject, predicate, new_object, context)

    @lru_cache(maxsize=1000)
    def query(self, subject=None, predicate=None, object=None, context=None):
        """
        Searches the QuadStore for matching elements.
        Any omitted parameters are treated as wildcards. Results are cached.
        """
        sub_id = self._str_to_id.get(subject) if subject is not None else None
        pred_id = self._str_to_id.get(predicate) if predicate is not None else None
        obj_id = self._str_to_id.get(object) if object is not None else None
        ctx_id = self._str_to_id.get(context) if context is not None else None

        # Return early if querying for a string that isn't mapped
        if subject is not None and sub_id is None: return []
        if predicate is not None and pred_id is None: return []
        if object is not None and obj_id is None: return []
        if context is not None and ctx_id is None: return []

        if subject is not None:
            return self._query_by_subject(sub_id, pred_id, obj_id, ctx_id)
        elif predicate is not None:
            return self._query_by_predicate(pred_id, obj_id, ctx_id)
        elif object is not None:
            return self._query_by_object(obj_id, ctx_id)
        elif context is not None:
            return self._query_by_context(ctx_id)
        else:
            return [self._to_str_quad(q) for q in self.quads]

    def _query_by_subject(self, sub_id, pred_id=None, obj_id=None, ctx_id=None):
        """Internal helper to resolve queries targeting a specific subject."""
        results = []
        for p in list(self.indices['spoc'].get(sub_id, {})):
            if pred_id is None or p == pred_id:
                for o in list(self.indices['spoc'][sub_id][p]):
                    if obj_id is None or o == obj_id:
                        for c in list(self.indices['spoc'][sub_id][p][o]):
                            if ctx_id is None or c == ctx_id:
                                results.append(self._to_str_quad((sub_id, p, o, c)))
        return results

    def _query_by_predicate(self, pred_id, obj_id=None, ctx_id=None):
        """Internal helper to resolve queries targeting a specific predicate."""
        results = []
        for o in list(self.indices['pocs'].get(pred_id, {})):
            if obj_id is None or o == obj_id:
                for c in list(self.indices['pocs'][pred_id][o]):
                    if ctx_id is None or c == ctx_id:
                        for s in list(self.indices['pocs'][pred_id][o][c]):
                            results.append(self._to_str_quad((s, pred_id, o, c)))
        return results

    def _query_by_object(self, obj_id, ctx_id=None):
        """Internal helper to resolve queries targeting a specific object."""
        results = []
        for c in list(self.indices['ocsp'].get(obj_id, {})):
            if ctx_id is None or c == ctx_id:
                for s in list(self.indices['ocsp'][obj_id][c]):
                    for p in list(self.indices['ocsp'][obj_id][c][s]):
                        results.append(self._to_str_quad((s, p, obj_id, c)))
        return results

    def _query_by_context(self, ctx_id):
        """Internal helper to resolve queries targeting a specific context."""
        results = []
        for s in list(self.indices['cspo'].get(ctx_id, {})):
            for p in list(self.indices['cspo'][ctx_id][s]):
                for o in list(self.indices['cspo'][ctx_id][s][p]):
                    results.append(self._to_str_quad((s, p, o, ctx_id)))
        return results

    def batch_add(self, quads):
        """Adds a list of quads tuple elements sequentially."""
        for quad in quads:
            self.add(*quad)

    def batch_remove(self, quads):
        """Removes a list of quads tuple elements sequentially."""
        for quad in quads:
            self.remove(*quad)

    def save_to_file(self, filename):
        """Serializes the QuadStore to disk via iterative JSONLines dumps."""
        with open(filename, 'w') as f:
            for q_id in self.quads:
                f.write(json.dumps(self._to_str_quad(q_id)) + '\n')

    @classmethod
    def load_from_file(cls, filename):
        """
        Instantiates a QuadStore from a file, supporting fallback to legacy array schemas
        but prioritizing native line-delimited streaming syntax.
        """
        quad_store = cls()
        if not os.path.exists(filename):
            print(f"Warning: {filename} does not exist. Created an empty QuadStore.")
            return quad_store
        
        quads = []
        try:
            with open(filename, 'r') as f:
                content = f.read().strip()
                if not content:
                    return quad_store
                try:
                    quads = json.loads(content)
                except json.JSONDecodeError:
                    for line in content.split('\n'):
                        if line.strip():
                            quads.append(json.loads(line))
            quad_store.batch_add(quads)
        except Exception as e:
            print(f"Error loading {filename}: {e}")
        return quad_store

    def clear(self):
        """Completely purges the quadstore arrays, indices, ID maps, and clears the lookup cache."""
        self.quads.clear()
        self._str_to_id.clear()
        self._id_to_str.clear()
        self._next_id = 0
        for index in self.indices.values():
            index.clear()
        if hasattr(self.query, 'cache_clear'):
            self.query.cache_clear()

    def __len__(self):
        """Returns the total volume of discrete quads currently stored."""
        return len(self.quads)
