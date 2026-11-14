#!/usr/bin/env python3
"""Reproduz um trecho de PCAP em rede emulada pelo Mininet e captura o tráfego com o NIDS de referência.

Executar com sudo e o Python do sistema, que tem o módulo do Mininet:

    sudo python3 scripts/emular_baixa_carga.py --modelo random-forest --trecho validacao

Topologia: dois hosts em enlace direto, sem switch. h1 envia o trecho com o tcpreplay na velocidade original.
h2 executa o NIDS, que captura a interface em modo promíscuo. Depois do último pacote, o script espera o tempo
limite dos fluxos e a margem do relógio ocioso, para a varredura emitir os últimos fluxos, e então encerra o NIDS.
O registro da reprodução vai para replay.json, na pasta da execução do NIDS.

O progresso de cada etapa e os relatórios do tcpreplay, a cada 60 s, saem no stderr. O stdout recebe só a linha
JSON final, com a pasta da execução.
"""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
VENV_PYTHON = SOURCE / "venv" / "bin" / "python"
TCPREPLAY_BUILD = ROOT / "tcpreplay" / "build"
# Antes da 4.6.0, o tcpreplay não envia pelo anel de transmissão os quadros acima de 4.064 bytes.
TCPREPLAY_MINIMUM = (4, 6, 0)
FLOW_TIMEOUT_S = 120
SETTLE_S = 15
STATS_INTERVAL_S = 60
# O extrator tem 30 s para parar. O restante cobre o fechamento dos arquivos e a gravação do relatório.
NIDS_STOP_TIMEOUT_S = 180
COUNTERS = ("rx_packets", "rx_bytes", "rx_dropped", "tx_packets", "tx_bytes", "tx_dropped")
OFFLOADS = ("rx", "tx", "sg", "tso", "gso", "gro", "lro")


def main() -> int:
    arguments = parse_arguments()
    if os.geteuid() != 0 or "SUDO_UID" not in os.environ:
        print("Execute com sudo, a partir do usuário que vai ficar dono dos arquivos.", file=sys.stderr)
        return 2
    owner = (int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
    try:
        replay_tool = check_tcpreplay()
    except (OSError, ValueError, KeyError) as error:
        print(f"tcpreplay indisponível: {error}", file=sys.stderr)
        return 1
    nids_config = json.loads((ROOT / "configs" / "nids.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / nids_config["preparation_manifest"]).read_text(encoding="utf-8"))
    segment = manifest["segments"][arguments.trecho]
    pcap = ROOT / segment["pcap"]["file"]
    if sha256(pcap) != segment["pcap"]["sha256"]:
        print(f"O trecho {pcap} difere do manifesto da preparação.", file=sys.stderr)
        return 1
    mtu = max(1500, min(65535, segment["summary"]["max_frame_bytes"] - 14))
    idle_margin_s = nids_config["extractor"]["idle-margin-us"] / 1e6
    wait_s = FLOW_TIMEOUT_S + idle_margin_s + SETTLE_S
    replay_s = (segment["summary"]["last_packet_us"] - segment["summary"]["first_packet_us"]) / 1e6
    log(f"Trecho {arguments.trecho} conferido: {segment['summary']['packets']} pacotes, cerca de {replay_s / 60:.1f} min "
        f"de tráfego. Duração prevista do ensaio: {(replay_s + wait_s) / 60:.0f} min. MTU: {mtu} bytes. "
        f"tcpreplay {replay_tool['version']}.")

    from mininet.log import setLogLevel
    from mininet.net import Mininet

    setLogLevel("warning")
    network = Mininet(controller=None, build=False, autoSetMacs=True)
    sender = network.addHost("h1", ip="10.255.0.1/30")
    receiver = network.addHost("h2", ip="10.255.0.2/30")
    network.addLink(sender, receiver)
    network.build()
    log("Rede emulada criada: h1-eth0 <-> h2-eth0.")
    record: dict = {"stage": "low-load replay", "model": arguments.modelo, "segment": arguments.trecho,
                    "pcap": segment["pcap"], "segment_packets": segment["summary"]["packets"],
                    "topology": {"hosts": ["h1", "h2"], "link": "h1-eth0 <-> h2-eth0, enlace direto (veth)",
                                 "switch": None, "mtu": mtu, "ipv6": "desativado"},
                    "wait_after_replay_s": wait_s, "tcpreplay_build": replay_tool}
    nids = None
    run_dir = None
    nids_log: dict[str, Path] = {}
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
        command = [str(VENV_PYTHON), "main.py", "nids-executar", "--modelo", arguments.modelo,
                   "--trecho", arguments.trecho, "--interface", "h2-eth0", "--sinal-pronto", str(ready)]
        record["nids_command"] = command
        log(f"Iniciando o NIDS em h2, com o {arguments.modelo}.")
        # A saída do NIDS vai para arquivos: um pipe lido só no fim poderia encher e travar a captura.
        nids_log = {"stdout": Path(f"/tmp/nids-{os.getpid()}.out"), "stderr": Path(f"/tmp/nids-{os.getpid()}.err")}
        with nids_log["stdout"].open("w") as out, nids_log["stderr"].open("w") as err:
            nids = receiver.popen(command, cwd=str(SOURCE), env=environment, stdout=out, stderr=err, text=True)
        deadline = time.monotonic() + 180
        while not ready.exists():
            if nids.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("O NIDS não abriu a captura: " + nids_log["stderr"].read_text()[-2000:])
            time.sleep(0.2)
        run_dir = Path(json.loads(ready.read_text())["run_dir"])
        ready.unlink()
        log(f"NIDS pronto, capturando h2-eth0. Execução: {run_dir}")
        before = {"h1-eth0": counters(sender, "h1-eth0"), "h2-eth0": counters(receiver, "h2-eth0")}
        replay_command = [str(TCPREPLAY_BUILD / "tcpreplay"), "--intf1=h1-eth0", "--multiplier=1", f"--stats={STATS_INTERVAL_S}", str(pcap)]
        record["replay_command"] = replay_command
        record["replay_started_utc"] = datetime.now(timezone.utc).isoformat()
        log(f"Reprodução iniciada em h1. O tcpreplay informa o progresso a cada {STATS_INTERVAL_S} s.")
        started = time.monotonic()
        replay = sender.popen(replay_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = []
        for line in replay.stdout:
            lines.append(line.rstrip("\n"))
            if line.strip():
                log("tcpreplay: " + line.strip())
        replay.wait()
        output = "\n".join(lines)
        record["replay_seconds"] = time.monotonic() - started
        record["replay_finished_utc"] = datetime.now(timezone.utc).isoformat()
        record["tcpreplay"] = {"exit_code": replay.returncode, "output": lines, **parse_tcpreplay(output)}
        log(f"Reprodução concluída em {record['replay_seconds']:.0f} s (código {replay.returncode}).")
        log(f"Aguardando {wait_s:.0f} s para a varredura emitir os últimos fluxos.")
        deadline = time.monotonic() + wait_s
        while (remaining := deadline - time.monotonic()) > 0:
            time.sleep(min(30.0, remaining))
            if deadline - time.monotonic() > 1:
                log(f"Faltam {deadline - time.monotonic():.0f} s de espera.")
        after = {"h1-eth0": counters(sender, "h1-eth0"), "h2-eth0": counters(receiver, "h2-eth0")}
        record["interface_counters"] = {name: {key: after[name][key] - before[name][key] for key in COUNTERS}
                                        for name in after}
        log("Encerrando o NIDS.")
        nids.send_signal(signal.SIGTERM)
        try:
            nids.wait(timeout=NIDS_STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            log(f"O NIDS não encerrou em {NIDS_STOP_TIMEOUT_S} s e será encerrado à força.")
            nids.kill()
            nids.wait()
            record["nids_stop_timeout"] = True
        log(f"NIDS encerrado (código {nids.returncode}).")
        record["nids"] = {"exit_code": nids.returncode,
                          "output": nids_log["stdout"].read_text().strip().splitlines(),
                          "errors": nids_log["stderr"].read_text().strip().splitlines()[-20:]}
        nids_report = run_dir / "report.json"
        if nids_report.is_file():
            capture = json.loads(nids_report.read_text(encoding="utf-8"))["extractor_end"]
            record["delivered"] = {"libpcap": capture.get("pcap_stats"), "flows_emitted": capture["flows_emitted"],
                                   "flows_per_second": capture["flows_emitted"] / record["replay_seconds"]}
    finally:
        if nids is not None and nids.poll() is None:
            nids.kill()
        network.stop()
        for path in nids_log.values():
            path.unlink(missing_ok=True)
        if run_dir is not None and run_dir.is_dir():
            (run_dir / "replay.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")
            give_back(run_dir, owner)
            for parent in (run_dir.parent, run_dir.parent.parent):
                if parent.stat().st_uid == 0:
                    os.chown(parent, *owner)
            for report in (ROOT / "relatorios").glob(f"nids-execucao-interface-{run_dir.name}.md"):
                os.chown(report, *owner)
            log(f"Registro gravado em {run_dir / 'replay.json'}.")
    print(json.dumps({"run_dir": str(run_dir), "nids_exit_code": record.get("nids", {}).get("exit_code"),
                      "tcpreplay": {key: record.get("tcpreplay", {}).get(key) for key in ("successful", "failed")}},
                     ensure_ascii=False))
    return 0 if record.get("nids", {}).get("exit_code") == 0 and not record.get("nids_stop_timeout") else 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", choices=("random-forest", "xgboost"), required=True)
    parser.add_argument("--trecho", required=True)
    return parser.parse_args()


def check_tcpreplay() -> dict[str, str]:
    """Confere o binário compilado por tcpreplay/build.sh com o registro da compilação e exige a versão mínima."""
    binary, build_record = TCPREPLAY_BUILD / "tcpreplay", TCPREPLAY_BUILD / "tcpreplay-build.json"
    if not binary.is_file() or not build_record.is_file():
        raise ValueError("compile-o com tcpreplay/build.sh.")
    build = json.loads(build_record.read_text(encoding="utf-8"))
    if sha256(binary) != build["binary"]["sha256"]:
        raise ValueError(f"{binary} difere do registro da compilação.")
    reported = subprocess.run([str(binary), "--version"], capture_output=True, text=True)
    match = re.search(r"tcpreplay version: (\d+)\.(\d+)\.(\d+)", reported.stdout + reported.stderr)
    if match is None:
        raise ValueError(f"{binary} não informou a versão.")
    version = tuple(int(part) for part in match.groups())
    if version < TCPREPLAY_MINIMUM:
        raise ValueError(f"a versão {'.'.join(map(str, version))} é anterior à "
                         f"{'.'.join(map(str, TCPREPLAY_MINIMUM))}.")
    return {"version": ".".join(map(str, version)), "binary": str(binary.relative_to(ROOT)),
            "binary_sha256": build["binary"]["sha256"], "archive": build["archive"]}


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
