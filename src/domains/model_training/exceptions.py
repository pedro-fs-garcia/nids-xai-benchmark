class ModelTrainingError(Exception):
    """Erro base do domínio de treinamento."""


class InvalidTrainingDataError(ModelTrainingError):
    """Os dados derivados não correspondem ao contrato ou ao manifesto."""


class InvalidPilotConfigError(ModelTrainingError):
    """A configuração não permite executar o treinamento piloto."""
