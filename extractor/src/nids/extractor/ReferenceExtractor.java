package nids.extractor;

import cic.cs.unb.ca.jnetpcap.BasicFlow;
import cic.cs.unb.ca.jnetpcap.BasicPacketInfo;
import cic.cs.unb.ca.jnetpcap.FlowFeature;
import cic.cs.unb.ca.jnetpcap.FlowGenerator;
import cic.cs.unb.ca.jnetpcap.PacketReader;
import org.jnetpcap.PcapClosedException;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Extração de referência. Repete a sequência de chamadas de Cmd.readPcapFile do CICFlowMeter corrigido
 * no commit 13a061520b, com as classes sem alteração: tempos limite de 120 s e 5 s, leitura só de IPv4,
 * uma linha por fluxo emitido durante a leitura e, no fim, os fluxos que ainda estavam abertos. O modo
 * Offline da interface gráfica, que os autores do Improved CIC-IDS2017 usaram, faz a mesma sequência em
 * ReadPcapFileWorker.readPcapFile.
 */
public final class ReferenceExtractor {
    private static final long FLOW_TIMEOUT = 120000000L;
    private static final long ACTIVITY_TIMEOUT = 5000000L;
    private static final String LINE_SEP = System.lineSeparator();

    private ReferenceExtractor() {
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 2) {
            System.err.println("uso: ReferenceExtractor <pcap> <csv de saída>");
            System.exit(2);
        }
        File output = new File(args[1]);
        if (output.exists()) {
            System.err.println("O arquivo de saída já existe: " + output);
            System.exit(2);
        }
        FlowGenerator generator = new FlowGenerator(true, FLOW_TIMEOUT, ACTIVITY_TIMEOUT);
        long[] emitted = {0L};
        long total = 0L;
        long valid = 0L;
        long discarded = 0L;
        long firstDisordered = -1L;
        long previous = 0L;
        try (OutputStream stream = new FileOutputStream(output)) {
            stream.write((FlowFeature.getHeader() + LINE_SEP).getBytes(StandardCharsets.US_ASCII));
            generator.addFlowListener((BasicFlow flow) -> {
                try {
                    stream.write((flow.dumpFlowBasedFeaturesEx() + LINE_SEP).getBytes(StandardCharsets.US_ASCII));
                    emitted[0]++;
                } catch (IOException error) {
                    throw new IllegalStateException(error);
                }
            });
            PacketReader reader = new PacketReader(args[0], true, false);
            while (true) {
                try {
                    BasicPacketInfo packet = reader.nextPacket();
                    total++;
                    if (packet != null) {
                        long timestamp = packet.getTimeStamp();
                        if (firstDisordered < 0 && previous > timestamp) {
                            firstDisordered = packet.getId();
                        } else {
                            previous = timestamp;
                        }
                        generator.addPacket(packet);
                        valid++;
                    } else {
                        discarded++;
                    }
                } catch (PcapClosedException end) {
                    break;
                }
            }
        }
        long remaining = generator.dumpLabeledCurrentFlow(output.getPath(), FlowFeature.getHeader());
        System.out.println("{\"packets_read\":" + total + ",\"packets_valid\":" + valid
                + ",\"packets_discarded\":" + discarded + ",\"flows_emitted_during_reading\":" + emitted[0]
                + ",\"flows_dumped_at_end\":" + remaining + ",\"first_disordered_packet_id\":" + firstDisordered + "}");
    }
}
