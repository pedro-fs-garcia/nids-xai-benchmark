from pathlib import Path

from config import PROJECT_ROOT, get_settings
from core.pcap_tools import PcapTools
from domains.traffic_preparation.repository import TrafficRepository
from domains.traffic_preparation.service import TrafficPreparationService


def get_traffic_preparation_service(config_path: Path | None = None) -> TrafficPreparationService:
    settings = get_settings()
    return TrafficPreparationService(
        TrafficRepository(PROJECT_ROOT, settings.derived_data_dir, settings.training_runs_dir, settings.reports_dir),
        PcapTools(),
        settings.extractor_build_dir,
        config_path or settings.pcap_preparation_config,
    )
