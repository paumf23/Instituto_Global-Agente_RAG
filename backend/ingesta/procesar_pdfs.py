"""
Módulo de ingesta de documentos PDF.
Lee los PDFs de /documentos, los fragmenta y los almacena en ChromaDB
usando embeddings de Google Gemini.

Estrategia de chunking HÍBRIDA:
  1. Se intenta fragmentar por sección (respetando encabezados numerados
     tipo "1. Propósito y Alcance", "Capítulo III: ...") --esto da chunks
     semánticamente completos, sin partir una regla a la mitad.
  2. Si el documento no tiene ningún encabezado reconocible se cae
     automáticamente al fragmentado genérico por tamaño fijo.
"""
import os
import re

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

# Detecta encabezados de sección en los 3 formatos presentes en los documentos
PATRON_SECCION = re.compile(
    r"^(?:Capítulo\s+[IVXLC]+:[^\n]+"
    r"|Sección\s+\d+:[^\n]+"
    r"|\d+(?:\.\d+)?\.?[ \t]+[A-ZÁÉÍÓÚÑ¿][^\n]{2,80}"
    r"|¿[^\n]{5,100}\?)",
    re.MULTILINE,
)
LARGO_MINIMO_CHUNK = 50  


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


def _fragmentar_por_seccion(docs_pagina: list[Document]) -> list[Document] | None:
    if not docs_pagina:
        return None

    nombre_archivo = docs_pagina[0].metadata["fuente"]

    texto_completo = ""
    offsets_pagina: list[tuple[int, int]] = []  
    for doc in docs_pagina:
        offsets_pagina.append((len(texto_completo), doc.metadata["pagina"]))
        texto_completo += doc.page_content + "\n"

    matches = list(PATRON_SECCION.finditer(texto_completo))
    if not matches:
        return None  # sin estructura reconocible -> fallback genérico

    def pagina_en_offset(offset: int) -> int:
        pagina = offsets_pagina[0][1]
        for offset_inicio, num_pagina in offsets_pagina:
            if offset_inicio <= offset:
                pagina = num_pagina
            else:
                break
        return pagina

    chunks_crudos = []
    for i, m in enumerate(matches):
        inicio = m.start()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto_completo)
        contenido = texto_completo[inicio:fin].strip()
        if len(contenido) < 20:  # descarta matches espurios sin contenido real
            continue
        chunks_crudos.append({
            "texto": contenido,
            "seccion": m.group().strip(),
            "pagina": pagina_en_offset(inicio),
        })

    # Fusiona encabezados "vacíos" (título sin contenido propio, todo su
    # texto vive en sus subsecciones) con el chunk siguiente.
    fusionados = []
    for chunk in chunks_crudos:
        if fusionados and len(fusionados[-1]["texto"]) < LARGO_MINIMO_CHUNK:
            anterior = fusionados.pop()
            chunk["texto"] = anterior["texto"] + "\n" + chunk["texto"]
            chunk["seccion"] = f'{anterior["seccion"]} / {chunk["seccion"]}'
            chunk["pagina"] = anterior["pagina"]
        fusionados.append(chunk)

    return [
        Document(
            page_content=c["texto"],
            metadata={
                "fuente": nombre_archivo,
                "pagina": c["pagina"],
                "seccion": c["seccion"],
            },
        )
        for c in fusionados
    ]


def _fragmentar_generico(docs_pagina: list[Document]) -> list[Document]:
    """Fallback: Usado cuando no se detecta ningún encabezado de sección."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    return splitter.split_documents(docs_pagina)


def _fragmentar_documentos(docs_por_archivo: dict[str, list[Document]]) -> list[Document]:
    
    todos_los_chunks = []
    for nombre_archivo, docs_pagina in docs_por_archivo.items():
        chunks_seccion = _fragmentar_por_seccion(docs_pagina)
        if chunks_seccion is not None:
            print(f"  ✂️  {nombre_archivo}: chunking por sección ({len(chunks_seccion)} chunks)")
            todos_los_chunks.extend(chunks_seccion)
        else:
            chunks_genericos = _fragmentar_generico(docs_pagina)
            print(f"  ✂️  {nombre_archivo}: sin estructura reconocible, "
                  f"chunking genérico ({len(chunks_genericos)} chunks)")
            todos_los_chunks.extend(chunks_genericos)

    return todos_los_chunks


def inicializar_vectorstore() -> Chroma:

    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_metadata={"hnsw:space": "cosine"},
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

    docs_por_archivo: dict[str, list[Document]] = {}
    for pdf in sorted(pdfs):
        ruta = os.path.join(documentos_dir, pdf)
        docs_pagina = _extraer_texto_pdf(ruta)
        print(f"  📖 {pdf}: {len(docs_pagina)} páginas extraídas")
        docs_por_archivo[pdf] = docs_pagina

    chunks = _fragmentar_documentos(docs_por_archivo)
    print(f"  🔪 {len(chunks)} chunks generados en total")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_metadata={"hnsw:space": "cosine"},
    )

    print(f"✅ Ingesta completa. {len(chunks)} chunks almacenados en ChromaDB.")
    return vectorstore


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    inicializar_vectorstore()