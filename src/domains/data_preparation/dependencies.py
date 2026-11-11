from config import get_settings
from domains.data_preparation.repository import DataPreparationRepository
from domains.data_preparation.service import DataPreparationService


def get_data_preparation_repository() -> DataPreparationRepository:
    settings = get_settings()
    return DataPreparationRepository(
        raw_dir=settings.raw_data_dir,
        derived_dir=settings.derived_data_dir,
        source_files=settings.source_files,
    )


def get_data_preparation_service() -> DataPreparationService:
    settings = get_settings()
    return DataPreparationService(
        repo=get_data_preparation_repository(),
        fractions=settings.split_fractions,
        seed=settings.split_seed,
    )
