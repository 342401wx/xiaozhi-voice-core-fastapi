import json
from pathlib import Path

import chromadb
from config import VECTOR_DB_PATH

client = chromadb.PersistentClient(path=VECTOR_DB_PATH)

def get_or_create_collection(name):
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )

def add_documents(collection_name, documents, metadatas=None, ids=None):
    collection = get_or_create_collection(collection_name)
    if ids is None:
        ids = [f"doc_{collection.count() + i}" for i in range(len(documents))]
    metadatas = _metadatas_with_defaults(collection_name, metadatas, ids)
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    return ids

def upsert_documents(collection_name, documents, metadatas=None, ids=None):
    collection = get_or_create_collection(collection_name)
    if ids is None:
        ids = [f"doc_{collection.count() + i}" for i in range(len(documents))]
    metadatas = _metadatas_with_defaults(collection_name, metadatas, ids)
    collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
    return ids

def query_documents(collection_name, query_text, n_results=3):
    collection = get_or_create_collection(collection_name)
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )
    return results

def delete_documents(collection_name, ids):
    collection = get_or_create_collection(collection_name)
    collection.delete(ids=ids)

def update_documents(collection_name, ids, documents, metadatas=None):
    collection = get_or_create_collection(collection_name)
    metadatas = _metadatas_with_defaults(collection_name, metadatas, ids) if metadatas else None
    collection.update(ids=ids, documents=documents, metadatas=metadatas)

def get_collection_stats(collection_name):
    collection = get_or_create_collection(collection_name)
    return {"count": collection.count(), "name": collection_name}

def _metadata_value_for_chroma(value):
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)

def _normalize_metadatas(metadatas):
    if metadatas is None:
        return None
    return [
        {key: _metadata_value_for_chroma(value) for key, value in (metadata or {}).items()}
        for metadata in metadatas
    ]

def _metadatas_with_defaults(collection_name, metadatas, ids):
    normalized = _normalize_metadatas(metadatas) or [{} for _ in ids]
    if len(normalized) < len(ids):
        normalized.extend({} for _ in range(len(ids) - len(normalized)))
    normalized = normalized[:len(ids)]
    for metadata, doc_id in zip(normalized, ids):
        metadata.setdefault("collection", collection_name)
        metadata.setdefault("doc_id", doc_id)
        metadata.setdefault("source_id", doc_id)
        metadata.setdefault("title", doc_id)
        metadata.setdefault("source_file", "runtime_update")
        metadata.setdefault("source_address", f"runtime_update#collection={collection_name}&doc_id={doc_id}")
    return normalized

def _metadata_for_chroma(item, collection_name, knowledge_path):
    metadata = dict(item.get("metadata") or {})
    doc_id = item.get("id", "")
    source_file = str(knowledge_path.resolve())

    metadata["source_id"] = item.get("id", "")
    metadata["doc_id"] = doc_id
    metadata["title"] = item.get("title", "")
    metadata["collection"] = collection_name
    metadata["source_file"] = source_file
    metadata["source_address"] = f"{source_file}#collection={collection_name}&doc_id={doc_id}"

    if isinstance(metadata.get("tags"), list):
        metadata["tags"] = ",".join(metadata["tags"])
    return metadata

def init_knowledge_base():
    try:
        knowledge_path = Path(__file__).with_name("enterprise_service_desk_knowledge_base.json")
        with knowledge_path.open("r", encoding="utf-8") as f:
            knowledge_base = json.load(f)

        for collection_name, items in knowledge_base["collections"].items():
            ids = [item["id"] for item in items]
            documents = [item["text"] for item in items]
            metadatas = [_metadata_for_chroma(item, collection_name, knowledge_path) for item in items]
            upsert_documents(collection_name, documents, metadatas, ids)
    except Exception as e:
        print(f"知识库初始化失败（可稍后手动导入）: {e}")

if __name__ == "__main__":
    init_knowledge_base()
    print("知识库初始化完成")
