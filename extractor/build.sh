#!/usr/bin/env bash
# Compila os dois programas do extrator a partir do CICFlowMeter corrigido no commit fixado pela decisão 3.
#   build/reference-extractor.jar: classes originais, sem alteração, com o ReferenceExtractor.
#   build/nids-extractor.jar: classes com os patches de patches/, com o NidsExtractor.
# Requer git, Maven, um JDK 8 ou mais novo e a libpcap do sistema.
set -euo pipefail

COMMIT=13a061520b862d605eea746c79ca4033b30d98fc
REPOSITORY=https://github.com/GintsEngelen/CICFlowMeter.git
HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$HERE/build"
UPSTREAM="$BUILD/upstream"
PACKAGE=src/main/java/cic/cs/unb/ca/jnetpcap
JNETPCAP=jnetpcap/linux/jnetpcap-1.4.r1425

mkdir -p "$BUILD"
if [ ! -d "$UPSTREAM/.git" ]; then
    git clone -q "$REPOSITORY" "$UPSTREAM"
fi
git -C "$UPSTREAM" checkout -q "$COMMIT"
if [ "$(git -C "$UPSTREAM" rev-parse HEAD)" != "$COMMIT" ] || [ -n "$(git -C "$UPSTREAM" status --porcelain)" ]; then
    echo "O clone do extrator não está limpo no commit $COMMIT." >&2
    exit 1
fi

rm -rf "$BUILD/lib" "$BUILD/native" "$BUILD/classes" "$BUILD/patched"
mvn -q -B -f "$HERE/pom.xml" dependency:copy-dependencies -DoutputDirectory="$BUILD/lib"
cp "$UPSTREAM/$JNETPCAP/jnetpcap.jar" "$BUILD/lib/"
mkdir -p "$BUILD/native"
cp "$UPSTREAM/$JNETPCAP/libjnetpcap.so" "$UPSTREAM/$JNETPCAP/libjnetpcap-pcap100.so" "$BUILD/native/"
# A libjnetpcap.so procura libpcap.so sem versão, que só existe com o pacote de desenvolvimento da libpcap.
LIBPCAP="$(ldconfig -p | awk '/libpcap\.so\.[0-9.]+ \(libc6,x86-64\)/ {print $NF; exit}')"
if [ -z "$LIBPCAP" ]; then
    echo "libpcap não encontrada." >&2
    exit 1
fi
ln -s "$LIBPCAP" "$BUILD/native/libpcap.so"

compile() {
    local output="$1" source_root="$2" program="$3"
    mkdir -p "$output"
    javac --release 8 -nowarn -encoding UTF-8 -cp "$BUILD/lib/*" -d "$output" \
        "$source_root/$PACKAGE"/*.java "$source_root/$PACKAGE/worker/FlowGenListener.java" \
        "$HERE/src/nids/extractor/$program.java" 2>&1 | grep -v '^Note:' >&2 || true
    test -f "$output/nids/extractor/$program.class"
}

compile "$BUILD/classes/reference" "$UPSTREAM" ReferenceExtractor
mkdir -p "$BUILD/patched"
cp -r "$UPSTREAM/src" "$BUILD/patched/src"
for patch_file in "$HERE"/patches/*.patch; do
    patch -s -p1 -d "$BUILD/patched" < "$patch_file"
done
compile "$BUILD/classes/nids" "$BUILD/patched" NidsExtractor

jar cf "$BUILD/reference-extractor.jar" -C "$BUILD/classes/reference" .
jar cf "$BUILD/nids-extractor.jar" -C "$BUILD/classes/nids" .

python3 - "$BUILD" "$HERE" "$COMMIT" "$LIBPCAP" <<'PYTHON'
import hashlib, json, pathlib, subprocess, sys

build, here, commit, libpcap = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

java = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.splitlines()[0]
record = {
    "extractor_commit": commit,
    "java": java,
    "release": 8,
    "libpcap": libpcap,
    "jars": {path.name: digest(path) for path in sorted(build.glob("*.jar"))},
    "patches": {path.name: digest(path) for path in sorted((here / "patches").glob("*.patch"))},
    "sources": {path.name: digest(path) for path in sorted((here / "src/nids/extractor").glob("*.java"))},
    "libraries": {path.name: digest(path) for path in sorted((build / "lib").glob("*.jar"))},
    "native": {path.name: digest(path) for path in sorted((build / "native").glob("libjnetpcap*.so"))},
}
(build / "extractor-build.json").write_text(json.dumps(record, indent=2) + "\n")
PYTHON
echo "Extrator compilado em $BUILD."
