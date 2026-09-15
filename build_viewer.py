"""Embed the audited full-node analysis in the linked visualization fragment."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'build' / 'viewer-fragment.html'

def main():
    fragment = (HERE / 'viewer_template.html').read_text()
    original=json.loads((HERE / 'analysis.json').read_text())
    # Distances are reconstructed from all weighted tree edges in the browser.
    # Deduplicate the common source and shuffled target geometries; no node reduction.
    def compact_tree(t):
        return {k:v for k,v in t.items() if k in ['label','nodes','edges','n','rootIndex','masses','units']}
    tree_pool={'source':compact_tree(original['trees'][0]),'ti9':compact_tree(original['trees'][1])}
    original['trees']=['source','ti9']
    experiments = [{'key':'original','label':'Ti8 vs Ti9 · original comparison','data':original}]
    rotation = HERE / 'rotation_180/analysis.json'
    study_path=HERE/'deformation_study/viewer_data.json'
    bundle={'experiments':experiments,'treePool':tree_pool}
    if study_path.exists():
        study=json.loads(study_path.read_text())
        bundle.update(studyPermutation=study['permutation'],affectedIndices=study['affectedIndices'],anchorIds=study['anchorIds'])
        for case in study['cases']:
            key=case['key'];case['tree']['label']='Ti8 180°' if key=='rotation' else 'Ti8 bent'
            tree_pool[key]=compact_tree(case['tree'])
            data={'trees':['source',key],'study':case['stats'],'orderVariants':case['protocols'],
                'gw':{'p':tree_pool['source']['masses'],'q':tree_pool[key]['masses'],'nStarts':12},'deformationLabel':case['label']}
            experiments.append({'key':key,'label':case['label']+' · Ti8 rotated target','data':data})
        bundle['defaultExperiment']='bend_05'
    elif rotation.exists():
        rot=json.loads(rotation.read_text());tree_pool['rotation']=compact_tree(rot['trees'][1]);rot['trees']=['source','rotation']
        experiments.append({'key':'rotation','label':'Ti8 vs Ti8 rotated 180° · rotation control','data':rot})
        bundle['defaultExperiment']='rotation'
    else:bundle['defaultExperiment']='original'
    fragment = fragment.replace('__PAYLOAD__', json.dumps(bundle,separators=(',',':'),ensure_ascii=False))
    fragment = fragment.replace('__SPATIAL_SCRIPT__', (HERE / 'spatial_view.js').read_text())
    assert '__PAYLOAD__' not in fragment and '__SPATIAL_SCRIPT__' not in fragment
    assert len(fragment.encode()) < 1_000_000
    assert '<html' not in fragment and '<!doctype' not in fragment.lower()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(fragment)
    print(f'{OUTPUT}: {OUTPUT.stat().st_size:,} bytes')

if __name__ == '__main__':
    main()
