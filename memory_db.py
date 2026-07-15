"""In-memory fallback for the MongoDB collection.

Implements the small subset of the pymongo collection API this bot uses so the
app can run without a MongoDB instance. State lives in a plain dict keyed by the
document's ``_id`` and is lost when the process exits.

Supported operations:
    - find_one(filter)
    - find(filter, projection)          -> iterable of documents
    - count_documents(filter)
    - update_one(filter, update, upsert=False)
        update operators: $set, $setOnInsert, $inc (dotted keys supported)
    filter operators: plain equality and {"$exists": bool}
"""

import copy
import itertools
import threading


def _matches(doc, filter):
    """Return True if ``doc`` satisfies the (small) query ``filter``."""
    for key, cond in filter.items():
        if isinstance(cond, dict) and "$exists" in cond:
            present = key in doc
            if present != bool(cond["$exists"]):
                return False
        else:
            if doc.get(key) != cond:
                return False
    return True


def _set_dotted(doc, dotted_key, value):
    """Set ``value`` at a possibly dotted key path (e.g. 'stats.files_sent')."""
    parts = dotted_key.split(".")
    target = doc
    for part in parts[:-1]:
        nxt = target.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            target[part] = nxt
        target = nxt
    target[parts[-1]] = value


def _get_dotted(doc, dotted_key, default=None):
    parts = dotted_key.split(".")
    target = doc
    for part in parts:
        if not isinstance(target, dict) or part not in target:
            return default
        target = target[part]
    return target


class InMemoryCollection:
    """Minimal thread-safe stand-in for a pymongo collection."""

    def __init__(self):
        self._docs = {}
        self._lock = threading.RLock()
        self._ids = itertools.count(1)

    def find_one(self, filter):
        with self._lock:
            for doc in self._docs.values():
                if _matches(doc, filter):
                    return copy.deepcopy(doc)
            return None

    def find(self, filter=None, projection=None):
        filter = filter or {}
        with self._lock:
            # Materialise the list under the lock so callers can iterate freely.
            return [copy.deepcopy(doc) for doc in self._docs.values() if _matches(doc, filter)]

    def count_documents(self, filter):
        filter = filter or {}
        with self._lock:
            return sum(1 for doc in self._docs.values() if _matches(doc, filter))

    def update_one(self, filter, update, upsert=False):
        with self._lock:
            doc = None
            for existing in self._docs.values():
                if _matches(existing, filter):
                    doc = existing
                    break

            inserted = False
            if doc is None:
                if not upsert:
                    return
                # Seed the new document from equality conditions in the filter.
                doc = {}
                for key, cond in filter.items():
                    if not (isinstance(cond, dict) and "$exists" in cond):
                        doc[key] = cond
                doc["_id"] = next(self._ids)
                self._docs[doc["_id"]] = doc
                inserted = True

            for key, value in update.get("$setOnInsert", {}).items():
                if inserted:
                    _set_dotted(doc, key, value)

            for key, value in update.get("$set", {}).items():
                _set_dotted(doc, key, value)

            for key, amount in update.get("$inc", {}).items():
                current = _get_dotted(doc, key, 0) or 0
                _set_dotted(doc, key, current + amount)
