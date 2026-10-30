"""Falhas de retomada encontradas pela revisão final; nenhum dado bruto alterado."""
from pathlib import Path
import sys
import pytest
from sbsr_lidar.crown_data import completed
from sbsr_lidar.storage import atomic_write_json, fingerprint

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from etapa15.editorial import check_pdf_elements


def test_incomplete_checkpoint_is_cache_miss_and_can_be_rebuilt(tmp_path):
    a = tmp_path/'a.txt'; b = tmp_path/'b.txt'; seal = tmp_path/'complete.json'
    a.write_text('first'); b.write_text('second')
    atomic_write_json(seal, {'outputs': [fingerprint(a), fingerprint(b)]})
    assert completed(seal)
    b.unlink()
    assert completed(seal) is None
    assert a.read_text() == 'first'
    b.write_text('rebuilt')
    # Recriar o arquivo com conteúdo diferente não autentica o selo antigo.
    assert completed(seal) is None
    atomic_write_json(seal, {'outputs': [fingerprint(a), fingerprint(b)]})
    assert completed(seal)


def test_pdf_audit_requires_actual_captions_not_just_mentions_in_text():
    complete = 'Figura 1: mapa. Figura 2: ranks. Figura 3: sensibilidade. Tabela 1: amostra. Tabela 2: controles.'
    assert check_pdf_elements(complete)['figures'] == [1, 2, 3]
    missing = complete.replace('Figura 3: sensibilidade.', 'Veja a Figura 3 para a sensibilidade.')
    with pytest.raises(ValueError, match='ausentes'): check_pdf_elements(missing)
