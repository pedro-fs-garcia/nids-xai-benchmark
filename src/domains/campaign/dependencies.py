from config import PROJECT_ROOT, get_settings
from domains.campaign.service import CampaignService
from domains.nids.dependencies import get_nids_service
from domains.nids.repository import NidsRepository


def get_campaign_service() -> CampaignService:
    settings = get_settings()
    return CampaignService(
        NidsRepository(PROJECT_ROOT, settings.derived_data_dir, settings.training_runs_dir, settings.reports_dir),
        get_nids_service(),
    )
