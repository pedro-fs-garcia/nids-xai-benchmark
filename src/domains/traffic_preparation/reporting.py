"""Relatório legível da conferência entre a extração do PCAP e os fluxos rotulados."""

from typing import Any


def render_extraction(summary: dict[str, Any]) -> str:
    flows, header = summary["flows"], summary["header"]
    statistics = summary["extractor_statistics"]
    differing = {name: item for name, item in summary["attributes"].items() if item["mismatches"]}
    excluded = summary["excluded_attributes"]
    result = "aprovada" if summary["passed"] else "reprovada"
    lines = [
        f"# Conferência da extração de atributos: trecho `{summary['segment']}`",
        "",
        f"A conferência foi {result}. Ela compara os fluxos que o CICFlowMeter corrigido, no commit "
        f"`{summary['extractor_commit'][:10]}` e sem alterações, extrai do trecho de PCAP com os fluxos "
        "rotulados de `tuesday.csv` do Improved CIC-IDS2017. O extrator e seus tempos limite seguem a "
        "[decisão 3](../docs/decisoes.md), e os atributos seguem o [dicionário](../docs/dicionario-atributos.md).",
        "",
        "## Trecho",
        "",
        f"O trecho contém os pacotes do início da captura de terça-feira até `{summary['stop']}` (UTC). "
        f"A tabela de referência reúne os {_integer(flows['reference'])} fluxos de `tuesday.csv` cujo primeiro "
        "pacote é anterior a esse instante.",
        "",
        f"Um fluxo pode durar até 120 s. Por isso, os fluxos que começam nos últimos {summary['border_seconds']} s "
        "do trecho formam a borda: o corte pode ter retirado parte dos seus pacotes, e eles são contados à parte.",
        "",
        "## Colunas",
        "",
        f"O extrator produz {header['extractor_columns']} colunas. "
        + ("Os nomes e a ordem coincidem com os do CSV, sem as colunas `id` e `Attempted Category`, que o CSV "
           "recebe na rotulagem." if header["equal"] else
           f"Os nomes ou a ordem diferem do CSV: {header['differences']}."),
        "As unidades vêm do mesmo método `dumpFlowBasedFeaturesEx` que gerou os CSVs.",
        "",
        "## Fluxos",
        "",
        "| Situação | Fora da borda | Na borda |",
        "|---|---:|---:|",
        f"| Fluxo presente nos dois lados | {_integer(flows['matched_inside'])} | {_integer(flows['matched_border'])} |",
        f"| Só no CSV | {_integer(flows['reference_only_inside'])} | {_integer(flows['reference_only_border'])} |",
        f"| Só na extração | {_integer(flows['extracted_only_inside'])} | {_integer(flows['extracted_only_border'])} |",
        "",
        "Dois fluxos correspondem quando têm o mesmo `Flow ID`, os mesmos endereços, portas e protocolo e o mesmo "
        "instante do primeiro pacote. Fluxos repetidos com a mesma chave são casados na ordem em que aparecem.",
        "",
        _nan_text(flows),
        "",
        "Rótulos dos fluxos casados fora da borda: "
        + ", ".join(f"{label} ({_integer(count)})" for label, count in sorted(summary["matched_inside_labels"].items()))
        + ".",
        "",
        "## Valores",
        "",
    ]
    rounding = {name: item for name, item in summary["attributes"].items() if item["rounding_differences"]}
    if differing:
        lines += ["| Atributo | Fluxos divergentes | Maior diferença absoluta | Exemplo (CSV; extração) |",
                  "|---|---:|---:|---|"]
        for name, item in differing.items():
            example = item["example"]
            lines.append(f"| {name} | {_integer(item['mismatches'])} | {item['max_abs_difference']:g} | "
                         f"`{example['flow_id']}` em {example['timestamp']}: {example['left']}; {example['right']} |")
    else:
        lines.append(f"Nos {_integer(flows['matched_inside'])} fluxos casados fora da borda, as entradas inteiras do "
                     "classificador, como contagens, tamanhos e flags, coincidem exatamente, e as entradas com fração "
                     f"diferem no máximo {summary['relative_tolerance']:g} em valor relativo.")
    lines += [""]
    if rounding:
        total = sum(item["rounding_differences"] for item in rounding.values())
        worst = max(item["max_rounding_relative"] for item in rounding.values())
        worst_ulps = max(item["max_rounding_ulps"] for item in rounding.values())
        lines += [
            f"Em {_integer(total)} valores de {len(rounding)} atributos com fração, o número da extração e o do CSV "
            f"diferem nos últimos algarismos. A maior diferença relativa é {worst:.2g}, ou {worst_ulps:g} unidades no "
            "último bit do `float64`. O notebook de rotulagem dos autores lê os CSVs com `pd.read_csv` e os grava com "
            "`to_csv`, convertendo cada número de texto para `float` e de volta. A versão do pandas usada não está "
            "registrada, e os conversores do pandas deste ambiente não reproduzem os valores do CSV, então a origem "
            "dessas diferenças não foi confirmada.",
            "",
            "| Atributo | Valores com diferença | Maior diferença relativa | Exemplo (CSV; extração) |",
            "|---|---:|---:|---|",
        ]
        for name, item in rounding.items():
            example = item["rounding_example"]
            lines.append(f"| {name} | {_integer(item['rounding_differences'])} | {item['max_rounding_relative']:.2g} | "
                         f"{example['left']}; {example['right']} |")
        lines += [""]
    excluded_lines = [f"{name}: {_integer(item['mismatches'])} fluxos divergentes"
                      for name, item in excluded.items() if item["mismatches"]]
    if excluded_lines:
        lines += ["Os dois comprimentos de cabeçalho, que não são entradas do classificador (decisão 2), divergem "
                  "em parte dos fluxos: " + "; ".join(excluded_lines) + ". A decisão 2 registra que a rotulagem "
                  "converteu essas colunas para `int16` no CSV, o que altera os valores acima de 32.767.", ""]
    else:
        lines += ["Os dois comprimentos de cabeçalho, que não são entradas do classificador, também coincidem.", ""]
    if summary["border_attributes"]:
        lines += ["Na borda, divergem: " + ", ".join(
            f"{name} ({_integer(item['mismatches'])})" for name, item in summary["border_attributes"].items())
            + ". O corte do trecho explica essas diferenças.", ""]
    for title, key in (("Fluxos só no CSV, fora da borda", "reference_only_inside"),
                       ("Fluxos só na extração, sem NaN, fora da borda", "extracted_only_inside"),
                       ("Exemplos de fluxos com NaN, só na extração", "extracted_only_inside_with_nan")):
        if summary["examples"][key]:
            lines += [f"### {title}", "", "```json", *[str(row) for row in summary["examples"][key]], "```", ""]
    lines += [
        "## Extrator do NIDS",
        "",
        _emission_text(summary["nids_extractor"]),
        "",
        "## Leitura dos pacotes",
        "",
        f"O extrator leu {_integer(statistics['packets_read'])} pacotes, dos quais "
        f"{_integer(statistics['packets_valid'])} são IPv4 e {_integer(statistics['packets_discarded'])} foram "
        f"descartados por não serem IPv4. Ele emitiu {_integer(statistics['flows_emitted_during_reading'])} fluxos "
        f"durante a leitura e {_integer(statistics['flows_dumped_at_end'])} no fim do arquivo. "
        + ("Nenhum pacote estava fora de ordem." if statistics["first_disordered_packet_id"] < 0
           else f"O primeiro pacote fora de ordem tem id {statistics['first_disordered_packet_id']}."),
        "",
        "## Reprodução",
        "",
        "A partir de `src/`, depois de compilar o extrator com `extractor/build.sh` e preparar o PCAP com "
        "`python main.py preparar-pcap`:",
        "",
        "```bash",
        f"python main.py conferir-extracao --trecho {summary['segment']}",
        "```",
        "",
        f"O registro da execução está em [training-runs/traffic/extracao/{summary['run_id']}/report.json]"
        f"(../training-runs/traffic/extracao/{summary['run_id']}/report.json). O manifesto da preparação está em "
        f"[{summary['preparation_manifest']}](../{summary['preparation_manifest']}).",
        "",
    ]
    return "\n".join(lines)


def _nan_text(flows: dict[str, Any]) -> str:
    if not flows["extracted_with_nan"]:
        return "Nenhum fluxo extraído tem valor `NaN`."
    columns = ", ".join(f"`{name}` ({_integer(count)})" for name, count in flows["nan_columns"].items())
    return (f"{_integer(flows['extracted_with_nan'])} fluxos extraídos têm algum valor `NaN`, e "
            f"{_integer(flows['reference_with_nan'])} fluxos do CSV têm. Fora da borda, "
            f"{_integer(flows['extracted_only_inside_with_nan'])} dos {_integer(flows['extracted_only_inside'])} fluxos "
            f"que só a extração tem estão nesse caso. As colunas com `NaN` são: {columns}. São fluxos de um único "
            "pacote, sem intervalo entre pacotes. Na leitura de cada CSV, o notebook de rotulagem dos autores "
            "(`read_csvs_from_path_and_reformat`) chama `df.dropna()`, que descarta toda linha com algum `NaN`. A "
            "conferência não reprova esses fluxos.")


def _emission_text(emission: dict[str, Any]) -> str:
    causes = ", ".join(f"{cause} ({_integer(count)})" for cause, count in emission["by_cause"].items())
    if emission["equal"]:
        return (f"O extrator do NIDS, com os patches de emissão e de captura ao vivo, produziu as mesmas "
                f"{_integer(emission['nids_lines'])} linhas de atributos que o extrator sem alterações, no mesmo "
                f"trecho. Só o instante da emissão muda. Causas de emissão: {causes}. "
                f"Pacotes que chegaram a um fluxo já emitido: {_integer(emission['packets_after_emission'])}.")
    return (f"O extrator do NIDS diverge do extrator sem alterações: {_integer(emission['only_reference'])} linhas só na "
            f"referência e {_integer(emission['only_nids'])} só no NIDS. Causas de emissão: {causes}.")


def _integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")
