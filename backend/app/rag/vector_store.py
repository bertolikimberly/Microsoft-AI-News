# Re-export from app.pipeline.rag so both import paths work:
#   from app.pipeline.rag.vector_store import ArticleVectorStore  (local/legacy)
#   from app.rag.vector_store import ArticleVectorStore           (team/origin/main)
from app.pipeline.rag.vector_store import ArticleVectorStore, _orm_to_pipeline  # noqa: F401
