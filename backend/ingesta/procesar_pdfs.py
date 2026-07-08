"""
Módulo de ingesta de documentos PDF.
Lee los PDFs de /documentos, los fragmenta y los almacena en ChromaDB
usando embeddings de Google Gemini.
"""
import os

import fitz 
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma


DOCUMENTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "documentos")
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "instituto_global"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "models/gemini-embedding-001"


def _extraer_texto_pdf(pdf_path: str) -> list[Document]:

    docs = []
    nombre_archivo = os.path.basename(pdf_path)

    with fitz.open(pdf_path) as pdf:
        for num_pagina, pagina in enumerate(pdf, start=1):
            texto = pagina.get_text("text").strip()
            if texto:
                docs.append(Document(
                    page_content=texto,
                    metadata={"fuente": nombre_archivo, "pagina": num_pagina}
                ))

    return docs


def _fragmentar_documentos(docs: list[Document]) -> list[Document]:
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    return splitter.split_documents(docs)


def inicializar_vectorstore() -> Chroma:
   
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )

   
    cantidad = vectorstore._collection.count()
    if cantidad > 0:
        print(f"✅ ChromaDB ya contiene {cantidad} chunks. Saltando ingesta.")
        return vectorstore

    
    print("📄 Iniciando ingesta de documentos...")

    documentos_dir = os.path.abspath(DOCUMENTOS_DIR)
    pdfs = [f for f in os.listdir(documentos_dir) if f.endswith(".pdf")]

    if not pdfs:
        print("⚠️ No se encontraron archivos PDF en:", documentos_dir)
        return vectorstore

    todos_los_docs = []
    for pdf in sorted(pdfs):
        ruta = os.path.join(documentos_dir, pdf)
        docs_pagina = _extraer_texto_pdf(ruta)
        print(f"  📖 {pdf}: {len(docs_pagina)} páginas extraídas")
        todos_los_docs.extend(docs_pagina)

    chunks = _fragmentar_documentos(todos_los_docs)
    print(f"  🔪 {len(chunks)} chunks generados")

    
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    print(f"✅ Ingesta completa. {len(chunks)} chunks almacenados en ChromaDB.")
    return vectorstore


if __name__ == "__main__":
   
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    inicializar_vectorstore()
