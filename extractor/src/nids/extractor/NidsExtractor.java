package nids.extractor;

import cic.cs.unb.ca.jnetpcap.BasicFlow;
import cic.cs.unb.ca.jnetpcap.BasicPacketInfo;
import cic.cs.unb.ca.jnetpcap.FlowFeature;
import cic.cs.unb.ca.jnetpcap.FlowGenerator;
import cic.cs.unb.ca.jnetpcap.PacketReader;
import org.jnetpcap.PcapClosedException;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Extrator do NIDS. Usa as classes do CICFlowMeter corrigido com os patches de emissão e de captura ao vivo.
 * Lê de um arquivo PCAP ou de uma interface, emite cada fluxo quando o relógio da captura passa do tempo
 * limite e escreve uma linha JSON por evento na saída padrão: abertura, um fluxo por linha e encerramento.
 * A leitura de arquivo termina no fim do arquivo. A captura ao vivo termina quando a entrada padrão é
 * fechada ou recebe a linha "stop".
 */
public final class NidsExtractor {
    static final String EXTRACTOR_COMMIT = "13a061520b862d605eea746c79ca4033b30d98fc";
    private static final long FLOW_TIMEOUT = 120000000L;
    private static final long ACTIVITY_TIMEOUT = 5000000L;

    private final BufferedWriter out = new BufferedWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8));
    private final Map<String, Long> flowsByCause = new LinkedHashMap<>();
    private volatile boolean stopRequested;
    private long sequence;
    private long captureClock;
    private FlowGenerator generator;

    private NidsExtractor() {
    }

    public static void main(String[] args) throws IOException {
        Map<String, String> options = parse(args);
        new NidsExtractor().run(options);
    }

    private void run(Map<String, String> options) throws IOException {
        boolean live = options.containsKey("--iface");
        int readTimeoutMillis = Integer.parseInt(options.getOrDefault("--read-timeout-ms", "100"));
        int snaplen = Integer.parseInt(options.getOrDefault("--snaplen", "65535"));
        long idleMarginMicros = Long.parseLong(options.getOrDefault("--idle-margin-us", "2000000"));
        String source = live ? options.get("--iface") : options.get("--pcap");
        PacketReader reader = live
                ? new PacketReader(source, snaplen, readTimeoutMillis)
                : new PacketReader(source, true, false);
        generator = new FlowGenerator(true, FLOW_TIMEOUT, ACTIVITY_TIMEOUT);
        generator.addFlowListener(this::emit);
        if (live) {
            watchStandardInput();
        }

        StringBuilder header = new StringBuilder("[");
        String[] names = FlowFeature.getHeader().split(",");
        for (int index = 0; index < names.length; index++) {
            header.append(index == 0 ? "" : ",").append(quote(names[index]));
        }
        header.append(']');
        write("{\"type\":\"start\",\"extractor_commit\":" + quote(EXTRACTOR_COMMIT)
                + ",\"flow_timeout_us\":" + FLOW_TIMEOUT + ",\"activity_timeout_us\":" + ACTIVITY_TIMEOUT
                + ",\"source\":" + quote(live ? "interface" : "file") + ",\"location\":" + quote(source)
                + ",\"snaplen\":" + snaplen + ",\"read_timeout_ms\":" + readTimeoutMillis
                + ",\"idle_margin_us\":" + idleMarginMicros + ",\"java_version\":" + quote(System.getProperty("java.version"))
                + ",\"monotonic_ns\":" + System.nanoTime() + ",\"header\":" + header + "}");

        long total = 0L;
        long valid = 0L;
        long discarded = 0L;
        long readTimeouts = 0L;
        long firstDisordered = -1L;
        long previous = 0L;
        String stopReason = "end_of_file";
        while (true) {
            if (stopRequested) {
                stopReason = "stop_requested";
                break;
            }
            BasicPacketInfo packet;
            try {
                packet = reader.nextPacket();
            } catch (PcapClosedException end) {
                break;
            }
            if (packet == null && reader.lastReadTimedOut()) {
                readTimeouts++;
                advanceClock(nowMicros() - idleMarginMicros);
                generator.sweep(captureClock);
                continue;
            }
            total++;
            if (packet == null) {
                discarded++;
                continue;
            }
            long timestamp = packet.getTimeStamp();
            if (firstDisordered < 0 && previous > timestamp) {
                firstDisordered = packet.getId();
            } else {
                previous = timestamp;
            }
            advanceClock(timestamp);
            generator.sweep(captureClock);
            generator.addPacket(packet);
            valid++;
        }
        int openBeforeFlush = generator.getOpenFlowCount();
        generator.flush();
        long[] stats = live ? reader.captureStats() : null;
        StringBuilder causes = new StringBuilder("{");
        for (Map.Entry<String, Long> entry : flowsByCause.entrySet()) {
            causes.append(causes.length() == 1 ? "" : ",").append(quote(entry.getKey())).append(':').append(entry.getValue());
        }
        causes.append('}');
        write("{\"type\":\"end\",\"stop_reason\":" + quote(stopReason) + ",\"packets_read\":" + total
                + ",\"packets_valid\":" + valid + ",\"packets_discarded\":" + discarded
                + ",\"read_timeouts\":" + readTimeouts + ",\"packets_after_emission\":" + generator.getPacketsAfterEmission()
                + ",\"first_disordered_packet_id\":" + firstDisordered + ",\"open_flows_before_flush\":" + openBeforeFlush
                + ",\"flows_emitted\":" + sequence + ",\"flows_by_cause\":" + causes
                + ",\"pcap_stats\":" + (stats == null ? "null"
                        : "{\"received\":" + stats[0] + ",\"dropped\":" + stats[1] + ",\"interface_dropped\":" + stats[2] + "}")
                + ",\"monotonic_ns\":" + System.nanoTime() + "}");
    }

    private void emit(BasicFlow flow) {
        String features = flow.dumpFlowBasedFeaturesEx();
        long t0 = System.nanoTime();
        String cause = generator.getLastEmissionCause();
        sequence++;
        flowsByCause.merge(cause, 1L, Long::sum);
        write("{\"type\":\"flow\",\"seq\":" + sequence + ",\"cause\":" + quote(cause)
                + ",\"first_packet_us\":" + flow.getFlowStartTime() + ",\"last_packet_us\":" + flow.getLastSeen()
                + ",\"capture_clock_us\":" + captureClock + ",\"t0_ns\":" + t0
                + ",\"features\":" + quote(features) + "}");
    }

    private void advanceClock(long candidate) {
        // O relógio da captura nunca volta atrás.
        captureClock = Math.max(captureClock, candidate);
    }

    private void write(String line) {
        try {
            out.write(line);
            out.newLine();
            out.flush();
        } catch (IOException error) {
            throw new UncheckedIOException(error);
        }
    }

    private void watchStandardInput() {
        Thread watcher = new Thread(() -> {
            try (BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
                String line;
                while ((line = input.readLine()) != null) {
                    if ("stop".equals(line.trim())) {
                        break;
                    }
                }
            } catch (IOException ignored) {
                // Entrada padrão indisponível equivale a pedido de parada.
            }
            stopRequested = true;
        }, "stdin-watcher");
        watcher.setDaemon(true);
        watcher.start();
    }

    private static long nowMicros() {
        return ChronoUnit.MICROS.between(Instant.EPOCH, Instant.now());
    }

    private static String quote(String value) {
        StringBuilder text = new StringBuilder("\"");
        for (char character : value.toCharArray()) {
            if (character == '"' || character == '\\') {
                text.append('\\').append(character);
            } else if (character < 0x20) {
                text.append(String.format("\\u%04x", (int) character));
            } else {
                text.append(character);
            }
        }
        return text.append('"').toString();
    }

    private static Map<String, String> parse(String[] args) {
        Map<String, String> options = new LinkedHashMap<>();
        for (int index = 0; index + 1 < args.length; index += 2) {
            options.put(args[index], args[index + 1]);
        }
        if (args.length % 2 != 0 || options.containsKey("--pcap") == options.containsKey("--iface")) {
            System.err.println("uso: NidsExtractor (--pcap ARQUIVO | --iface INTERFACE) [--snaplen N] "
                    + "[--read-timeout-ms N] [--idle-margin-us N]");
            System.exit(2);
        }
        return options;
    }
}
