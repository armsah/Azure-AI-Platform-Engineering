from cloud_platform.adapters.memory_storage import (
    MemoryObjectStorage,
)


def test_application_storage_contract():
    storage = MemoryObjectStorage()

    storage.write_text(
        "documents",
        "architecture.txt",
        "portable platform",
    )

    result = storage.read_text(
        "documents",
        "architecture.txt",
    )

    assert result == "portable platform"