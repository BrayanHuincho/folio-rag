from folio.ingest.chunker import Chunk, chunk
from folio.ingest.parsers import ParseError, Section, UnsupportedFile, parse, set_image_describer, supported

__all__ = [
    "Chunk",
    "ParseError",
    "Section",
    "UnsupportedFile",
    "chunk",
    "get_index_manager",
    "parse",
    "set_image_describer",
    "supported",
]


def __getattr__(name: str):
    # import diferido: pipeline arrastra embeddings y watchfiles
    if name in {"IndexManager", "get_index_manager"}:
        from folio.ingest import pipeline

        return getattr(pipeline, name)
    raise AttributeError(name)
