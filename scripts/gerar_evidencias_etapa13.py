"""Gerar o pacote de evidências da etapa13 a partir da execução PyCrown imutável."""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import subprocess
import time
import uuid
import yaml
from sbsr_lidar.storage import fingerprint,atomic_write_json,read_json
from etapa13.evidence import Evidence,authenticate
from etapa13.figures import all_figures,setup
from etapa13.tables import compact_tables,captions,proofs


def generate(project,config_path,output=None):
    config=yaml.safe_load(config_path.read_text())
    if config['scientific_protocol']!='0.3.0' or config['inferential_intervals_enabled'] or config['external_accuracy_claims_enabled']:
        raise ValueError('Este pacote é restrito à v0.3.0 exploratória, sem acurácia externa ou IC')
    source_manifest,checked,aliases=authenticate(project,project/config['source_manifest'])
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:10]
    out=output or project/config['output_root']/run_id;out=out.resolve()
    if not (out.is_relative_to(project/'relatorios/etapa13') or out.is_relative_to(Path('/tmp'))):raise ValueError('Saída precisa estar em relatorios/etapa13 ou /tmp')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    source_files=[Path(__file__).resolve(),*sorted((project/'scripts/etapa13').glob('*.py'))]
    code=[fingerprint(p) for p in source_files]
    manifest={'stage':'13','run_id':run_id,'status':'running','scientific_protocol':'0.3.0','presentation_version':config['presentation_version'],
        'source_run_id':source_manifest['run_id'],'config':config,'config_fingerprint':fingerprint(config_path),'code':code,
        'source_manifest':fingerprint(project/config['source_manifest']),'authenticated_artifact_count':len(checked),'historical_mutable_snapshots':aliases,
        'environment':{name:importlib.metadata.version(name) for name in ['numpy','pandas','geopandas','rasterio','matplotlib','scipy']},
        'new_LAZ_processing':False,'source_products_modified':False,'outputs':[]}
    atomic_write_json(out/'manifest.json',manifest)
    try:
        evidence=Evidence(project,config).prepare();evidence.export(out)
        manifest['font']=setup(config)
        template=Path(config['template_pdf']);subprocess.run(['pdftotext','-layout',str(template),str(out/'modelo_fornecido_texto.txt')],check=True)
        text=(out/'modelo_fornecido_texto.txt').read_text()
        if '86 mm' not in text or '178 mm' not in text:raise ValueError('Dimensões do modelo PDF não confirmadas')
        manifest['template_pdf']=fingerprint(template)
        legends=captions(evidence);atomic_write_json(out/'legendas.json',legends)
        (out/'legendas.md').write_text('\n\n'.join(legends[k] for k in legends)+'\n')
        records=all_figures(evidence,out);records+=compact_tables(evidence,out)
        atomic_write_json(out/'indice_figuras_tabelas.json',{'items':records})
        manifest['proof_pdf']=proofs(records,legends,out)
        atomic_write_json(out/'auditoria_apresentacao.json',{'dimensions':'86mm/178mm conforme modelo fornecido','minimum_font_pt':config['minimum_font_pt'],
            'caption_font_pt':config['caption_font_pt'],'caption_font_weight':'bold','font':manifest['font'],
            'all_text_within_canvas':all(not r['text_outside_canvas'] for r in records),'all_map_height_scales_identical':len({tuple(r['height_scale_m']) for r in records if 'height_scale_m' in r})==1,
            'no_height_clipping':all(r.get('height_cells_clipped_above_maximum',0)==0 for r in records),
            'map_crs_epsg':31983,'category_semantics':{'0':'não processado','1':'observado sem copa detectada','2':'NoData no contexto','3':'copa estimada'},
            'not_a_submission_manuscript':True,'official_rules_check':fingerprint(project/'relatorios/etapa13/fontes_editoriais_verificadas.json')})
        manifest.update(status='completed',elapsed_seconds=time.monotonic()-started,
            outputs=[fingerprint(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'])
        atomic_write_json(out/'manifest.json',manifest)
        pointer={'run_id':run_id,'output_root':str(out),'manifest':fingerprint(out/'manifest.json'),'source_run_id':manifest['source_run_id']}
        atomic_write_json(project/'relatorios/etapa13/ultima_execucao.json',pointer)
        return pointer
    except BaseException as error:
        manifest.update(status='failed',error={'type':type(error).__name__,'message':str(error)})
        atomic_write_json(out/'manifest.json',manifest);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,default=Path('configs/apresentacao_etapa13.yaml'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();project=Path(__file__).resolve().parents[1]
    print(json.dumps(generate(project,args.config.resolve(),args.output),ensure_ascii=False,indent=2))
