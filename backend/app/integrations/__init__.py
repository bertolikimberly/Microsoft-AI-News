"""
Integration glue between the backend and the sibling `llm_engineering/`
tree (taxonomy bridge, ORM <-> Pydantic adapter, pipeline bootstrap).

Importing this package side-effect-inserts `llm_engineering/` on
sys.path so `taxonomy.py` and `llm_bridge.py` can do top-level
`from src.* import ...`. Keep this as the single entry point for any
backend module that needs to talk to the pipeline.
"""
from app.integrations.bootstrap import ensure_pipeline_importable

ensure_pipeline_importable()
