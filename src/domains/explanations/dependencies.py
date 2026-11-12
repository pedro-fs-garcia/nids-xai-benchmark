from pathlib import Path

from config import PROJECT_ROOT, get_settings
from core.process_runner import PythonProcessRunner
from domains.explanations.repository import ExplanationRepository
from domains.explanations.service import ExplanationService


def get_explanation_service(config_path: Path | None = None) -> ExplanationService:
    settings = get_settings()
    return ExplanationService(
        ExplanationRepository(PROJECT_ROOT, settings.derived_data_dir, settings.training_runs_dir, settings.reports_dir),
        PythonProcessRunner(),
        config_path or settings.tree_shap_config,
    )
