"""Executar com Python nativo do QGIS, sem importar o ambiente científico."""
import argparse
import json
import os
import tempfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    args=parser.parse_args()
    directory=args.package.resolve()
    plan=json.loads((directory/'plano_referencia.json').read_text())
    with tempfile.TemporaryDirectory(prefix='sbsr_qgis_05_') as temporary:
        os.environ['QT_QPA_PLATFORM']='offscreen'
        for key,subdir in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime')]:
            target=Path(temporary)/subdir;target.mkdir(mode=0o700)
            os.environ[key]=str(target)
        from qgis.core import (QgsApplication,QgsProject,QgsVectorLayer,QgsRasterLayer,QgsCoordinateReferenceSystem,
            QgsFillSymbol,QgsMarkerSymbol,QgsEditorWidgetSetup,QgsDefaultValue,QgsRectangle,
            QgsMultiBandColorRenderer,Qgis)
        app=QgsApplication([],False,str(Path(temporary)/'profile'))
        app.initQgis()
        created=[]
        for mode in ['anotacao_cega','qa_insumos']:
            project=QgsProject()
            project.setCrs(QgsCoordinateReferenceSystem.fromEpsgId(plan['epsg']))
            project.setTitle('Etapa 05 — '+mode+' — rótulos pendentes')
            project.setFileName(str(directory/(mode+'.qgz')))
            project.setPresetHomePath(str(directory))
            # Nenhum ranking, índice ou classe LAS é carregado neste projeto.
            for window in plan['windows']:
                image=directory/'janelas'/window['window_id']/'rgb_pontos_lidar.tif'
                layer=QgsRasterLayer(str(image),window['window_id']+' · RGB LiDAR 2020 (não ortofoto)')
                if not layer.isValid():raise RuntimeError('Raster QGIS inválido: '+str(image))
                renderer=QgsMultiBandColorRenderer(layer.dataProvider(),1,2,3);renderer.setAlphaBand(4)
                layer.setRenderer(renderer);project.addMapLayer(layer)
            for name in ['janelas','contextos']:
                layer=QgsVectorLayer(str(directory/'amostras.gpkg')+'|layername='+name,name,'ogr')
                if not layer.isValid():raise RuntimeError('Camada QGIS inválida: '+name)
                layer.setReadOnly(True)
                layer.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'transparent','outline_color':'55,81,127',
                    'outline_width':'0.3' if name=='janelas' else '0.15'}))
                project.addMapLayer(layer)
            if mode=='qa_insumos':
                for case,source in plan['terrain_sources'].items():
                    for key in ['dtm','validity']:
                        layer=QgsRasterLayer(source[key],case+' · QC '+key+' (mesmo sensor)')
                        if not layer.isValid():raise RuntimeError('Raster de QA inválido')
                        project.addMapLayer(layer)
            for purpose in ['vegetacao','altura','lacunas','prioridade']:
                layer=QgsVectorLayer(str(directory/'trabalho/anotacoes.gpkg')+'|layername='+purpose,'Anotar '+purpose,'ogr')
                if not layer.isValid():raise RuntimeError('Camada de anotação inválida: '+purpose)
                def widget(name,kind,options):layer.setEditorWidgetSetup(layer.fields().indexFromName(name),QgsEditorWidgetSetup(kind,options))
                def value_map(name,values):widget(name,'ValueMap',{'map':[{value:value} for value in values]})
                value_map('state',['pendente','concluido']);value_map('confidence',['baixa','media','alta'])
                value_map('reviewer_slot',['A','B']);value_map('temporal_compatible',['sim','nao','incerto'])
                value_map('method',['manual','medicao_campo','registro_externo']);value_map('saw_rankings',['nao','sim'])
                value_map('window_id',[w['window_id'] for w in plan['windows']])
                value_map('source_id',['lidar_rgb_xyz_2020','terreno_derivado_2020'])
                if purpose in plan['annotation_labels']:value_map('label',plan['annotation_labels'][purpose])
                if purpose=='altura':value_map('value_type',['altura_objeto','cota_terreno'])
                tasks=[t for t in plan['tasks'] if t['purpose']==purpose]
                widget('task_id','ValueMap',{'map':[{t['window_id']+' / '+t['reviewer_slot']:t['task_id']} for t in tasks]})
                for name,expression in [('annotation_id','uuid()'),('state',"'pendente'"),('purpose',"'"+purpose+"'")]:
                    layer.setDefaultValueDefinition(layer.fields().indexFromName(name),QgsDefaultValue(expression))
                for field in ['window_id','reviewer_slot']:
                    expression='CASE "task_id" '+''.join("WHEN '"+t['task_id']+"' THEN '"+t[field]+"' " for t in tasks)+'END'
                    layer.setDefaultValueDefinition(layer.fields().indexFromName(field),QgsDefaultValue(expression,True))
                symbol=(QgsMarkerSymbol.createSimple({'color':'232,171,42','size':'2'}) if purpose=='altura' else
                        QgsFillSymbol.createSimple({'color':'244,206,70,70','outline_color':'136,89,18','outline_width':'.3'}))
                layer.renderer().setSymbol(symbol)
                project.addMapLayer(layer)
            first=plan['windows'][0]['bounds']
            project.viewSettings().setDefaultViewExtent(__import__('qgis.core',fromlist=['QgsReferencedRectangle']).QgsReferencedRectangle(
                QgsRectangle(first[0]-5,first[1]-5,first[2]+5,first[3]+5),project.crs()))
            if not project.write():raise RuntimeError('Não foi possível salvar projeto QGIS')
            # Reabrir para validar caminhos e provedores, sem afirmar inspeção humana.
            test=QgsProject()
            if not test.read(project.fileName()) or any(not layer.isValid() for layer in test.mapLayers().values()):
                raise RuntimeError('Projeto QGIS não reabriu com camadas válidas')
            created.append({'project':project.fileName(),'layers':len(test.mapLayers()),'valid_layers':True})
            test.clear();project.clear()
        (directory/'qgis_validacao.json').write_text(json.dumps({'qgis_version':Qgis.QGIS_VERSION,'projects':created,
            'human_inspection_performed':False},ensure_ascii=False,indent=2)+'\n')
        # O processo isolado encerra QGIS; não toca nas preferências do usuário.


if __name__=='__main__':main()
