#!/usr/bin/env bash
# Compila o tcpreplay usado na reprodução do tráfego, a partir do pacote oficial da versão fixada pela decisão 10.
#   build/tcpreplay-edit: binário chamado por scripts/emular_trecho.py, que reescreve os endereços de cada cópia.
#   build/tcpreplay e build/tcprewrite: o mesmo envio sem edição e a mesma reescrita gravada em arquivo.
# Nada é instalado no sistema. Requer curl, gcc, make e o pacote de desenvolvimento da libpcap (libpcap-dev).
set -euo pipefail

VERSION=4.6.2
SHA256=83a7ca2f9daa367949926cfe34d30193e756c233c164b38f84f0d6d272a87e66
ARCHIVE="tcpreplay-$VERSION.tar.xz"
URL="https://github.com/appneta/tcpreplay/releases/download/v$VERSION/$ARCHIVE"
HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$HERE/build"
CONFIGURE_OPTIONS=(--disable-shared)

if ! echo '#include <pcap.h>' | cc -E - > /dev/null 2>&1; then
    echo "Cabeçalhos da libpcap não encontrados. Instale o pacote libpcap-dev." >&2
    exit 1
fi

mkdir -p "$BUILD"
if [ ! -f "$BUILD/$ARCHIVE" ]; then
    curl -fsSL -o "$BUILD/$ARCHIVE.part" "$URL"
    mv "$BUILD/$ARCHIVE.part" "$BUILD/$ARCHIVE"
fi
if [ "$(sha256sum "$BUILD/$ARCHIVE" | cut -d' ' -f1)" != "$SHA256" ]; then
    echo "O pacote $BUILD/$ARCHIVE difere do SHA-256 fixado." >&2
    exit 1
fi

rm -rf "$BUILD/source" "$BUILD/objects" "$BUILD/tcpreplay" "$BUILD/tcpreplay-edit" "$BUILD/tcprewrite" \
    "$BUILD/tcpreplay-build.json"
mkdir -p "$BUILD/source" "$BUILD/objects"
tar -xJf "$BUILD/$ARCHIVE" -C "$BUILD/source" --strip-components=1
cd "$BUILD/objects"
if ! "$BUILD/source/configure" "${CONFIGURE_OPTIONS[@]}" > "$BUILD/configure.log" 2>&1; then
    tail -n 20 "$BUILD/configure.log" >&2
    exit 1
fi
if ! make -j"$(nproc)" > "$BUILD/make.log" 2>&1; then
    tail -n 20 "$BUILD/make.log" >&2
    exit 1
fi
cp src/tcpreplay src/tcpreplay-edit src/tcprewrite "$BUILD/"

python3 - "$BUILD" "$VERSION" "$URL" "$SHA256" "${CONFIGURE_OPTIONS[@]}" <<'PYTHON'
import hashlib, json, pathlib, re, subprocess, sys

build, version, url, archive_sha256, options = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
binaries, outputs = {}, {}
for name in ("tcpreplay", "tcpreplay-edit", "tcprewrite"):
    binary = build / name
    reported = subprocess.run([str(binary), "--version"], capture_output=True, text=True)
    lines = (reported.stdout + reported.stderr).splitlines()
    match = re.search(r"version: (\S+)", "\n".join(lines))
    if match is None or match.group(1) != version:
        sys.exit(f"O binário {name} não informa a versão {version}.")
    binaries[name] = {"file": name, "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    outputs[name] = [line for line in lines if line.strip() and not line.startswith("Warning")]
if "Packet editing: enabled" not in outputs["tcpreplay-edit"]:
    sys.exit("O tcpreplay-edit foi compilado sem a edição de pacotes.")
record = {
    "version": version,
    "archive": {"url": url, "sha256": archive_sha256},
    "configure_options": options,
    "compiler": subprocess.run(["cc", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
    "binary": binaries["tcpreplay"],
    "binaries": binaries,
    "version_output": outputs["tcpreplay"],
    "version_outputs": outputs,
}
(build / "tcpreplay-build.json").write_text(json.dumps(record, indent=2) + "\n")
PYTHON
echo "tcpreplay $VERSION compilado em $BUILD."
