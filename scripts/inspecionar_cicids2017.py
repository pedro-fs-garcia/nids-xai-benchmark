#!/usr/bin/env python3
"""Gera uma inspeção dos cinco CSVs sem modificar as entradas."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
from itertools import chain, groupby
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
import zipfile
import zlib

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
METADATA = {'id', 'Flow ID', 'Src IP', 'Dst IP', 'Timestamp'}
ANNOTATIONS = {'Label', 'Attempted Category'}
TEXT = {'Flow ID', 'Src IP', 'Dst IP', 'Timestamp', 'Label'}
MISSING = {'', 'na', 'n/a', 'null', 'none'}
PARTS = ['finite', 'missing', 'nan', 'positive_infinity', 'negative_infinity', 'non_numeric']


def fingerprint(path):
    digest, crc = hashlib.sha256(), 0
    before = path.stat()
    with path.open('rb') as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
            crc = zlib.crc32(block, crc)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f'Arquivo mudou durante a leitura: {path}')
    return dict(bytes=after.st_size, mtime_ns=after.st_mtime_ns,
                sha256=digest.hexdigest(), crc32=f'{crc & 0xffffffff:08x}')


def new_stats():
    return {**dict.fromkeys(PARTS + ['zero', 'negative'], 0), 'min': None, 'max': None, 'examples': []}


def observe(stats, text, line):
    value = text.strip()
    if value.lower() in MISSING:
        kind = 'missing'
    else:
        try:
            number = float(value)
        except ValueError:
            kind = 'non_numeric'
        else:
            if math.isfinite(number):
                stats['finite'] += 1
                stats['zero'] += number == 0
                stats['negative'] += number < 0
                if stats['min'] is None or number < stats['min']:
                    stats['min'] = number
                if stats['max'] is None or number > stats['max']:
                    stats['max'] = number
                return False
            kind = 'nan' if math.isnan(number) else ('positive_infinity' if number > 0 else 'negative_infinity')
    stats[kind] += 1
    if len(stats['examples']) < 3:
        stats['examples'].append(dict(line=line, value=text, kind=kind))
    return True


def signature(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def duplicates(spool, temporary):
    ordered = spool.with_suffix('.sorted')
    subprocess.run(['sort', '--parallel=2', '--buffer-size=512M', f'--temporary-directory={temporary}',
                    '-k1,1', '-o', str(ordered), str(spool)], check=True, env={**os.environ, 'LC_ALL': 'C'})
    result = dict.fromkeys(['rows', 'unique_groups', 'duplicate_groups', 'excess_rows',
                           'rows_in_duplicate_groups', 'cross_file_groups', 'rows_in_cross_file_groups',
                           'conflicting_label_groups', 'rows_in_conflicting_label_groups', 'max_group_size'], 0)
    result['within_file_excess'], result['conflicting_examples'] = Counter(), []
    with ordered.open(encoding='utf-8') as stream:
        for digest, group in groupby(stream, key=lambda line: line.partition('\t')[0]):
            result['unique_groups'] += 1
            first, second = next(group), next(group, None)
            if second is None:
                result['rows'] += 1
                result['max_group_size'] = max(result['max_group_size'], 1)
                continue
            files, labels, locations, size = Counter(), Counter(), [], 0
            for record in chain((first, second), group):
                _, filename, label, line = record.rstrip('\n').split('\t')
                size += 1
                files[filename] += 1
                labels[label] += 1
                if len(locations) < 5:
                    locations.append(dict(file=filename, line=int(line)))
            result['rows'] += size
            result['duplicate_groups'] += 1
            result['excess_rows'] += size - 1
            result['rows_in_duplicate_groups'] += size
            result['max_group_size'] = max(result['max_group_size'], size)
            for filename, count in files.items():
                result['within_file_excess'][filename] += count - 1
            if len(files) > 1:
                result['cross_file_groups'] += 1
                result['rows_in_cross_file_groups'] += size
            if len(labels) > 1:
                result['conflicting_label_groups'] += 1
                result['rows_in_conflicting_label_groups'] += size
                result['conflicting_examples'].append(dict(sha256=digest, rows=size, files=dict(files), labels=dict(labels), locations=locations))
                result['conflicting_examples'].sort(key=lambda item: (-item['rows'], item['sha256']))
                del result['conflicting_examples'][10:]
    ordered.unlink()
    return result


def inspect(path, header, feature_indices, labels, complete, features):
    numeric = [(index, name) for index, name in enumerate(header) if name not in TEXT]
    indexes = {name: header.index(name) for name in ['Label', 'Attempted Category', 'Timestamp']}
    result = dict(file=path.name, records=0, structured_rows=0, blank_records=0, wrong_width=0,
                  repeated_headers=0, numeric_problem_rows=0, feature_problem_rows=0, bad_timestamps=0,
                  labels=Counter(), categories=Counter(), label_category=Counter(), empty=Counter(), whitespace=Counter(),
                  numeric={name: new_stats() for _, name in numeric}, timestamp_min=None, timestamp_max=None,
                  structural_examples=[])
    feature_set = set(feature_indices)
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.reader(stream, strict=True)
        if next(reader) != header:
            raise ValueError(f'Cabeçalho divergente: {path}')
        columns = [(index, result['numeric'][name]) for index, name in numeric]
        for row in reader:
            result['records'] += 1
            line = reader.line_num
            if not row or len(row) != len(header) or row == header:
                key = 'blank_records' if not row else ('repeated_headers' if row == header else 'wrong_width')
                result[key] += 1
                if len(result['structural_examples']) < 5:
                    result['structural_examples'].append(dict(line=line, columns=len(row), kind=key))
                continue
            result['structured_rows'] += 1
            for name, value in zip(header, row):
                if not value.strip():
                    result['empty'][name] += 1
                if value != value.strip():
                    result['whitespace'][name] += 1
            label, category = row[indexes['Label']], row[indexes['Attempted Category']]
            result['labels'][label] += 1
            result['categories'][category] += 1
            result['label_category'][(label, category)] += 1
            bad_numeric, bad_features = False, False
            for index, stats in columns:
                bad = observe(stats, row[index], line)
                bad_numeric |= bad
                bad_features |= bad and index in feature_set
            result['numeric_problem_rows'] += bad_numeric
            result['feature_problem_rows'] += bad_features
            try:
                timestamp = datetime.fromisoformat(row[indexes['Timestamp']]).isoformat(sep=' ', timespec='microseconds')
            except ValueError:
                result['bad_timestamps'] += 1
            else:
                if result['timestamp_min'] is None or timestamp < result['timestamp_min']:
                    result['timestamp_min'] = timestamp
                if result['timestamp_max'] is None or timestamp > result['timestamp_max']:
                    result['timestamp_max'] = timestamp
            label_id = labels.setdefault(label, len(labels))
            tail = f'\t{path.name}\t{label_id}\t{line}\n'
            complete.write(signature(row) + tail)
            features.write(signature([row[index] for index in feature_indices]) + tail)
            if result['records'] % 250000 == 0:
                print(f'{path.name}: {result["records"]:,} registros', flush=True)
    result['label_category'] = [dict(label=label, category=category, rows=count) for (label, category), count in sorted(result['label_category'].items())]
    print(f'{path.name}: concluído, {result["records"]:,} registros', flush=True)
    return result


def aggregate(files, header):
    numeric = {name: new_stats() for name in header if name not in TEXT}
    labels, categories = Counter(), Counter()
    for file in files:
        labels.update(file['labels'])
        categories.update(file['categories'])
        for name, source in file['numeric'].items():
            target = numeric[name]
            for key in PARTS + ['zero', 'negative']:
                target[key] += source[key]
            if source['min'] is not None:
                target['min'] = source['min'] if target['min'] is None else min(target['min'], source['min'])
                target['max'] = source['max'] if target['max'] is None else max(target['max'], source['max'])
            target['examples'].extend(dict(file=file['file'], **example) for example in source['examples'])
    return dict(numeric=numeric, labels=labels, categories=categories)


def fmt(value):
    if value is None:
        return '—'
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return f'{int(value):,}'.replace(',', '.')
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ') or '(vazio)'


def render(report):
    files, combined = report['files'], report['aggregate']
    total = sum(file['records'] for file in files)
    parsed = sum(file['structured_rows'] for file in files)
    complete, features = report['duplicates']['complete_records'], report['duplicates']['traffic_attributes']
    numeric = combined['numeric']
    md = ['# Inspeção do Improved CIC-IDS2017', '', f'Gerado em {report["generated_at_utc"]}.', '',
          '## Resultado', '',
          f'- Leitura integral de **{fmt(total)} registros**, em cinco CSVs com **{len(report["columns"])} colunas** de mesmo cabeçalho.',
          f'- **{len(combined["labels"])} rótulos textuais**, preservados conforme os arquivos originais.',
          f'- **{fmt(sum(file["feature_problem_rows"] for file in files))} registros** com ao menos um atributo numérico de tráfego ausente, não numérico, NaN ou infinito.',
          f'- **{fmt(complete["excess_rows"])} repetições excedentes de linhas completas** e **{fmt(features["excess_rows"])} repetições excedentes na representação de atributos** definida abaixo.',
          '- **SHA-256, CRC32, tamanho e data de modificação de todas as entradas permaneceram iguais antes e depois da inspeção.**', '',
          'A inspeção não aplicou limpeza, remoção, reclassificação, amostragem, divisão entre conjuntos ou treinamento. Os arquivos originais permaneceram intactos.']

    def section(title, text=None):
        md.extend(['', f'## {title}', ''])
        if text:
            md.extend([text, ''])

    def table(headers, rows):
        md.append('| ' + ' | '.join(headers) + ' |')
        md.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        for row in rows:
            md.append('| ' + ' | '.join(fmt(value) for value in row) + ' |')
        md.append('')

    section('Procedência e integridade', 'A estrutura dos arquivos é compatível com o Improved CIC-IDS2017 associado ao trabalho de Liu e colaboradores, publicado no IEEE CNS 2022. Esta inspeção local não autentica a origem do download. [Documentação dos autores](https://intrusion-detection.distrinet-research.be/CNS2022/index.html).')
    table(['Arquivo', 'Bytes', 'SHA-256', 'Igual depois'],
          [(name, source['bytes'], f'`{source["sha256"]}`', 'Sim' if source == report['integrity_after'][name] else 'Não') for name, source in report['integrity_before'].items()])
    table(['CSV extraído', 'Tamanho e CRC32 correspondem ao diretório do ZIP'], [(entry['file'], 'Sim' if entry['matches'] else 'Não') for entry in report['archive_entries']])
    section('Volume e estrutura por arquivo', 'Registros são entradas retornadas pelo leitor CSV, descontado o cabeçalho inicial. Registros estruturados têm o número esperado de campos e não repetem o cabeçalho.')
    table(['Arquivo', 'Registros', 'Estruturados', 'Campos incorretos', 'Linhas vazias', 'Cabeçalhos repetidos', 'Bytes'],
          [(file['file'], *[file[key] for key in ['records', 'structured_rows', 'wrong_width', 'blank_records', 'repeated_headers']], report['integrity_before'][file['file']]['bytes']) for file in files])
    section('Distribuição dos rótulos', 'Valores originais de `Label`, sem agrupamento ou renomeação.')
    table(['Rótulo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Total', 'Proporção'],
          [(label, *[file['labels'].get(label, 0) for file in files], count, f'{100 * count / parsed:.4f}%'.replace('.', ',')) for label, count in sorted(combined['labels'].items(), key=lambda item: (-item[1], item[0]))])
    md.append('A divisão entre treino, validação e teste deve considerar classes por dia, repetições e relações entre fluxos. Separar por dias pode deixar classes ausentes do treinamento; sortear linhas pode distribuir registros repetidos entre conjuntos.')
    section('Categorias Attempted', '`Label` e `Attempted Category` são campos de anotação e devem ficar fora das entradas preditivas. A política para as categorias Attempted continua aberta. Os autores orientam seu tratamento conforme o objetivo da análise e recomendam que não sejam utilizadas como classes adicionais. [Orientações dos autores](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html).')
    table(['Attempted Category original', 'Registros'], sorted(combined['categories'].items()))
    combinations = Counter()
    for file in files:
        for item in file['label_category']:
            combinations[(item['label'], item['category'])] += item['rows']
    table(['Rótulo original', 'Categoria diferente de -1', 'Registros'], [(label, category, count) for (label, category), count in sorted(combinations.items()) if category != '-1'])
    section('Qualidade dos valores', 'Problemas numéricos incluem ausentes, NaN, infinitos e valores não numéricos. As contagens por registro representam a união dos problemas, sem contar um registro várias vezes.')
    table(['Arquivo', 'Registros com problema numérico, incluindo id e categoria', 'Registros com problema nos atributos de tráfego', 'Timestamps inválidos', 'Células vazias', 'Células com espaços nas extremidades'],
          [(file['file'], file['numeric_problem_rows'], file['feature_problem_rows'], file['bad_timestamps'], sum(file['empty'].values()), sum(file['whitespace'].values())) for file in files])
    problem_columns = [(name, stats) for name, stats in numeric.items() if any(stats[key] for key in PARTS[1:])]
    table(['Coluna', 'Ausentes', 'NaN', '+Infinito', '-Infinito', 'Não numéricos'], [(name, *[stats[key] for key in PARTS[1:]]) for name, stats in problem_columns])
    if not problem_columns:
        md.append('Não foram encontrados valores ausentes, NaN, infinitos ou não numéricos nas colunas numéricas.')
    else:
        table(['Arquivo', 'Linha física, incluindo cabeçalho', 'Coluna', 'Valor', 'Problema'], [(example['file'], example['line'], name, f'`{example["value"]}`', example['kind']) for name, stats in problem_columns for example in stats['examples']])
    section('Valores negativos e colunas constantes', 'Valores negativos foram contabilizados sem classificação automática como erro. Anotações e valores sentinela exigem interpretação própria; valores negativos em durações ou contagens requerem investigação. Nenhuma coluna foi excluída.')
    table(['Coluna', 'Negativos', 'Mínimo finito', 'Máximo finito'], [(name, stats['negative'], stats['min'], stats['max']) for name, stats in numeric.items() if stats['negative']])
    table(['Coluna constante entre valores finitos', 'Valor', 'Finitos', 'Não finitos ou ausentes'], [(name, stats['min'], stats['finite'], sum(stats[key] for key in PARTS[1:])) for name, stats in numeric.items() if stats['finite'] and stats['min'] == stats['max']])
    md.append('A constância descreve a população inspecionada. A seleção futura de atributos deve ser ajustada somente com o treinamento.')
    section('Duplicações', f'A comparação utiliza os valores textuais lidos pelo parser CSV, serializados em JSON e agrupados por SHA-256. Diferenças como `1` e `1.0` geram assinaturas distintas. A linha completa inclui todas as {len(report["columns"])} colunas. A representação diagnóstica de tráfego possui {len(report["traffic_attributes"])} atributos e exclui `id`, `Flow ID`, `Src IP`, `Dst IP`, `Timestamp`, `Label` e `Attempted Category`. Portas e protocolo são mantidos. A seleção final de atributos permanece aberta.')
    names = [('Registros comparados', 'rows'), ('Assinaturas distintas', 'unique_groups'), ('Grupos repetidos', 'duplicate_groups'), ('Repetições excedentes, descontada uma ocorrência por grupo', 'excess_rows'), ('Registros em grupos repetidos', 'rows_in_duplicate_groups'), ('Maior grupo', 'max_group_size'), ('Grupos em mais de um arquivo', 'cross_file_groups'), ('Registros em grupos presentes em mais de um arquivo', 'rows_in_cross_file_groups'), ('Grupos com mais de um rótulo textual', 'conflicting_label_groups'), ('Registros em grupos com mais de um rótulo textual', 'rows_in_conflicting_label_groups')]
    table(['Medida', 'Linhas completas', 'Atributos de tráfego'], [(name, complete[key], features[key]) for name, key in names])
    table(['Arquivo', 'Repetições excedentes de linhas completas dentro do arquivo', 'Repetições excedentes de atributos dentro do arquivo'], [(file['file'], complete['within_file_excess'].get(file['file'], 0), features['within_file_excess'].get(file['file'], 0)) for file in files])
    md.append('Fluxos legítimos distintos podem ter atributos iguais. Rótulos diferentes nessa projeção podem decorrer da perda de contexto ao excluir endereços e horários. Os grupos sinalizam pontos de investigação e não provam, por si sós, erros de rotulagem. Nenhuma repetição foi removida.')
    table(['Assinatura SHA-256', 'Registros', 'Rótulos e contagens', 'Localizações de exemplo'], [(f'`{item["sha256"]}`', item['rows'], ', '.join(f'{label} ({count})' for label, count in item['labels'].items()), ', '.join(f'{point["file"]}, linha {point["line"]}' for point in item['locations'])) for item in features['conflicting_examples']])
    section('Cobertura temporal', 'Extremos de `Timestamp`, interpretados como ISO 8601 sem conversão de fuso. São horários de início registrados para os fluxos, não necessariamente o início efetivo dos ataques ou o horário dos últimos pacotes.')
    table(['Arquivo', 'Menor Timestamp', 'Maior Timestamp'], [(file['file'], file['timestamp_min'], file['timestamp_max']) for file in files])
    section('Próximas decisões')
    md.extend(['- Definir a tarefa de classificação e o destino das categorias Attempted.', '- Selecionar atributos compatíveis com o extrator do NIDS, preservando metadados para rastreabilidade.', '- Investigar os valores inválidos e as repetições antes de estabelecer regras de tratamento.', '- Definir a separação entre treino, validação e teste com base nas classes por dia e nas relações entre fluxos.', '- Ajustar eventuais transformações somente com o treinamento e salvar os resultados em arquivos derivados separados.'])
    section('Método e reprodução')
    md.extend([f'- Python {report["python"]}, biblioteca padrão e GNU sort. Nenhuma dependência adicional foi instalada.', '- Leitura sequencial, sem carregar todos os CSVs em memória. Assinaturas intermediárias foram ordenadas em disco temporário e removidas ao final.', '- Ausentes numéricos incluem campos vazios, NA, N/A, null e None, sem distinção de maiúsculas e minúsculas. NaN é contado separadamente.', '- Estatísticas numéricas utilizam valores finitos convertidos para float64 durante a inspeção. As assinaturas utilizam os textos originais dos campos.', f'- Tempo total da inspeção e verificação de integridade: {report["elapsed_seconds"]} segundos. Este tempo não mede inferência nem TreeSHAP.', f'- SHA-256 do script executado: `{report["script_sha256"]}`.', '', 'Executar a partir da raiz do projeto.', '', '```bash', 'python3 scripts/inspecionar_cicids2017.py', '```', '', 'Os detalhes por arquivo e coluna, as combinações de categorias e rótulos e os hashes antes e depois estão em [inspecao-cicids2017.json](inspecao-cicids2017.json).'])
    section('Estatísticas numéricas por coluna')
    table(['Coluna', 'Finitos', 'Ausentes', 'NaN', '+Infinito', '-Infinito', 'Não numéricos', 'Zeros', 'Negativos', 'Mínimo finito', 'Máximo finito'], [(name, *[stats[key] for key in PARTS + ['zero', 'negative', 'min', 'max']]) for name, stats in numeric.items()])
    return '\n'.join(md) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('cicds-dataset/CICIDS2017_improved'))
    parser.add_argument('--archive', type=Path, default=Path('cicds-dataset/CICIDS2017_improved.zip'))
    parser.add_argument('--output', type=Path, default=Path('relatorios'))
    args = parser.parse_args()
    if shutil.which('sort') is None:
        parser.error('GNU sort é necessário para agrupar as assinaturas em disco.')
    source, output = args.input.resolve(), args.output.resolve()
    if output == source or source in output.parents:
        parser.error('A saída deve ficar fora da pasta dos CSVs.')
    files = [source / f'{day}.csv' for day in DAYS]
    if not all(path.is_file() for path in files):
        parser.error('Os cinco CSVs de segunda a sexta são necessários.')
    started = time.monotonic()
    paths = files + ([args.archive.resolve()] if args.archive.is_file() else [])
    print('Calculando hashes e CRC32 das entradas...', flush=True)
    before = {path.name: fingerprint(path) for path in paths}
    with files[0].open(newline='', encoding='utf-8-sig') as stream:
        header = next(csv.reader(stream, strict=True))
    if len(set(header)) != len(header) or not (TEXT | METADATA | ANNOTATIONS).issubset(header):
        raise ValueError('Cabeçalho com colunas repetidas ou campos necessários ausentes.')
    feature_indices = [index for index, name in enumerate(header) if name not in METADATA | ANNOTATIONS]
    label_ids = {}
    with tempfile.TemporaryDirectory(prefix='inspecao-cicids2017-') as temporary:
        temporary = Path(temporary)
        complete_path, features_path = temporary / 'complete.tsv', temporary / 'features.tsv'
        with complete_path.open('w', encoding='utf-8') as complete, features_path.open('w', encoding='utf-8') as features:
            inspections = [inspect(path, header, feature_indices, label_ids, complete, features) for path in files]
        print('Agrupando assinaturas de linhas completas...', flush=True)
        complete_duplicates = duplicates(complete_path, temporary)
        complete_path.unlink()
        print('Agrupando assinaturas de atributos de tráfego...', flush=True)
        feature_duplicates = duplicates(features_path, temporary)
    labels_by_id = {str(value): label for label, value in label_ids.items()}
    for summary in [complete_duplicates, feature_duplicates]:
        for example in summary['conflicting_examples']:
            example['labels'] = {labels_by_id[label]: count for label, count in example['labels'].items()}
    print('Verificando novamente hashes e CRC32 das entradas...', flush=True)
    after = {path.name: fingerprint(path) for path in paths}
    if before != after:
        raise RuntimeError('Entradas mudaram durante a inspeção; relatório não publicado.')
    entries = []
    if args.archive.is_file():
        with zipfile.ZipFile(args.archive) as archive:
            for entry in archive.infolist():
                name = Path(entry.filename).name
                if name in before and name.endswith('.csv'):
                    entries.append(dict(file=name, bytes=entry.file_size, crc32=f'{entry.CRC:08x}', matches=before[name]['bytes'] == entry.file_size and before[name]['crc32'] == f'{entry.CRC:08x}'))
    parsed = sum(file['structured_rows'] for file in inspections)
    for file in inspections:
        assert sum(file['labels'].values()) == file['structured_rows']
        assert sum(file['categories'].values()) == file['structured_rows']
        assert all(sum(stats[key] for key in PARTS) == file['structured_rows'] for stats in file['numeric'].values())
    for summary in [complete_duplicates, feature_duplicates]:
        assert summary['rows'] == parsed
        assert summary['unique_groups'] + summary['excess_rows'] == parsed
    report = dict(generated_at_utc=datetime.now(timezone.utc).isoformat(), input_directory=str(source), columns=header,
                  traffic_attributes=[header[index] for index in feature_indices], python=platform.python_version(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), integrity_before=before, integrity_after=after,
                  archive_entries=entries, files=inspections, aggregate=aggregate(inspections, header),
                  duplicates=dict(complete_records=complete_duplicates, traffic_attributes=feature_duplicates), elapsed_seconds=round(time.monotonic() - started, 3))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'inspecao-cicids2017.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (output / 'inspecao-cicids2017.md').write_text(render(report), encoding='utf-8')
    print(f'Relatório publicado em {output / "inspecao-cicids2017.md"}', flush=True)


if __name__ == '__main__':
    main()
