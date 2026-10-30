"""Infraestrutura e processamento do piloto LiDAR (etapas 02–11)."""
from __future__ import annotations

import argparse
import errno
import json
import sys
import zipfile
from pathlib import Path

from laspy.errors import LaspyException
from pydantic import ValidationError

from .config import Config, load_config
from .storage import atomic_write_json


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sbsr-lidar", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/piloto.yaml"))
    commands = parser.add_subparsers(dest="command", required=True)
    doctor_parser = commands.add_parser("doctor", help="Somente pré-verificação; não processa nuvens")
    doctor_parser.add_argument("--report", type=Path, help="Opcional: salvar o JSON no projeto")
    smoke_parser = commands.add_parser("smoke", help="IO sintético e até 10.000 pontos de uma nuvem real")
    smoke_parser.add_argument("--no-cache", action="store_true")
    plan_parser = commands.add_parser("plan-inputs", help="Plano do domínio/complementos; somente leitura")
    plan_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    prep_parser = commands.add_parser("prepare-inputs", help="Etapa 03: domínio e QC integral dos insumos")
    prep_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    prep_parser.add_argument("--download-missing", action="store_true")
    prep_parser.add_argument("--no-cache", action="store_true")
    terrain_parser = commands.add_parser("terrain", help="Etapa 04: comparar TIN/IDW, terreno e H com suporte limitado")
    terrain_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    terrain_parser.add_argument("--method", choices=["auto", "tin", "idw"], default="auto")
    terrain_parser.add_argument("--no-cache", action="store_true")
    reference_parser = commands.add_parser("reference", help="Etapa 05: janelas, recortes e formulários com rótulos pendentes")
    reference_parser.add_argument("--no-cache", action="store_true")
    canopy_parser = commands.add_parser("canopy", help="Etapa 06: baseline de copa, refino experimental e incerteza")
    canopy_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    canopy_parser.add_argument("--no-cache", action="store_true")
    units_parser = commands.add_parser("segment", help="Etapa 07: grades, revisão geométrica de eixos e unidades multiescala")
    units_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    units_parser.add_argument("--no-cache", action="store_true")
    indicators_parser = commands.add_parser("indicators", help="Etapa 08: métricas físicas e suporte por unidade, sem rankings")
    indicators_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    indicators_parser.add_argument("--no-cache", action="store_true")
    compare_parser = commands.add_parser("compare", help="Etapa 09: comparação exploratória, ablações e rankings no suporte comum")
    compare_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    compare_parser.add_argument("--no-cache", action="store_true")
    sensitivity_parser = commands.add_parser("sensitivity", help="Etapa 10: robustez, suporte comum e auditoria de validação")
    sensitivity_parser.add_argument("--case", choices=["main", "adversarial"], default="main")
    sensitivity_parser.add_argument("--plan-only", action="store_true")
    sensitivity_parser.add_argument("--no-cache", action="store_true")
    assessment_parser = commands.add_parser("evaluate-pilot", help="Etapa 11: avaliar evidências e planejar amostra; não processa nuvens")
    assessment_parser.add_argument("--design", type=Path, default=Path("configs/amostra_cientifica_v0_2_0.yaml"))
    crown_parser=commands.add_parser('sample-pycrown',help='Etapa 12: amostra exploratória PyCrown sem referência externa')
    crown_parser.add_argument('--design',type=Path,default=Path('configs/amostra_pycrown_exploratoria_v0_3_0.yaml'))
    crown_parser.add_argument('--case',help='Somente um dos dez corredores congelados')
    crown_parser.add_argument('--plan-only',action='store_true')
    crown_parser.add_argument('--download-missing',action='store_true')
    annotation_parser = commands.add_parser("check-annotations", help="Validar esquema, fonte, divisão e estado atual das anotações")
    annotation_parser.add_argument("--package", type=Path, required=True)
    annotation_parser.add_argument("--report", type=Path)
    commands.add_parser("config-schema", help="Exibir JSON Schema da configuração")
    args = parser.parse_args(argv)
    try:
        if args.command == "config-schema":
            print(json.dumps(Config.model_json_schema(), ensure_ascii=False, indent=2))
            return 0
        config = load_config(args.config)
        if args.command == "doctor":
            from .doctor import inspect_environment
            result = inspect_environment(config)
            if args.report:
                target = args.report.expanduser().resolve()
                if not target.is_relative_to(config.paths.project_root / "relatorios") or target.suffix != ".json":
                    raise ValueError("Relatório doctor deve ser JSON em project_root/relatorios")
                atomic_write_json(target, result)
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if result["ok"] else 1
        if args.command == "check-annotations":
            from .annotations import check_annotations
            result=check_annotations(args.package)
            if args.report:
                target=args.report.expanduser().resolve()
                if not target.is_relative_to(config.paths.project_root/'relatorios') or target.suffix!='.json':
                    raise ValueError('Relatório de anotações deve ser JSON em project_root/relatorios')
                atomic_write_json(target,result)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['ok'] else 2
        if args.command == 'sample-pycrown':
            from .crown_run import sample_pycrown
            result=sample_pycrown(config,args.design,case=args.case,plan_only=args.plan_only,download_missing=args.download_missing)
        elif args.command == "evaluate-pilot":
            from .pilot_evaluation import evaluate_pilot
            result = evaluate_pilot(config, args.design)
        elif args.command == "sensitivity":
            from .sensitivity_run import sensitivity_run, sensitivity_plan
            result = sensitivity_plan(config, args.case) if args.plan_only else sensitivity_run(config, args.case, use_cache=not args.no_cache)
        elif args.command == "compare":
            from .comparison_run import comparison_run
            result=comparison_run(config,args.case,use_cache=not args.no_cache)
        elif args.command == "indicators":
            from .indicator_run import indicators_run
            result=indicators_run(config,args.case,use_cache=not args.no_cache)
        elif args.command == "segment":
            from .segmentation import segmentation_run
            result=segmentation_run(config,args.case,use_cache=not args.no_cache)
        elif args.command == "canopy":
            from .canopy import canopy_run
            result=canopy_run(config,args.case,use_cache=not args.no_cache)
        elif args.command == "reference":
            from .reference import reference_run
            result=reference_run(config,use_cache=not args.no_cache)
        elif args.command == "terrain":
            from .terrain import terrain_run
            result = terrain_run(config,args.case,requested_method=args.method,use_cache=not args.no_cache)
        elif args.command in {"plan-inputs", "prepare-inputs"}:
            from .preparation import plan_inputs, prepare_inputs
            result = plan_inputs(config, args.case) if args.command == "plan-inputs" else prepare_inputs(
                config, args.case, download_missing=args.download_missing, use_cache=not args.no_cache)
        else:
            from .smoke import smoke
            result = smoke(config, use_cache=not args.no_cache)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print("Interrompido; consulte o manifesto da execução e execute novamente para retomar.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, ValidationError, LaspyException, zipfile.BadZipFile) as error:
        if isinstance(error, OSError) and error.errno in {errno.ENOSPC, errno.EDQUOT}:
            print(f"Sem espaço; execução interrompida: {error}", file=sys.stderr)
        else:
            print(f"Erro: {error}", file=sys.stderr)
        return 2
