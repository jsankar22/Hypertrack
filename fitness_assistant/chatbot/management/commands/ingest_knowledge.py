from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chatbot.services import rag


class Command(BaseCommand):
    help = 'Chunk the documents in chatbot/knowledge/ and load them into the ChromaDB vector store.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', default=None, help='Folder of .md/.txt files (default: chatbot/knowledge)')
        parser.add_argument('--max-chars', type=int, default=900, help='Maximum characters per chunk')

    def handle(self, *args, **options):
        folder = options['dir'] or rag.knowledge_dir()
        chunks = rag.load_chunks(folder, options['max_chars'])
        if not chunks:
            raise CommandError(f'No .md or .txt documents found in {folder}')

        try:
            retriever = rag.ChromaRetriever(settings.CHROMA_DIR)
        except ImportError:
            raise CommandError('chromadb is not installed. Run: pip install -r requirements.txt')

        self.stdout.write('Embedding chunks (the first run downloads a small embedding model)...')
        count = retriever.ingest(chunks, reset=True)
        docs = len({c.source for c in chunks})
        self.stdout.write(self.style.SUCCESS(f'Ingested {count} chunks from {docs} documents into {settings.CHROMA_DIR}'))
