from config import PROJECT_ROOT, get_settings
from domains.campaign.audit import CampaignAudit
from domains.campaign.results import CampaignResults
from domains.campaign.service import CampaignService
from domains.nids.dependencies import get_nids_service
from domains.nids.repository import NidsRepository


def _repository() -> NidsRepository:
    settings = get_settings()
    return NidsRepository(PROJECT_ROOT, settings.derived_data_dir, settings.training_runs_dir, settings.reports_dir)


def get_campaign_service() -> CampaignService:
    return CampaignService(_repository(), get_nids_service())


def get_campaign_audit() -> CampaignAudit:
    return CampaignAudit(_repository())


def get_campaign_results() -> CampaignResults:
    return CampaignResults(_repository())
