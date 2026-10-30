"""Rastreabilidade e semântica de apresentação; nenhum rótulo externo simulado."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from etapa13.evidence import evaluate_recipe,choose_examples,authenticate,native
from etapa13.figures import map_categories
from etapa13.verification import arithmetic
from etapa13.tables import latex_table
from sbsr_lidar.storage import fingerprint,atomic_write_json


def test_recipe_scalar_requires_one_row():
    data=pd.DataFrame({'case':['evaluation','evaluation'],'x':[.2,.5]})
    with pytest.raises(ValueError,match='uma linha'):
        evaluate_recipe(data,{'aggregation':'scalar','column':'x','filters':{'case':'evaluation'}})


def test_recipe_filters_role_and_scenario_not_first_row():
    data=pd.DataFrame({'role':['development','evaluation','evaluation'],'w':[.5,.25,.5],'rho':[.9,.8,.6]})
    assert evaluate_recipe(data,{'aggregation':'scalar','column':'rho','filters':{'role':'evaluation','w':.5}})==.6
    assert evaluate_recipe(data,{'aggregation':'count','filters':{'role':'evaluation'}})==2


def test_map_unknown_is_distinct_from_observed_without_canopy():
    observation=np.array([[255,2,3,4,1,1]],dtype='uint8');labels=np.array([[-1,-1,-1,-1,0,2]],dtype='int32')
    np.testing.assert_array_equal(map_categories(observation,labels),[[0,2,2,2,1,3]])


def test_map_rejects_canopy_in_unobserved_cell():
    with pytest.raises(ValueError,match='fora do suporte'):
        map_categories(np.array([[2]],dtype='uint8'),np.array([[1]],dtype='int32'))


def test_map_rejects_unknown_code_instead_of_silent_absence():
    with pytest.raises(ValueError,match='desconhecido'):map_categories(np.array([[0]]),np.array([[0]]))


def test_examples_reproducible_with_both_agreement_and_disagreement():
    rows=[]
    for status in ['kept','lost','gained','neither']:
        rows.extend([{'disagreement':status,'selection_hash':'b','unit_id':status+'1','score':100},
            {'disagreement':status,'selection_hash':'a','unit_id':status+'2','score':0}])
    data=pd.DataFrame(rows);a=choose_examples(data,'hash');b=choose_examples(data.sample(frac=1,random_state=3),'hash')
    assert [e['unit_id'] for e in a]==[e['unit_id'] for e in b]
    assert {e['status'] for e in a}=={'kept','lost','gained','neither'}
    assert all(e['unit_id'].endswith('2') and e['group_n']==2 for e in a)


def test_empty_stratum_is_not_invented():
    rows=pd.DataFrame([{'disagreement':'lost','selection_hash':'a','unit_id':'U'}])
    assert [e['status'] for e in choose_examples(rows,'hash')]==['lost']


def test_arithmetic_provenance_reproduces_shortfall_and_top_partition():
    metrics={'target':120,'actual':114,'n':114,'k':23,'intersection':12}
    assert arithmetic('target-actual',metrics)==6
    assert arithmetic('n-2*k+intersection',metrics)==80
    assert arithmetic('intersection/(2*k-intersection)',metrics)==pytest.approx(12/34)


def test_recipe_cannot_execute_arbitrary_code():
    with pytest.raises(ValueError):arithmetic("__import__('os').system('true')",{})


def test_authentication_preserves_mutable_history_but_rejects_changed_science(tmp_path):
    (tmp_path/'docs').mkdir();state=tmp_path/'docs/estado_projeto.json';state.write_text('{"etapa":12}')
    scientific=tmp_path/'data.csv';scientific.write_text('n\n114\n')
    m=tmp_path/'manifest.json';atomic_write_json(m,{'artifacts':[fingerprint(state),fingerprint(scientific)]})
    _,checked,aliases=authenticate(tmp_path,m);assert len(checked)==2 and len(aliases)==1
    state.write_text('{"etapa":13}');authenticate(tmp_path,m)
    scientific.write_text('n\n120\n')
    with pytest.raises(ValueError,match='alterada'):authenticate(tmp_path,m)


def test_native_missing_is_not_exported_as_zero():
    assert native({'value':np.float64(np.nan)})=={'value':None}
    assert native({'value':np.int64(114)})=={'value':114}


def test_latex_export_escapes_literal_numeric_percent_and_id():
    text=latex_table(pd.DataFrame({'id':['CO_BT_05'],'obs':['88.6%']}))
    assert r'CO\_BT\_05' in text and r'88.6\%' in text
