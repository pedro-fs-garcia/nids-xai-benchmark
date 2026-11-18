#!/usr/bin/env python3
"""Reproduz um trecho de PCAP em rede emulada pelo Mininet, em uma ou mais cópias ao mesmo tempo, e captura o
tráfego com o NIDS.

Executar com sudo e o Python do sistema, que tem o módulo do Mininet:

    sudo python3 scripts/emular_trecho.py --modelo random-forest --trecho dev --carga 1 2
    sudo python3 scripts/emular_trecho.py --modelo random-forest xgboost --trecho campanha \\
        --estrategia sem-xai sincrono-total sincrono-condicional assincrono --criterio probabilidade --carga 4

Cada combinação de modelo, estratégia, critério e carga é um ensaio, executado em sequência, cada um com a sua
rede. O critério só se aplica ao sincrono-condicional. A carga é o número de cópias do trecho enviadas ao mesmo
tempo, e o padrão é 1.

Topologia: dois hosts em enlace direto, sem switch. h1 envia as cópias do trecho na velocidade original. h2
executa o NIDS, que captura a interface em modo promíscuo. A cópia 1 é o trecho sem alteração. Cada cópia seguinte
troca os endereços IPv4 do trecho pelos do seu bloco (src/core/traffic_copies.py). Cada cópia é um processo do
tcpreplay-edit, fixo numa das CPUs de reprodução da configuração do NIDS. Depois do último pacote, o script espera
o tempo limite dos fluxos e a margem do relógio ocioso, para a varredura emitir os últimos fluxos, e então encerra
o NIDS. No modo assíncrono, o NIDS ainda espera a fila de explicações pendentes esvaziar.

Antes de cada ensaio, o script confere se a máquina está na tomada, ociosa e com memória disponível, e espera até
o tempo máximo. Sem isso, o ensaio não começa e fica registrado como não iniciado. Durante o ensaio, uma thread grava
o estado da máquina a cada segundo. O registro da reprodução vai para replay.json, e as leituras da máquina, para
machine.jsonl, na pasta da execução do NIDS.

O progresso de cada etapa e os relatórios da cópia 1 do tcpreplay, a cada 60 s, saem no stderr. O stdout recebe uma
linha JSON por ensaio, com a pasta da execução.
"""

import argparse
import hashlib
import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
# O script roda como root. Sem cache de bytecode, nenhum arquivo do root fica nas pastas do projeto.
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))

from core.machine_sampler import MachineSampler, wait_until_ready  # noqa: E402
from core.traffic_copies import MAX_COPIES, argument_digest, check_addresses, pnat_argument  # noqa: E402

VENV_PYTHON = SOURCE / "venv" / "bin" / "python"
TCPREPLAY_BUILD = ROOT / "tcpreplay" / "build"
TCPREPLAY = "tcpreplay-edit"
# Antes da 4.6.0, o tcpreplay não envia pelo anel de transmissão os quadros acima de 4.064 bytes.
TCPREPLAY_MINIMUM = (4, 6, 0)
FLOW_TIMEOUT_S = 120
SETTLE_S = 15
STATS_INTERVAL_S = 60
# Antes de sair, o extrator entrega os fluxos que restam na fila de saída, no ritmo do classificador, e é encerrado se
# ficar 30 s sem entregar um. O caminho mais lento, o Random Forest no Síncrono total, atende cerca de 84 fluxos por
# segundo, e o prazo reserva o tempo de entregar a fila cheia a 50 fluxos por segundo. O processo explicador tem o
# tempo máximo de esvaziamento da configuração. Os 180 s restantes cobrem o fechamento dos arquivos, as verificações e
# a gravação do relatório. Cada cópia acrescenta 60 s, porque as verificações crescem com o número de fluxos.
EXTRACTOR_STOP_S = 30
SLOWEST_DELIVERY_PER_S = 50
REPORT_S = 180
REPORT_PER_COPY_S = 60
STRATEGIES = ("sem-xai", "sincrono-total", "sincrono-condicional", "assincrono")
CRITERIA = ("probabilidade", "incerteza")
COUNTERS = ("rx_packets", "rx_bytes", "rx_dropped", "tx_packets", "tx_bytes", "tx_dropped")
OFFLOADS = ("rx", "tx", "sg", "tso", "gso", "gro", "lro")
# Condições da máquina antes de cada ensaio, quando quem chama não informa outras.
MACHINE = {"require_mains": True, "max_busy_share": 0.25, "min_available_mib": 3072, "window_s": 10.0,
           "max_wait_s": 600.0}
# Campos do tcpreplay somados entre as cópias. As taxas somadas são as do envio de todas as cópias juntas.
SUMMARY_FIELDS = ("attempted_packets", "attempted_bytes", "successful", "failed", "truncated", "retried_enobufs",
                  "retried_eagain", "rated_bytes_per_second", "rated_mbps", "rated_packets_per_second")


@dataclass(frozen=True)
class Context:
    """O que todos os ensaios de um trecho usam: configuração do NIDS, trecho conferido, endereços e tcpreplay."""
    nids_config: dict
    segment_name: str
    segment: dict
    pcap: Path
    addresses: list[str]
    replay_tool: dict
    owner: tuple[int, int]


def main() -> int:
    arguments = parse_arguments()
    owner = sudo_owner()
    if owner is None:
        return 2
    try:
        context = load_context(arguments.trecho, owner)
    except (OSError, ValueError, KeyError) as error:
        print(f"Não foi possível preparar a reprodução: {error}", file=sys.stderr)
        return 1
    trials = [(model, strategy, criterion, copies)
              for model, strategy, copies in itertools.product(arguments.modelo, arguments.estrategia, arguments.carga)
              for criterion in (arguments.criterio if strategy == "sincrono-condicional" else [None])]
    replay_s = (context.segment["summary"]["last_packet_us"] - context.segment["summary"]["first_packet_us"]) / 1e6
    wait_s = FLOW_TIMEOUT_S + context.nids_config["extractor"]["idle-margin-us"] / 1e6 + SETTLE_S
    log(f"Trecho {arguments.trecho} conferido: {context.segment['summary']['packets']} pacotes, cerca de "
        f"{replay_s / 60:.1f} min de tráfego. {len(trials)} ensaios, cerca de "
        f"{len(trials) * (replay_s + wait_s) / 60:.0f} min no total. tcpreplay {context.replay_tool['version']}.")
    failures = 0
    for number, (model, strategy, criterion, copies) in enumerate(trials, start=1):
        log(f"Ensaio {number} de {len(trials)}: {model}, {strategy}" + (f", {criterion}" if criterion else "")
            + f", {copies} cópia(s).")
        result = run_trial_safely(context, model, strategy, criterion, copies)
        failures += result["exit_code"] != 0
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if failures == 0 else 1


def sudo_owner() -> tuple[int, int] | None:
    if os.geteuid() != 0 or "SUDO_UID" not in os.environ:
        print("Execute com sudo, a partir do usuário que vai ficar dono dos arquivos.", file=sys.stderr)
        return None
    return int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])


def load_context(segment_name: str, owner: tuple[int, int]) -> Context:
    """Confere o tcpreplay, o trecho e a lista de endereços uma vez para todos os ensaios."""
    replay_tool = check_tcpreplay()
    nids_config = json.loads((ROOT / "configs" / "nids.json").read_text(encoding="utf-8"))
    found = []
    for path in nids_config["preparation_manifests"]:
        manifest = json.loads((ROOT / path).read_text(encoding="utf-8"))
        if segment_name in manifest["segments"]:
            found.append(manifest["segments"][segment_name])
    if len(found) != 1:
        raise ValueError(f"trecho {segment_name} ausente ou repetido nos manifestos da preparação.")
    segment = found[0]
    pcap = ROOT / segment["pcap"]["file"]
    if sha256(pcap) != segment["pcap"]["sha256"]:
        raise ValueError(f"o trecho {pcap} difere do manifesto da preparação.")
    addresses: list[str] = []
    if "addresses" in segment:
        path = ROOT / segment["addresses"]["file"]
        if sha256(path) != segment["addresses"]["sha256"]:
            raise ValueError(f"a lista de endereços {path} difere do manifesto da preparação.")
        addresses = [address for address, _ in json.loads(path.read_text(encoding="utf-8"))]
        check_addresses(addresses)
    return Context(nids_config, segment_name, segment, pcap, addresses, replay_tool, owner)


def run_trial_safely(context: Context, model: str, strategy: str, criterion: str | None, copies: int,
                     machine: dict | None = None, cell: dict | None = None) -> dict:
    """Um ensaio que falha não interrompe os seguintes. A falha fica no resultado."""
    try:
        return run_trial(context, model, strategy, criterion, copies, machine or MACHINE, cell)
    except Exception as error:  # noqa: BLE001
        log(f"O ensaio falhou: {error}")
        return {"model": model, "strategy": strategy, "criterion": criterion, "copies": copies, "started": True,
                "error": str(error), "exit_code": 1}


def run_trial(context: Context, model: str, strategy: str, criterion: str | None, copies: int,
              machine: dict, cell: dict | None = None) -> dict:
    """Um ensaio: confere a máquina, cria a rede, inicia o NIDS em h2, envia as cópias em h1 e grava os registros."""
    if not 1 <= copies <= MAX_COPIES or (copies > 1 and not context.addresses):
        raise ValueError(f"{copies} cópias não são possíveis no trecho {context.segment_name}.")
    nids_config, segment = context.nids_config, context.segment
    readiness = wait_until_ready(machine, log)
    if not readiness["ready"]:
        log("A máquina não ficou pronta: " + "; ".join(readiness["reasons"]) + ". O ensaio não começa.")
        return {"model": model, "strategy": strategy, "criterion": criterion, "copies": copies, "started": False,
                "readiness": readiness, "exit_code": 1}
    mtu = max(1500, min(65535, segment["summary"]["max_frame_bytes"] - 14))
    wait_s = FLOW_TIMEOUT_S + nids_config["extractor"]["idle-margin-us"] / 1e6 + SETTLE_S
    replay_cpus = nids_config["resources"]["cpus"]["replay"]
    queue_delivery_s = nids_config["extractor"]["flow-queue-limit"] // SLOWEST_DELIVERY_PER_S
    nids_stop_timeout_s = (EXTRACTOR_STOP_S + queue_delivery_s + nids_config["explanation_queue"]["drain_timeout_s"]
                           + REPORT_S + REPORT_PER_COPY_S * copies)

    from mininet.log import setLogLevel
    from mininet.net import Mininet

    setLogLevel("warning")
    network = Mininet(controller=None, build=False, autoSetMacs=True)
    sender = network.addHost("h1", ip="10.255.0.1/30")
    receiver = network.addHost("h2", ip="10.255.0.2/30")
    network.addLink(sender, receiver)
    network.build()
    log("Rede emulada criada: h1-eth0 <-> h2-eth0.")
    record: dict = {"stage": "segment replay", "model": model, "strategy": strategy, "criterion": criterion,
                    "copies": copies, "segment": context.segment_name, "pcap": segment["pcap"],
                    "segment_packets": segment["summary"]["packets"], "addresses": segment.get("addresses"),
                    "topology": {"hosts": ["h1", "h2"], "link": "h1-eth0 <-> h2-eth0, enlace direto (veth)",
                                 "switch": None, "mtu": mtu, "ipv6": "desativado"},
                    "wait_after_replay_s": wait_s, "tcpreplay_build": context.replay_tool, "replay_cpus": replay_cpus,
                    "nids_stop_timeout_s": nids_stop_timeout_s, "readiness": readiness, "git": git_state(),
                    "cell": cell}
    nids = sampler = None
    run_dir = None
    temporary = {name: Path(f"/tmp/nids-{os.getpid()}.{name}") for name in ("out", "err", "machine")}
    try:
        interfaces = {}
        for host, interface in ((sender, "h1-eth0"), (receiver, "h2-eth0")):
            host.cmd("sysctl -qw net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1")
            host.cmd(f"ip link set dev {interface} mtu {mtu}")
            host.cmd(f"ethtool -K {interface} " + " ".join(f"{name} off" for name in OFFLOADS) + " 2>/dev/null")
            interfaces[interface] = {"offloads": host.cmd(f"ethtool -k {interface}").strip().splitlines(),
                                     "link": host.cmd(f"ip -d link show {interface}").strip()}
        record["interfaces"] = interfaces
        ready = Path(f"/tmp/nids-pronto-{os.getpid()}.json")
        ready.unlink(missing_ok=True)
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        command = [str(VENV_PYTHON), "main.py", "nids-executar", "--modelo", model, "--estrategia", strategy,
                   *(["--criterio", criterion] if criterion else []),
                   "--trecho", context.segment_name, "--interface", "h2-eth0", "--sinal-pronto", str(ready)]
        record["nids_command"] = command
        log(f"Iniciando o NIDS em h2, com o {model}.")
        # A saída do NIDS vai para arquivos: um pipe lido só no fim poderia encher e travar a captura.
        with temporary["out"].open("w") as out, temporary["err"].open("w") as err:
            nids = receiver.popen(command, cwd=str(SOURCE), env=environment, stdout=out, stderr=err, text=True)
        deadline = time.monotonic() + 180
        while not ready.exists():
            if nids.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("O NIDS não abriu a captura: " + temporary["err"].read_text()[-2000:])
            time.sleep(0.2)
        run_dir = Path(json.loads(ready.read_text())["run_dir"])
        ready.unlink()
        log(f"NIDS pronto, capturando h2-eth0. Execução: {run_dir}")
        # O amostrador divide a última CPU de reprodução com as cópias. Ele faz uma leitura por segundo.
        sampler = MachineSampler(temporary["machine"], [replay_cpus[-1]])
        sampler.start()
        before = {"h1-eth0": counters(sender, "h1-eth0"), "h2-eth0": counters(receiver, "h2-eth0")}
        record["replay_started_utc"] = datetime.now(timezone.utc).isoformat()
        log(f"Reprodução de {copies} cópia(s) iniciada em h1, nas CPUs {', '.join(map(str, replay_cpus))}. A cópia 1 "
            f"informa o progresso a cada {STATS_INTERVAL_S} s.")
        started = time.monotonic()
        replays = send_copies(context, sender, copies, replay_cpus)
        record["replay_seconds"] = time.monotonic() - started
        record["replay_finished_utc"] = datetime.now(timezone.utc).isoformat()
        record["replay_commands"] = [item.pop("command") for item in replays]
        record["replay_command"] = record["replay_commands"][0]
        record["tcpreplay"] = {"exit_code": max(item["exit_code"] for item in replays),
                               **{field: _sum(item.get(field) for item in replays) for field in SUMMARY_FIELDS},
                               "copies": replays}
        log(f"Reprodução concluída em {record['replay_seconds']:.0f} s (códigos "
            f"{sorted({item['exit_code'] for item in replays})}).")
        log(f"Aguardando {wait_s:.0f} s para a varredura emitir os últimos fluxos.")
        deadline = time.monotonic() + wait_s
        while (remaining := deadline - time.monotonic()) > 0:
            time.sleep(min(30.0, remaining))
            if deadline - time.monotonic() > 1:
                log(f"Faltam {deadline - time.monotonic():.0f} s de espera.")
        after = {"h1-eth0": counters(sender, "h1-eth0"), "h2-eth0": counters(receiver, "h2-eth0")}
        record["interface_counters"] = {name: {key: after[name][key] - before[name][key] for key in COUNTERS}
                                        for name in after}
        log("Encerrando o NIDS." + (" O NIDS espera a fila de explicações pendentes esvaziar."
                                    if strategy == "assincrono" else ""))
        nids.send_signal(signal.SIGTERM)
        try:
            nids.wait(timeout=nids_stop_timeout_s)
        except subprocess.TimeoutExpired:
            log(f"O NIDS não encerrou em {nids_stop_timeout_s} s e será encerrado à força.")
            nids.kill()
            nids.wait()
            record["nids_stop_timeout"] = True
        log(f"NIDS encerrado (código {nids.returncode}).")
        record["nids"] = {"exit_code": nids.returncode,
                          "output": temporary["out"].read_text().strip().splitlines(),
                          "errors": temporary["err"].read_text().strip().splitlines()[-20:]}
        nids_report = run_dir / "report.json"
        if nids_report.is_file():
            capture = json.loads(nids_report.read_text(encoding="utf-8"))["extractor_end"]
            record["delivered"] = {"libpcap": capture.get("pcap_stats"), "flows_emitted": capture["flows_emitted"],
                                   "flows_per_second": capture["flows_emitted"] / record["replay_seconds"]}
    finally:
        if nids is not None and nids.poll() is None:
            nids.kill()
        if sampler is not None:
            record["machine"] = sampler.stop()
        network.stop()
        if run_dir is not None and run_dir.is_dir():
            if temporary["machine"].exists():
                shutil.move(str(temporary["machine"]), run_dir / "machine.jsonl")
                record["machine"]["file"] = "machine.jsonl"
            (run_dir / "replay.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")
            give_back(run_dir, context.owner)
            for parent in (run_dir.parent, run_dir.parent.parent):
                if parent.stat().st_uid == 0:
                    os.chown(parent, *context.owner)
            for report in (ROOT / "relatorios").glob(f"nids-execucao-interface-{run_dir.name}.md"):
                os.chown(report, *context.owner)
            log(f"Registro gravado em {run_dir / 'replay.json'}.")
        for path in temporary.values():
            path.unlink(missing_ok=True)
    succeeded = record.get("nids", {}).get("exit_code") == 0 and not record.get("nids_stop_timeout")
    return {"model": model, "strategy": strategy, "criterion": criterion, "copies": copies, "started": True,
            "run_dir": str(run_dir), "nids_exit_code": record.get("nids", {}).get("exit_code"),
            "tcpreplay": {key: record.get("tcpreplay", {}).get(key) for key in ("successful", "failed")},
            "exit_code": 0 if succeeded else 1}


def send_copies(context: Context, sender, copies: int, replay_cpus: list[int]) -> list[dict]:
    """Inicia todas as cópias, cada uma fixa numa CPU de reprodução pelo taskset, e espera todas terminarem."""
    binary = TCPREPLAY_BUILD / TCPREPLAY
    launched = []
    for copy in range(1, copies + 1):
        pnat = pnat_argument(context.addresses, copy) if copy > 1 else None
        cpu = replay_cpus[(copy - 1) % len(replay_cpus)]
        command = [str(binary), "--intf1=h1-eth0", "--multiplier=1", "--no-flow-stats",
                   f"--stats={STATS_INTERVAL_S}", *([pnat] if pnat else []), str(context.pcap)]
        process = sender.popen(["taskset", "-c", str(cpu), *command], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
        lines: list[str] = []
        reader = threading.Thread(target=_read_output, args=(process, lines, copy == 1), daemon=True)
        reader.start()
        shown = [part if not part.startswith("--pnat=") else "--pnat=<pares da cópia>" for part in command]
        launched.append({"copy": copy, "cpu": cpu, "started_monotonic_ns": time.monotonic_ns(), "process": process,
                         "reader": reader, "lines": lines, "pnat_pairs": len(context.addresses) if pnat else 0,
                         "pnat_sha256": argument_digest(pnat), "command": shown})
    results = []
    for item in launched:
        item["process"].wait()
        item["reader"].join()
        output = "\n".join(item["lines"])
        results.append({"copy": item["copy"], "cpu": item["cpu"], "exit_code": item["process"].returncode,
                        "started_monotonic_ns": item["started_monotonic_ns"], "pnat_pairs": item["pnat_pairs"],
                        "pnat_sha256": item["pnat_sha256"], "command": item["command"],
                        **parse_tcpreplay(output), "output": item["lines"]})
    return results


def _read_output(process, lines: list[str], show: bool) -> None:
    for line in process.stdout:
        lines.append(line.rstrip("\n"))
        if show and line.strip():
            log("tcpreplay: " + line.strip())


def _sum(values) -> int | float | None:
    values = list(values)
    return None if any(value is None for value in values) else sum(values)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", choices=("random-forest", "xgboost"), nargs="+", required=True)
    parser.add_argument("--trecho", required=True)
    parser.add_argument("--estrategia", choices=STRATEGIES, nargs="+", default=["sem-xai"])
    parser.add_argument("--criterio", choices=CRITERIA, nargs="+", default=[],
                        help="Critérios do sincrono-condicional, com os limiares fixados na configuração do NIDS.")
    parser.add_argument("--carga", type=int, nargs="+", default=[1],
                        help="Números de cópias do trecho enviadas ao mesmo tempo. O padrão é 1.")
    arguments = parser.parse_args()
    if ("sincrono-condicional" in arguments.estrategia) != bool(arguments.criterio):
        parser.error("--criterio é obrigatório com sincrono-condicional e só se aplica a ele.")
    if any(not 1 <= copies <= MAX_COPIES for copies in arguments.carga):
        parser.error(f"--carga deve ficar entre 1 e {MAX_COPIES}.")
    return arguments


def check_tcpreplay() -> dict:
    """Confere os binários compilados por tcpreplay/build.sh com o registro da compilação e exige a versão mínima."""
    build_record = TCPREPLAY_BUILD / "tcpreplay-build.json"
    if not build_record.is_file():
        raise ValueError("compile o tcpreplay com tcpreplay/build.sh.")
    build = json.loads(build_record.read_text(encoding="utf-8"))
    binary = TCPREPLAY_BUILD / TCPREPLAY
    if TCPREPLAY not in build.get("binaries", {}) or not binary.is_file():
        raise ValueError(f"o {TCPREPLAY} não está na compilação. Recompile com tcpreplay/build.sh.")
    if sha256(binary) != build["binaries"][TCPREPLAY]["sha256"]:
        raise ValueError(f"{binary} difere do registro da compilação.")
    reported = subprocess.run([str(binary), "--version"], capture_output=True, text=True)
    output = reported.stdout + reported.stderr
    match = re.search(r"version: (\d+)\.(\d+)\.(\d+)", output)
    if match is None:
        raise ValueError(f"{binary} não informou a versão.")
    version = tuple(int(part) for part in match.groups())
    if version < TCPREPLAY_MINIMUM:
        raise ValueError(f"a versão {'.'.join(map(str, version))} é anterior à "
                         f"{'.'.join(map(str, TCPREPLAY_MINIMUM))}.")
    if "Packet editing: enabled" not in output:
        raise ValueError(f"{binary} foi compilado sem a edição de pacotes.")
    return {"version": ".".join(map(str, version)), "binary": str(binary.relative_to(ROOT)),
            "binary_sha256": build["binaries"][TCPREPLAY]["sha256"], "archive": build["archive"]}


def git_state() -> dict:
    """Commit do repositório e arquivos versionados com alterações, no início do ensaio."""
    def git(*arguments: str) -> str:
        result = subprocess.run(["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT), *arguments],
                                capture_output=True, text=True)
        return result.stdout.strip()

    return {"commit": git("rev-parse", "HEAD"),
            "modified_tracked_files": git("status", "--porcelain", "--untracked-files=no").splitlines()}


def counters(host, interface: str) -> dict[str, int]:
    """Contadores da interface, lidos por netlink dentro do namespace do host."""
    stats = json.loads(host.cmd(f"ip -s -j link show dev {interface}"))[0]["stats64"]
    return {f"{direction}_{name}": int(stats[direction][name])
            for direction in ("rx", "tx") for name in ("packets", "bytes", "dropped")}


def parse_tcpreplay(output: str) -> dict[str, float | int | None]:
    patterns = {
        "attempted_packets": r"Actual: (\d+) packets", "attempted_bytes": r"Actual: \d+ packets \((\d+) bytes\)",
        "seconds": r"sent in ([\d.]+) seconds", "rated_bytes_per_second": r"Rated: ([\d.]+) Bps",
        "rated_mbps": r"Rated: [\d.]+ Bps, ([\d.]+) Mbps", "rated_packets_per_second": r"Mbps, ([\d.]+) pps",
        "successful": r"Successful packets:\s+(\d+)", "failed": r"Failed packets:\s+(\d+)",
        "truncated": r"Truncated packets:\s+(\d+)", "retried_enobufs": r"Retried packets \(ENOBUFS\):\s+(\d+)",
        "retried_eagain": r"Retried packets \(EAGAIN\):\s+(\d+)",
    }
    result: dict[str, float | int | None] = {}
    for name, pattern in patterns.items():
        # Com --stats, os relatórios periódicos repetem os campos; o resumo final é a última ocorrência.
        matches = re.findall(pattern, output)
        value = matches[-1] if matches else None
        result[name] = None if value is None else (float(value) if "." in value else int(value))
    return result


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def give_back(path: Path, owner: tuple[int, int]) -> None:
    for item in [path, *path.rglob("*")]:
        os.chown(item, *owner)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    sys.exit(main())
