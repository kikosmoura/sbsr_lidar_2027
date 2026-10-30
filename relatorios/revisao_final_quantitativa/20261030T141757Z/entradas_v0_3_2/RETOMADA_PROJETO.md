# Retomada — revisão interpretativa0.3.2, 30/10/2026

Artigo atual: `artigo/revisao_interpretacao_v0_3_2/manuscrito.pdf`, quatro
páginas, três figuras e três tabelas. O ponteiro é `artigo/versao_atual.json`.
As versões14/15/17 estão preservadas. Leia
`docs/revisao_interpretacao_artigo.md`,
`docs/protocolo_revisao_interpretacao.md` e decisõesD171–D176.

Essa revisão mantém os resultados PyCrown v0.3.0 e o complemento analítico
v0.3.1:114 IDs,68 na coorte fixa e16 pares sem reutilização. Explicita pontuação
experimental sem valência ecológica, apresenta a distribuição dos 16 pares e
discute a medição com atestado/XML oficiais e QC TIN5 já existente.

O atestado declara PEC-PCD Classe A e46 pontos para controle dos produtos, sem
resíduos/RMSE publicados no documento. QC do mesmo MDT não é acurácia externa
de H ou de copas. RMSE mediano por janela 0,080/0,222 m para pontos/blocos;
cobertura 98,8%/27,3%. Não afirmar que os contrastes superam o erro total.
Não assumir precisão numérica a partir de resolução, escala LAS ou metadados
de outro levantamento. Não reprocessar LAZ nem ajustar peso para favorecer3D.

As fontes, snapshots históricos, resultados, testes e provas visuais estão
em `relatorios/revisao_interpretacao/ultima_execucao.json`. Para conferir:

```bash
.venv-cientifico/bin/python scripts/revisar_interpretacao_artigo.py --verify
.venv-cientifico/bin/python -m pytest tests/cientifico/test_measurement_review.py -q
```

O verificador atual autentica12–17 com os snapshots por época. O guia17 está
no diretório `entradas_etapa17` da revisão atual. PDFs14/17 que estavam ausentes
foram recuperados byte a byte dos pacotes autenticados; os registros estão
na execução desta revisão. Não recompilar históricos para mascarar diferenças.

A referência externa continua ausente e o protocolo confirmatório v0.2 não
foi liberado. Não há inferência municipal, causal, ecológica ou acurácia de
copas; os pares não são independentes. Perda de elegibilidade e suporte comum
por par não foram renomeados como estabilidade global dos 114 IDs.

O fechamento editorial permanece dependente do endereço institucional,
equivalência integral ao modelo aceito e aprovação humana. Nome, afiliação e
e-mail já foram fornecidos. Não inventar endereço, aprovação ou submissão.
