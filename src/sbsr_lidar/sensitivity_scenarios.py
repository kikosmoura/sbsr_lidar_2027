"""Cenários graduais do piloto; seleção por identidade, não por ordem do chunk."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np

from .domain import Domain, build_domain, input_plan


@dataclass(frozen=True)
class Scenario:
    scenario_id: str = 'primary'
    axis: str = 'primary'
    resolution_m: float = 1.
    height_m: float = 3.
    halo_m: float = 10.
    expansion_m: float = 0.
    radius_m: float = 5.
    method: str = 'tin'
    connectivity: int = 8
    mask_version: str = 'baseline'
    fraction: float = 1.
    seed: int = 2027
    sampling_mode: str = 'coupled'


def scenarios(config):
    base = Scenario(seed=config.resources.seed)
    result = [base]
    def add(name, axis, **kw):
        result.append(replace(base, scenario_id=name, axis=axis, **kw))
    for value in [.5, 2.]: add(f'res_{value:g}', 'resolution', resolution_m=value)
    for value in [2., 5.]: add(f'height_{value:g}', 'height', height_m=value)
    for value in [0., 20.]: add(f'halo_{value:g}', 'context', halo_m=value)
    for value in [5., 10.]: add(f'domain_plus_{value:g}', 'measurement_domain', expansion_m=value)
    for value in [3., 10.]: add(f'radius_{value:g}', 'interpolation_radius', radius_m=value)
    add('idw_5', 'interpolation_method', method='idw')
    add('connectivity_4', 'patch_definition', connectivity=4)
    add('refined', 'classification', mask_version='refined')
    add('uncertainty_upper', 'classification_bound', mask_version='uncertainty_upper')
    for mode in ['coupled', 'height_only']:
        for fraction in sorted(set(config.robustness.thinning_fractions), reverse=True):
            for offset in sorted(set(config.robustness.thinning_seed_offsets)):
                seed = config.resources.seed+offset
                add(f'thin_{mode}_{fraction:g}_s{seed}', f'density_{mode}',
                    fraction=fraction, seed=seed, sampling_mode=mode)
    add('first_returns', 'return_policy', sampling_mode='first_returns')
    add('fine_low', 'selected_interaction', resolution_m=.5, height_m=2.)
    add('coarse_high', 'selected_interaction', resolution_m=2., height_m=5.)
    if len(result) > config.robustness.maximum_scenarios:
        raise ValueError('Cenários excedem orçamento; revisar protocolo')
    # A etapa testa os eixos solicitados, sem silenciosamente ignorar configuração divergente.
    for actual, required in [(config.sensitivity.resolutions_m, [.5, 1., 2.]),
                             (config.sensitivity.heights_m, [2., 3., 5.]),
                             (config.sensitivity.lengths_m, [25., 50., 100.])]:
        if sorted(actual) != required:
            raise ValueError('Etapa 10 requer resoluções .5/1/2, alturas 2/3/5 e unidades 25/50/100')
    if (config.grid.resolution_m, config.vegetation.minimum_height_m, config.pilot.halo_m,
            config.vegetation.connectivity) != (1., 3., 10., 8):
        raise ValueError('Cenário principal divergente; revisar protocolo congelado')
    return result


def maximal_domain(config, case):
    pilot = config.pilot.model_copy(update={'halo_m': 20.,
        'context_tiles': sorted(set(config.pilot.context_tiles+config.pilot.sensitivity_tiles)),
        'sensitivity_tiles': []})
    domain = build_domain(config.model_copy(update={'pilot': pilot}), case)
    # Buffers poligonais sucessivos não coincidem exatamente com buffer da soma
    # (aproximação dos arcos). Incluir os contextos reais, sem perder essas bordas.
    envelope = domain.nominal_tiles.geometry.union_all()
    for expansion in [5., 10.]:
        p = domain.measurement.buffer(expansion)
        if case == 'adversarial': p = p.intersection(envelope)
        ctx = p.buffer(10.)
        if case == 'adversarial': ctx = ctx.intersection(envelope)
        domain.context = domain.context.union(ctx)
    if domain.context.difference(envelope).area > 1e-5:
        raise ValueError('Contexto máximo excede as folhas planejadas')
    domain.metadata['context_area_m2'] = domain.context.area
    domain.metadata['maximum_ROI_includes_successive_buffer_arcs'] = True
    return domain


def scenario_domain(base, maximal, scenario):
    measurement = base.measurement.buffer(scenario.expansion_m) if scenario.expansion_m else base.measurement
    requested = measurement.buffer(scenario.halo_m) if scenario.halo_m else measurement
    if base.case == 'adversarial':
        envelope = maximal.nominal_tiles.geometry.union_all()
        measurement = measurement.intersection(envelope)
        requested = measurement.buffer(scenario.halo_m) if scenario.halo_m else measurement
        context = requested.intersection(envelope)
    else:
        context = requested
    if context.difference(maximal.context).area > 1e-5:
        raise ValueError('Cenário excede recorte máximo aprovado')
    metadata = dict(base.metadata, measurement_area_m2=measurement.area, context_area_m2=context.area,
        halo_m=scenario.halo_m, expansion_m=scenario.expansion_m,
        requested_context_omitted_m2=requested.difference(context).area)
    return Domain(base.case, base.corridor_id, base.official, measurement, context, maximal.nominal_tiles, metadata)


def thinning_uniform(tile, point_index, seed):
    """SplitMix64: um valor por registro LAZ, estável sob reordenação/chunks.

    O código decimal da folha é injetado nos 32 bits superiores. Não se presume
    identidade de pulso; .25 é subconjunto de .5 para uma mesma semente.
    """
    codes = np.array([int(str(t).replace('-', '')) for t in tile], dtype=np.uint64)
    index = np.asarray(point_index, dtype=np.uint64)
    if np.any(index >= 2**32):
        raise ValueError('Identidade excede codificação de 32 bits por folha')
    value = (codes << np.uint64(32)) | index
    with np.errstate(over='ignore'):
        value = value ^ np.uint64(seed)
        value = value+np.uint64(0x9E3779B97F4A7C15)
        value = (value ^ (value >> np.uint64(30)))*np.uint64(0xBF58476D1CE4E5B9)
        value = (value ^ (value >> np.uint64(27)))*np.uint64(0x94D049BB133111EB)
        value ^= value >> np.uint64(31)
    return (value >> np.uint64(11)).astype(np.float64)/2**53


def plan(config, case):
    maximal = maximal_domain(config, case)
    rows = input_plan(config, maximal)
    return {'case': case, 'scenarios': [asdict(s) for s in scenarios(config)],
        'scales_m': [25, 50, 100], 'maximum_domain': maximal.metadata, 'inputs': rows,
        'raw_reads': 'one bounded MDS ROI extraction; one maximum MDT extraction; cached numerical intermediates',
        'horizontal_gap_distances_m': {'values': [0, 2, 5], 'executed': False,
            'reason': 'No graph metric is defined; B/C unavailable in frozen pilot. Do not bridge unknown gaps.'}}
