"""Configuração única do projeto."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    raw_data_dir: Path = PROJECT_ROOT / "cicids-dataset"
    derived_data_dir: Path = PROJECT_ROOT / "derived-data"
    training_runs_dir: Path = PROJECT_ROOT / "training-runs"
    reports_dir: Path = PROJECT_ROOT / "relatorios"
    forest_pilot_config: Path = PROJECT_ROOT / "configs" / "random-forest-pilot.json"
    forest_comparison_config: Path = PROJECT_ROOT / "configs" / "random-forest-comparison.json"
    source_files: tuple[str, ...] = (
        "monday.csv",
        "tuesday.csv",
        "wednesday.csv",
        "thursday.csv",
        "friday.csv",
    )

    split_seed: int = 42
    train_fraction: float = 0.70
    validation_fraction: float = 0.15
    test_fraction: float = 0.15

    @property
    def split_fractions(self) -> tuple[float, float, float]:
        return (self.train_fraction, self.validation_fraction, self.test_fraction)


@lru_cache
def get_settings() -> Settings:
    return Settings()
