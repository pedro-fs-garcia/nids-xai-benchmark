from collections.abc import Mapping, Sequence
from pathlib import Path


class DataPreparationError(Exception):
    """Erro base do domínio de preparação dos dados."""


class SourceFileMissingError(DataPreparationError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Arquivo original não encontrado: {path}")


class HeaderMismatchError(DataPreparationError):
    def __init__(self, file: str, reference: str) -> None:
        self.file = file
        self.reference = reference
        super().__init__(f"O cabeçalho de {file} difere do cabeçalho de {reference}.")


class MalformedRecordError(DataPreparationError):
    def __init__(self, file: str, line: int, detail: str) -> None:
        self.file = file
        self.line = line
        super().__init__(f"Registro inválido em {file}, linha {line}: {detail}")


class UnexpectedColumnsError(DataPreparationError):
    def __init__(self, missing: Sequence[str], input_count: int, expected: int) -> None:
        self.missing = tuple(missing)
        self.input_count = input_count
        self.expected = expected
        if self.missing:
            message = f"Colunas obrigatórias ausentes: {', '.join(self.missing)}"
        else:
            message = f"Os CSVs têm {input_count} colunas de entrada; o contrato define {expected}."
        super().__init__(message)


class InconsistentAttemptedLabelError(DataPreparationError):
    """O sufixo "- Attempted" do rótulo e a coluna Attempted Category discordam."""

    def __init__(self, records: int) -> None:
        self.records = records
        super().__init__(
            f"{records} registros têm rótulo Attempted e Attempted Category incompatíveis."
        )


class NonFiniteValuesError(DataPreparationError):
    def __init__(self, columns: Mapping[str, int]) -> None:
        self.columns = dict(columns)
        detail = ", ".join(f"{name} ({count})" for name, count in self.columns.items())
        super().__init__(f"Valores não finitos sem regra de tratamento: {detail}")


class SplitVerificationError(DataPreparationError):
    def __init__(self, check: str, detail: str) -> None:
        self.check = check
        super().__init__(f"Verificação reprovada ({check}): {detail}")


class SourceChangedError(DataPreparationError):
    def __init__(self, files: Sequence[str]) -> None:
        self.files = tuple(files)
        super().__init__(
            f"Arquivos originais mudaram durante a preparação: {', '.join(self.files)}"
        )
