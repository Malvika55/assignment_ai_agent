from pathlib import Path

from app.document_loader import load_documents


def test_load_knowledge_base():
    knowledge_base = Path("knowledge-base")

    documents = load_documents(knowledge_base)

    assert len(documents) > 0


def test_document_metadata_is_loaded():
    knowledge_base = Path("knowledge-base")

    documents = load_documents(knowledge_base)

    returns_policy = next(
        document
        for document in documents
        if document.document_id == "RET-2026-01"
    )

    assert returns_policy.title == "Returns Policy"
    assert returns_policy.status == "active"
    assert returns_policy.policy_authority == "official"


def test_internal_document_is_marked_correctly():
    knowledge_base = Path("knowledge-base")

    documents = load_documents(knowledge_base)

    internal_document = next(
        document
        for document in documents
        if document.document_id == "MIG-TEST-04"
    )

    assert internal_document.status == "draft"
    assert internal_document.audience == "internal"
    assert internal_document.policy_authority == "none"