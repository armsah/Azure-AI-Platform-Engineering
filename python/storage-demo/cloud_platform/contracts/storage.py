from typing import Protocol


class ObjectStorage(Protocol):

    def read_text(
        self,
        container: str,
        name: str,
    ) -> str:
        ...

    def write_text(
        self,
        container: str,
        name: str,
        content: str,
    ) -> None:
        ...