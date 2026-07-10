"""The mock embedding provider must be deterministic and correctly shaped."""
from app.services.embeddings.mock_provider import MockEmbeddingProvider


def test_mock_embedding_dim_and_determinism():
    p = MockEmbeddingProvider(dim=768)
    a = p.embed_one("swimming pool and clubhouse")
    b = p.embed_one("swimming pool and clubhouse")
    assert len(a) == 768
    assert a == b  # deterministic


def test_similar_text_more_similar_than_unrelated():
    p = MockEmbeddingProvider(dim=768)

    def dot(x, y):
        return sum(i * j for i, j in zip(x, y))

    base = p.embed_one("clubhouse gym swimming pool")
    similar = p.embed_one("gym and swimming pool clubhouse")
    unrelated = p.embed_one("payment plan possession date price")
    assert dot(base, similar) > dot(base, unrelated)
