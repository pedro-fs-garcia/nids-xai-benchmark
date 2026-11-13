from pathlib import Path

from config import PROJECT_ROOT, get_settings
from domains.nids.repository import NidsRepository
from domains.nids.service import NidsService


def get_nids_service(config_path: Path | None = None) -> NidsService:
    settings = get_settings()
    return NidsService(
        NidsRepository(PROJECT_ROOT, settings.derived_data_dir, settings.training_runs_dir, settings.reports_dir),
        settings.extractor_build_dir,
        config_path or settings.nids_config,
    )
