
import json

from qdrant_client import QdrantClient, models

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "rag_pipeline_smoke_test_4d"

client = QdrantClient(url=QDRANT_URL, timeout=10)

if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=4,
            distance=models.Distance.COSINE
        )
    )

collection_info = client.get_collection(COLLECTION_NAME)
vector_config = collection_info.config.params.vectors

if vector_config.size != 4:
    raise ValueError("Existing test collection has an unexpected vector dimension")

points = [
    models.PointStruct(
        id=1,
        vector=[0.90, 0.10, 0.00, 0.00],
        payload={
            "source": "fastapi",
            "category": "documentation",
            "content": "FastAPI supports dependency injection."
        }
    ),
    models.PointStruct(
        id=2,
        vector=[0.85, 0.15, 0.05, 0.00],
        payload={
            "source": "python",
            "category": "documentation",
            "content": "Python supports functions and classes."
        }
    ),
    models.PointStruct(
        id=3,
        vector=[0.05, 0.10, 0.90, 0.00],
        payload={
            "source": "security",
            "category": "research",
            "content": "Prompt injection is a security risk in RAG."
        }
    )
]

client.upsert(
    collection_name=COLLECTION_NAME,
    points=points,
    wait=True
)

retrieved_points = client.retrieve(
    collection_name=COLLECTION_NAME,
    ids=[1, 2, 3],
    with_payload=True,
    with_vectors=True
)

search_results = client.query_points(
    collection_name=COLLECTION_NAME,
    query=[0.90, 0.10, 0.00, 0.00],
    limit=3,
    with_payload=True
).points

filtered_results = client.query_points(
    collection_name=COLLECTION_NAME,
    query=[0.90, 0.10, 0.00, 0.00],
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value="documentation")
            )
        ]
    ),
    limit=3,
    with_payload=True
).points

print("\n===== COLLECTION INFORMATION =====")
print(collection_info)

print("\n===== RETRIEVED POINTS =====")
for point in retrieved_points:
    print(json.dumps(point.model_dump(), indent=2, default=str))

print("\n===== SIMILARITY SEARCH =====")
for result in search_results:
    print({
        "id": result.id,
        "score": result.score,
        "payload": result.payload
    })

print("\n===== FILTERED SEARCH =====")
for result in filtered_results:
    print({
        "id": result.id,
        "score": result.score,
        "payload": result.payload
    })

print("\nQDRANT PYTHON INTEGRATION TEST PASSED")
