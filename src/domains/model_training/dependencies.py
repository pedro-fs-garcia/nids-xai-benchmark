from typing import TYPE_CHECKING

from config import get_settings
from core.classification import RandomForestAdapter
from domains.model_training.comparison import ForestComparisonService
from domains.model_training.exceptions import InvalidPilotConfigError
from domains.model_training.repository import ModelTrainingRepository
from domains.model_training.service import ModelTrainingService

if TYPE_CHECKING:
    from domains.model_training.xgboost_service import XGBoostComparisonService


def get_model_training_service() -> ModelTrainingService:
    settings = get_settings()
    repo = ModelTrainingRepository(
        data_dir=settings.derived_data_dir,
        runs_dir=settings.training_runs_dir,
        reports_dir=settings.reports_dir,
    )
    config = repo.read_config(settings.forest_pilot_config)
    try:
        model = RandomForestAdapter(config.model)
    except (TypeError, ValueError) as error:
        raise InvalidPilotConfigError(f"Parâmetros do Random Forest inválidos: {error}") from error
    return ModelTrainingService(repo=repo, config=config, model=model)


def get_forest_comparison_service() -> ForestComparisonService:
    settings = get_settings()
    repo = ModelTrainingRepository(
        data_dir=settings.derived_data_dir,
        runs_dir=settings.training_runs_dir,
        reports_dir=settings.reports_dir,
    )
    return ForestComparisonService(
        repo=repo,
        config=repo.read_comparison_config(settings.forest_comparison_config),
        model_factory=RandomForestAdapter,
    )


def get_xgboost_service() -> "XGBoostComparisonService":
    from core.xgboost_model import XGBoostAdapter
    from domains.model_training.xgboost_service import XGBoostComparisonService

    settings = get_settings()
    repo = ModelTrainingRepository(settings.derived_data_dir, settings.training_runs_dir, settings.reports_dir)
    return XGBoostComparisonService(
        repo=repo, config=repo.read_xgboost_config(settings.xgboost_config), model_factory=XGBoostAdapter,
    )
