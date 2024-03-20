import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from .preprocessor import call_pdf_preprocess
from .utils.semantic_chuncker import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings
from lancedb.embeddings import EmbeddingFunctionRegistry
from lancedb.pydantic import LanceModel, Vector
import lancedb
import uuid


registry = EmbeddingFunctionRegistry().get_instance()
openai = registry.get("openai").create()


class Schema(LanceModel):
    vector: Vector(openai.ndims()) = openai.VectorField()
    id: str
    text: str


@dataclass
class SrcType:
    txt: List[str] = field(default_factory=lambda: ['txt', 'csv', 'json'])
    pdf: List[str] = field(default_factory=lambda: ['pdf'])
    word: List[str] = field(default_factory=lambda: ['doc', 'docx'])
    image: List[str] = field(default_factory=lambda: ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff'])
    sound: List[str] = field(default_factory=lambda: ['mp3', 'wav', 'aac', 'flac', 'ogg'])


class SrcIngestor(SrcType):
    """
    class that will read any document or file of various format and store its content in the corresponding memory bank
    """
    def __init__(self, memory_bank: str,
                 sess_name: str,
                 file_sources: Dict[str, list[str]],
                 schema=Schema,
                 openai_api=None) -> None:
        super().__init__()
        self.ai_credentials = openai_api
        self.base_schema = schema
        self.memory_bank = memory_bank
        self.file_sources = file_sources
        self._embeddings = OpenAIEmbeddings(openai_api_key=self.ai_credentials)
        current_dir = os.path.dirname(__file__)
        stm_dir = os.path.join(current_dir, '..', 'STM')
        self.db = lancedb.connect(f"{stm_dir}\\{self.memory_bank}")
        self._table = self.db.create_table(f"{sess_name}", schema=self.base_schema, mode="overwrite")

    def file_broker(self, progress_update=None) -> None:
        """
        This function will take file_sources and pair it with the corresponding method to ingest the file.
        """
        for file_type, files in self.file_sources.items():
            for file in files:
                extension = file.split('.')[-1]
                if extension in self.txt:
                    print(f"Processing {file}")
                    self.ingest_txt(file)
                elif extension in self.pdf:
                    print(f"Processing {file}")
                    self.ingest_pdf(file,  open_ai=self.ai_credentials)
                elif extension in self.word:
                    self.ingest_word(file)
                elif extension in self.image:
                    print(f"Processing {file}")
                    self.ingest_image(file)
                elif extension in self.sound:
                    print(f"Processing {file}")
                    self.ingest_sound(file)
                else:
                    print(f"Unsupported file type: {file}")
                # remove file from directory
                os.remove(file)

    def add_text(self, texts: List[Any], metadata: Optional[List[dict]] = None) -> None:
        docs = []
        ids = [str(uuid.uuid4()) for _ in texts]
        embeddings = self._embeddings.embed_documents(texts)
        for idx, text in enumerate(texts):
            embedding = embeddings[idx]
            meta = metadata[idx] if metadata else {}
            docs.append(
                {
                    "vector": embedding,
                    "id": ids[idx],
                    "text": text,
                    **meta,
                }
            )
        self._table.add(docs)

    def store_data(self, documents, metadata) -> None:
        self.add_text(documents, metadata)

    def ingest_word(self, payload) -> None:
        """
        This function will ingest a Word file and store its content in the corresponding memory bank.
        """
        pass

    def ingest_txt(self, payload) -> None:
        """
        This function will ingest a txt file (text, csv, json) and store its content in the corresponding memory bank.
        """
        pass

    def ingest_pdf(self, payload, open_ai) -> None:
        """
        This function will ingest a pdf file and store its content in the corresponding memory bank.
        """
        # Starting PDF ingestion
        processed_pdf, size = call_pdf_preprocess(payload, open_ai)

        # File name is the last part of the path and remove extension
        file_name = os.path.basename(payload).split('.')[0]
        txt_splitter = SemanticChunker(self._embeddings)

        # list all files in the same directory as the processed_pdf file
        other_file_names = os.listdir(payload.split(file_name)[0])

        metadata = [{'file_name': file_name, 'other_files': other_file_names,
                     'doc_info': {'file_type': 'pdf', 'pages_size': size}} for _ in range(len(processed_pdf))]

        pdf_documents = txt_splitter.split_text(processed_pdf)

        # Store processed_pdf in memory bank Vector Store
        self.store_data(pdf_documents, metadata)

    def ingest_image(self, payload) -> None:
        """
        This function will ingest an image (jpeg, etc) file and store its content in the corresponding memory bank.
        """
        pass

    def ingest_sound(self, payload) -> None:
        """
        This function will ingest a sound file and store its content in the corresponding memory bank.
        """
        pass

