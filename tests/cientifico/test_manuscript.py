"""Invariantes de transferência de evidências para o artigo, sem fabricar resultados."""
from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from etapa14.build import display, escape_tex, select_one
from etapa14.audit import (expand_numbers, prose, abstract_counts, claims_matrix,
    bibliography_checks, verify_registry, WORDS)
from sbsr_lidar.storage import atomic_write_json, fingerprint


@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), -float('inf')])
def test_missing_or_nonfinite_result_never_becomes_zero_or_printed_number(value):
    with pytest.raises(ValueError): display(value, 4)


def test_language_changes_separator_but_not_statistic_and_percent_scale():
    assert display(12/34, 4) == r'0{,}3529'
    assert display(12/34, 4, english=True) == '0.3529'
    assert display(.8150676431, 2, scale=100) == r'81{,}51'


def test_author_and_identifier_text_cannot_inject_tex():
    assert escape_tex('A & B_01 10%') == r'A \& B\_01 10\%'
    assert escape_tex(r'\input{secret}') == r'\textbackslash{}input\{secret\}'


def test_control_requires_unique_role_weight_and_scenario():
    data = pd.DataFrame({'role': ['dev', 'eval', 'eval'], 'w': [.5, .25, .5], 'rho': [.9, .8, .6]})
    assert select_one(data, {'role': 'eval', 'w': .5})['rho'] == .6
    with pytest.raises(ValueError): select_one(data, {'role': 'eval'})
    with pytest.raises(ValueError): select_one(data, {'role': 'missing'})


def test_unknown_macro_fails_instead_of_disappearing_during_tex_csname():
    registry = {'metrics': {'rho': {'value': .6681648, 'decimals': 4}}, 'parameters': {}}
    assert expand_numbers(r'\Ev{rho}; \En{rho}', registry) == '0,6682; 0.6682'
    with pytest.raises(ValueError, match='sem evidência'):
        expand_numbers(r'\Ev{invented_accuracy}', registry)


def test_word_count_preserves_escaped_percent_and_all_following_prose():
    text = prose(r'\noindent Top-20\% com 0,3529; \textit{sem validação}. % comentário')
    assert 'validação' in text and 'comentário' not in text
    assert WORDS.findall('0,3529 0.6682 top-20% pós-resultados') == ['0,3529', '0.6682', 'top', '20%', 'pós-resultados']


@pytest.mark.parametrize('n', [99, 151])
def test_abstract_outside_limits_blocks_compilation(n):
    words = ' '.join(['palavra']*n)
    source = '\\section*{Resumo}\n'+words+r'\smallskip'+'\n'+r'\begin{otherlanguage}{english}\itshape'+'\n'+words+r'\smallskip'
    with pytest.raises(ValueError, match='palavras'):
        abstract_counts(source, {'metrics': {}, 'parameters': {}})


def test_abstract_boundaries_exclude_keywords_and_headers():
    words = ' '.join(['palavra']*100)
    source = '\\section*{Resumo}\n'+words+r'\smallskip PALAVRAS CHAVE'+'\n'+r'\begin{otherlanguage}{english}\itshape'+'\n'+words+r'\smallskip KEYWORDS'
    counts = abstract_counts(source, {'metrics': {}, 'parameters': {}})
    assert counts['pt']['words'] == counts['en']['words'] == 100


def test_claim_requires_real_previous_evidence_id():
    source = '% EVIDENCIA: C14_R | exploratoria | C13_MISSING\nUma conclusão.'
    with pytest.raises(ValueError, match='sem índice'):
        claims_matrix(source, {'metrics': {}, 'parameters': {}}, [])


def test_citation_must_resolve_and_no_demonstration_reference_can_sneak_in():
    with pytest.raises(ValueError): bibliography_checks(r'\cite{real}', '@article{real,}\n@misc{example,}')
    with pytest.raises(ValueError): bibliography_checks(r'\cite{missing}', '@article{real,}')
    assert bibliography_checks(r'\cite{real}', '@article{real,}')['references'] == 1


def test_numeric_provenance_reproduces_raw_value_and_detects_changed_source(tmp_path):
    path = tmp_path/'result.json'; atomic_write_json(path, {'rho': .6681647966772448})
    registry = {'metrics': {'rho': {'value': .6681647966772448, 'source': fingerprint(path), 'json_pointer': '/rho'}}, 'parameters': {}}
    assert verify_registry(registry)['reproduced_metrics'] == 1
    registry['metrics']['rho']['value'] = .9
    with pytest.raises(ValueError, match='não reproduzido'): verify_registry(registry)
    registry['metrics']['rho']['value'] = .6681647966772448
    atomic_write_json(path, {'rho': .9})
    with pytest.raises(ValueError, match='alterada'): verify_registry(registry)
