from worker.tasks.process_document import process_document
from worker.tasks.run_ocr import run_ocr
from worker.tasks.generate_embeddings import generate_embeddings
from worker.tasks.analyze_document import analyze_document
from worker.tasks.generate_report import generate_report
from worker.tasks.cleanup_documents import cleanup_documents

__all__ = [
    "process_document",
    "run_ocr",
    "generate_embeddings",
    "analyze_document",
    "generate_report",
    "cleanup_documents",
]
