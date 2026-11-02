"""Retrieval-Augmented Generation: chunking, vector store and retrieval.

Primary store: ChromaDB (persistent, local, default MiniLM embeddings).
Fallback: an in-memory BM25 keyword retriever, used when chromadb is not
installed or the collection has not been ingested yet, so the chatbot keeps
working (with weaker retrieval) instead of failing.

Populate the vector DB with:  python manage.py ingest_knowledge
"""
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

COLLECTION_NAME = 'fitness_knowledge'
SUPPORTED_SUFFIXES = {'.md', '.txt'}


@dataclass
class Chunk:
    id: str
    text: str
    source: str   # file name
    title: str    # document title (first H1, else file stem)


@dataclass
class Hit:
    text: str
    source: str
    title: str
    score: float  # higher is better


# ---------------------------------------------------------------- loading
def load_chunks(knowledge_dir, max_chars=900):
    chunks = []
    for path in sorted(Path(knowledge_dir).glob('*')):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        text = path.read_text(encoding='utf-8')
        title = _doc_title(text, path)
        for i, piece in enumerate(chunk_text(text, title, max_chars)):
            chunks.append(Chunk(id=f'{path.stem}-{i}', text=piece, source=path.name, title=title))
    return chunks


def _doc_title(text, path):
    for line in text.splitlines():
        if line.startswith('# '):
            return line[2:].strip()
    return path.stem.replace('_', ' ').title()


def chunk_text(text, title, max_chars=900):
    """Split markdown into chunks that never cross a heading and stay under max_chars.

    Every chunk is prefixed with 'Document title > Section heading' so it still
    makes sense on its own when retrieved.
    """
    sections, heading, body = [], '', []
    for line in text.splitlines():
        if line.startswith('#'):
            if body:
                sections.append((heading, '\n'.join(body)))
                body = []
            heading = line.lstrip('#').strip()
        else:
            body.append(line)
    if body:
        sections.append((heading, '\n'.join(body)))

    chunks = []
    for heading, body_text in sections:
        prefix = title if not heading or heading == title else f'{title} > {heading}'
        current = ''
        for para in (p.strip() for p in re.split(r'\n\s*\n', body_text)):
            if not para:
                continue
            while len(para) > max_chars:  # very long paragraph: hard split on a space
                cut = para.rfind(' ', 0, max_chars)
                cut = cut if cut > 0 else max_chars
                if current:
                    chunks.append(f'{prefix}\n{current}')
                    current = ''
                chunks.append(f'{prefix}\n{para[:cut]}')
                para = para[cut:].strip()
            if current and len(current) + len(para) + 2 > max_chars:
                chunks.append(f'{prefix}\n{current}')
                current = ''
            current = f'{current}\n\n{para}' if current else para
        if current:
            chunks.append(f'{prefix}\n{current}')
    return chunks


# ------------------------------------------------------------ retrievers
class KeywordRetriever:
    """BM25 over in-memory chunks. No dependencies."""

    STOPWORDS = set(
        'a an and are as at be by can do does for from how i in is it my of on or should that the '
        'to what when which with you your me about have has get much many'.split()
    )

    def __init__(self, chunks):
        self.chunks = chunks
        self.docs = [self._tokens(c.text) for c in chunks]
        self.avg_len = (sum(len(d) for d in self.docs) / len(self.docs)) if self.docs else 0
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    @classmethod
    def _tokens(cls, text):
        return [t for t in re.findall(r'[a-z0-9]+', text.lower()) if t not in cls.STOPWORDS]

    def search(self, query, k=4):
        q = self._tokens(query)
        scored = []
        for chunk, doc in zip(self.chunks, self.docs):
            tf = Counter(doc)
            score = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    score += self.idf[t] * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * len(doc) / self.avg_len))
            if score > 0:
                scored.append(Hit(chunk.text, chunk.source, chunk.title, score))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]


class ChromaRetriever:
    def __init__(self, persist_dir, max_distance=0.95):
        import chromadb  # imported lazily so the app runs without it

        self.max_distance = max_distance
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(
            COLLECTION_NAME, metadata={'hnsw:space': 'cosine'}
        )

    def count(self):
        return self.collection.count()

    def ingest(self, chunks, reset=True):
        if reset:
            self.client.delete_collection(COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(
                COLLECTION_NAME, metadata={'hnsw:space': 'cosine'}
            )
        for start in range(0, len(chunks), 100):  # batch to stay under Chroma's max batch size
            batch = chunks[start:start + 100]
            self.collection.add(
                ids=[c.id for c in batch],
                documents=[c.text for c in batch],
                metadatas=[{'source': c.source, 'title': c.title} for c in batch],
            )
        return len(chunks)

    def search(self, query, k=4):
        result = self.collection.query(query_texts=[query], n_results=k)
        hits = []
        for doc, meta, dist in zip(result['documents'][0], result['metadatas'][0], result['distances'][0]):
            if dist <= self.max_distance:
                hits.append(Hit(doc, meta['source'], meta['title'], 1 - dist))
        return hits


# ---------------------------------------------------------------- facade
def knowledge_dir():
    return Path(__file__).resolve().parent.parent / 'knowledge'


@lru_cache(maxsize=1)
def get_retriever():
    """Chroma if available and populated, otherwise the keyword fallback."""
    from django.conf import settings

    try:
        retriever = ChromaRetriever(settings.CHROMA_DIR, getattr(settings, 'RAG_MAX_DISTANCE', 0.95))
        if retriever.count() > 0:
            return retriever
        logger.warning('Vector DB is empty - run "python manage.py ingest_knowledge". '
                       'Using keyword retrieval instead.')
    except ImportError:
        logger.warning('chromadb is not installed - using keyword retrieval instead.')
    except Exception:
        logger.exception('Could not open the vector DB - using keyword retrieval instead.')
    return KeywordRetriever(load_chunks(knowledge_dir()))


def retrieve(query, k=None):
    from django.conf import settings

    k = k or getattr(settings, 'RAG_TOP_K', 4)
    try:
        return get_retriever().search(query, k)
    except Exception:
        logger.exception('Retrieval failed; answering without reference material.')
        return []
