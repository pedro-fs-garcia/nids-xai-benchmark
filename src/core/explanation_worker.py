"""Processo explicador do modo assíncrono e a fila de explicações pendentes que o alimenta.

Único módulo que conhece esse processo, as suas mensagens e os registros que ele grava, como
core/flow_extractor.py faz com o extrator. O processo é iniciado no modo spawn, carrega a própria cópia do
modelo congelado e grava as explicações no canal de saída das explicações da execução. Durante a execução,
nenhuma mensagem volta ao classificador. Há uma mensagem de prontidão, antes de a captura abrir, e uma de
encerramento, depois que a fila esvazia.
"""

import csv
import json
import multiprocessing
import os
import queue
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from core.instrumentation import monotonic_ns
from core.process_resources import phase_usage, pin_all_threads, self_usage, start_phase

# Marcações de quem gera a explicação. A retirada da fila só existe no modo assíncrono.
EXPLANATION_TIMING = ["seq", "dequeued_ns", "explanation_start_ns", "explanation_end_ns", "t4_ns"]
# Espera máxima pela prontidão do processo explicador, que verifica o modelo e constrói o explicador.
READY_TIMEOUT_S = 300.0
# Intervalo em que uma espera por vaga na fila confere se o processo explicador ainda está vivo.
POLL_S = 1.0
_END = "end"


def explanation_record(seq: int, flow_id: str, reference_value: float, contributions: np.ndarray) -> dict[str, Any]:
    """Registro do canal de saída das explicações. As contribuições seguem a ordem das entradas do manifesto."""
    return {"seq": seq, "flow_id": flow_id, "reference_value": reference_value,
            "contributions": np.asarray(contributions, dtype=np.float64).tolist()}


class ExplanationWorkerError(RuntimeError):
    """O processo explicador terminou com erro ou não respondeu a tempo."""


class ExplanationWorker:
    """Processo explicador e fila de explicações pendentes, vistos pelo classificador.

    A fábrica é uma função de módulo, chamada no processo explicador com os argumentos dados. Ela devolve a
    função que explica um vetor de entradas, com o valor de referência e as contribuições, e um dicionário
    com os tempos de carregamento, construção e aquecimento."""

    def __init__(self, factory: Callable[..., Any], factory_args: tuple[Any, ...], run_dir: Path, limit: int,
                 cpus: list[int] | None, threads: int) -> None:
        context = multiprocessing.get_context("spawn")
        self.limit = limit
        self.requests = context.Queue(maxsize=limit)
        self._results = context.Queue()
        self.process = context.Process(target=_serve, name="explainer", daemon=True, args=(
            factory, factory_args, str(run_dir), cpus, threads, self.requests, self._results))
        self.process.start()
        self.accepted = 0
        self.dropped = 0
        try:
            self.ready = self._result("ready", READY_TIMEOUT_S)
        except BaseException:
            self.kill()
            raise

    def submit(self, seq: int, flow_id: str, vector: np.ndarray, block: bool) -> bool:
        """Encaminha a solicitação de explicação de um fluxo. Sem bloqueio, a fila cheia descarta a solicitação."""
        item = (seq, flow_id, vector)
        if not block:
            try:
                self.requests.put_nowait(item)
            except queue.Full:
                self.dropped += 1
                return False
            self.accepted += 1
            return True
        while True:
            try:
                self.requests.put(item, timeout=POLL_S)
            except queue.Full:
                if not self.process.is_alive():
                    raise ExplanationWorkerError(f"O processo explicador terminou com código {self.process.exitcode}.")
                continue
            self.accepted += 1
            return True

    def finish(self, drain_timeout_s: float) -> dict[str, Any]:
        """Envia a marca de fim e espera o processo explicador esvaziar a fila.

        Passado o tempo máximo de esvaziamento, o processo é encerrado, e as solicitações que restaram ficam
        pendentes."""
        started = monotonic_ns()
        deadline = started + int(drain_timeout_s * 1e9)
        record: dict[str, Any] = {"end_sent_ns": None, "killed_after_drain_timeout": False, "worker": None}
        try:
            while record["end_sent_ns"] is None:
                remaining = (deadline - monotonic_ns()) / 1e9
                if remaining <= 0:
                    raise TimeoutError
                try:
                    self.requests.put(_END, timeout=min(POLL_S, remaining))
                    record["end_sent_ns"] = monotonic_ns()
                except queue.Full:
                    self._check_alive()
            record["worker"] = self._result("end", max((deadline - monotonic_ns()) / 1e9, 0.001))
            self.process.join(timeout=max((deadline - monotonic_ns()) / 1e9, 0.001) + 30)
        except TimeoutError:
            record["killed_after_drain_timeout"] = True
            self.kill()
        record.update({"finished_ns": monotonic_ns(), "exit_code": self.process.exitcode,
                       "accepted": self.accepted, "dropped": self.dropped, "limit": self.limit,
                       "drain_timeout_s": drain_timeout_s})
        return record

    def kill(self) -> None:
        # As solicitações que restam no buffer da fila não devem prender o fim do classificador.
        self.requests.cancel_join_thread()
        self._results.cancel_join_thread()
        if self.process.is_alive():
            self.process.kill()
        self.process.join(timeout=30)

    def _check_alive(self) -> None:
        if not self.process.is_alive():
            raise ExplanationWorkerError(f"O processo explicador terminou com código {self.process.exitcode}: "
                                         f"{self._error_message()}")

    def _error_message(self) -> str:
        try:
            kind, payload = self._results.get_nowait()
        except queue.Empty:
            return "sem mensagem de erro"
        return payload if kind == "error" else f"mensagem inesperada {kind}"

    def _result(self, expected: str, timeout_s: float) -> dict[str, Any]:
        deadline = monotonic_ns() + int(timeout_s * 1e9)
        while True:
            remaining = (deadline - monotonic_ns()) / 1e9
            if remaining <= 0:
                raise TimeoutError
            try:
                kind, payload = self._results.get(timeout=min(POLL_S, remaining))
            except queue.Empty:
                if not self.process.is_alive():
                    raise ExplanationWorkerError(
                        f"O processo explicador terminou com código {self.process.exitcode} antes da mensagem "
                        f"{expected}.") from None
                continue
            if kind == "error":
                raise ExplanationWorkerError(f"Erro no processo explicador: {payload}")
            if kind != expected:
                raise ExplanationWorkerError(f"Mensagem {kind} do processo explicador; esperada {expected}.")
            return payload


def read_explanations(run_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """Registros do canal de saída das explicações, com as marcações de quem gerou cada explicação.

    Devolve também quantos registros do canal ficaram sem marcações. Isso só acontece quando o processo
    explicador é encerrado entre a escrita do registro e a das suas marcações."""
    with (run_dir / "explanations.csv").open(newline="", encoding="utf-8") as stream:
        marks = {int(row["seq"]): {key: int(value) if value else None for key, value in row.items()}
                 for row in csv.DictReader(stream)}
    records = []
    with (run_dir / "explanations.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # Só a última linha pode ficar incompleta, e ela não tem marcações.
                continue
    channel = {record["seq"] for record in records}
    if any(seq not in channel for seq in marks):
        raise ExplanationWorkerError("Há marcações de explicação sem registro no canal de saída das explicações.")
    complete = [{**record, **marks[record["seq"]]} for record in records if record["seq"] in marks]
    return complete, len(records) - len(complete)


def _serve(factory: Callable[..., Any], factory_args: tuple[Any, ...], run_dir: str, cpus: list[int] | None,
           threads: int, requests: Any, results: Any) -> None:
    """Laço do processo explicador: retira uma solicitação, explica o fluxo e grava a explicação."""
    try:
        from threadpoolctl import threadpool_limits

        if cpus is not None:
            pin_all_threads(cpus)
        directory = Path(run_dir)
        with threadpool_limits(limits=threads):
            explain, info = factory(*factory_args)
            with (directory / "explanations.jsonl").open("w", encoding="utf-8") as channel, \
                    (directory / "explanations.csv").open("w", newline="", encoding="utf-8") as table_stream:
                table = csv.DictWriter(table_stream, fieldnames=EXPLANATION_TIMING)
                table.writeheader()
                results.put(("ready", {**info, "pid": os.getpid(), "monotonic_ns": monotonic_ns()}))
                # O uso de recursos que interessa é o do atendimento das solicitações, sem a carga do modelo.
                serving = start_phase()
                received = 0
                while True:
                    item = requests.get()
                    dequeued = monotonic_ns()
                    if item == _END:
                        break
                    received += 1
                    seq, flow_id, vector = item
                    start = monotonic_ns()
                    reference_value, contributions = explain(vector)
                    end = monotonic_ns()
                    channel.write(json.dumps(explanation_record(seq, flow_id, reference_value, contributions)) + "\n")
                    channel.flush()
                    t4 = monotonic_ns()
                    table.writerow({"seq": seq, "dequeued_ns": dequeued, "explanation_start_ns": start,
                                    "explanation_end_ns": end, "t4_ns": t4})
        results.put(("end", {"received": received, "end_dequeued_ns": dequeued, "process": phase_usage(serving),
                             "process_total": self_usage()}))
    except BaseException:
        results.put(("error", traceback.format_exc()))
        raise
