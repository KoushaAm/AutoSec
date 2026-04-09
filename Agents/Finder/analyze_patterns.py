import json

projects = {
    'zip4j': 'output/srikanth-lingala__zip4j_CVE-2018-1002202_1.3.2/test/killed_tps_report.json',
    'zt-zip': 'output/zeroturnaround__zt-zip_CVE-2018-1002201_1.12/test/killed_tps_report.json',
    'hutool': 'output/dromara__hutool_CVE-2018-17297_4.1.11/test/killed_tps_report.json',
    'jstachio': 'output/jstachio__jstachio_CVE-2023-33962_1.0.0/test/killed_tps_report.json',
    'sqlite': 'output/xerial__sqlite-jdbc_CVE-2023-32697_3.41.2.1/test/killed_tps_report.json',
    'uima': 'output/apache__uima-uimaj_CVE-2022-32287_3.3.0/alex_gpt5mini_uima/killed_tps_report.json',
}

for name, path in projects.items():
    with open(path) as f:
        data = json.load(f)
    killed = data.get('killed_tp_details', [])
    if not killed:
        print(f'=== {name}: no killed TPs ===\n')
        continue

    src_fp_count = sum(1 for k in killed if k.get('src_fp') == True)
    sink_fp_count = sum(1 for k in killed if k.get('sink_fp') == True and k.get('src_fp') != True)
    cached_count = sum(1 for k in killed if '[Caching]' in str(k.get('explanation', '')))

    sources = set()
    for k in killed:
        sources.add(k.get('source', 'unknown'))

    unique_reasons = set()
    for k in killed:
        exp = k.get('explanation', '')
        if '[Caching]' not in exp:
            unique_reasons.add(exp[:250])

    print(f'=== {name}: {len(killed)} killed TPs ===')
    print(f'  Marked as source FP: {src_fp_count}/{len(killed)}')
    print(f'  Marked as sink FP:   {sink_fp_count}/{len(killed)}')
    print(f'  Due to caching:      {cached_count}/{len(killed)}')
    print(f'  Unique sources:      {sources}')
    print(f'  Unique LLM reasons ({len(unique_reasons)}):')
    for r in list(unique_reasons)[:6]:
        print(f'    - {r[:220]}...')
    print()
