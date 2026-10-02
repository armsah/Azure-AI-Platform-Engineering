class MemoryObjectStorage:

    def __init__(self):
        self.objects: dict[
            tuple[str, str],
            str,
        ] = {}

    def write_text(
        self,
        container: str,
        name: str,
        content: str,
    ) -> None:
        self.objects[(container, name)] = content

    def read_text(
        self,
        container: str,
        name: str,
    ) -> str:
        return self.objects[(container, name)]