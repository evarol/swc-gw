"""Branch deformation, target permutation, and GW initialization experiment."""
import base64
import copy
import csv
import json
from pathlib import Path

import numpy as np
import ot
from compute_rotation import read_swc, metrics
from compute_gw import support_objective, sha256

HERE = Path(__file__).resolve().parent
OUT = HERE / 'deformation_study'
PROTOCOLS = [('ordered','Original order'),('shuffled_matched','Shuffled · matched initial plans'),('shuffled_fresh','Shuffled · fresh initial plans')]
CASES = [('rotation','Rotation only',0.,False),('bend_isometric','Bend only · lengths preserved',0.,True),
         ('bend_02','Mild bow · 2%',.02,False),('bend_05','Mild bow · 5%',.05,False),
         ('bend_10','Moderate bow · 10%',.10,False),('bend_20','Strong bow · 20%',.20,False),
         ('bend_40','Stress test · 40%',.40,False)]

def sparse_plan(t):
    n=len(t);cols=t.argmax(1)
    if len(np.unique(cols))==n and np.count_nonzero(t)==n and np.array_equal(t[np.arange(n),cols],np.full(n,1/n)):
        return dict(permutation=cols.tolist())
    ii,jj=np.nonzero(t)
    return dict(entries=[[int(i),int(j),float(t[i,j])] for i,j in zip(ii,jj)])

def starts_for(a,b,p,root_a,root_b):
    starts=[('independent_product',np.outer(p,p))]
    for name in ['root_distance','mean_distance']:
        x=a[root_a] if name=='root_distance' else a@p
        y=b[root_b] if name=='root_distance' else b@p
        starts.append((name,ot.emd(p,p,(x[:,None]-y[None,:])**2,numThreads=1)))
    for seed in range(9):
        starts.append((f'random_emd_seed_{seed}',ot.emd(p,p,np.random.default_rng(seed).random(a.shape),numThreads=1)))
    return starts

def main():
    OUT.mkdir(exist_ok=True)
    original=json.loads((HERE/'analysis.json').read_text())
    source=read_swc(HERE/'sources/Ti8.swc')
    rotated_nodes=read_swc(HERE/'rotation_180/Ti8_rotated_180_z.swc')
    xyz=np.array([[r['x'],r['y'],r['z']] for r in rotated_nodes])
    aa,da,edges=metrics(source);n=len(source);p=np.ones(n)/n
    children=[[] for _ in source];parents=np.full(n,-1,dtype=int)
    for i,j,_ in edges:children[j].append(i);parents[i]=j
    def descendants(i):return [i]+sum((descendants(j) for j in children[i]),[])
    anchors=[23,81,163]
    subtrees=[descendants(i) for i in anchors]
    assert sum(map(len,subtrees))==len(set(sum(subtrees,[]))), 'Selected branches overlap'
    affected=sorted(set(sum(subtrees,[]))-set(anchors))
    perm=np.random.default_rng(20260915).permutation(n);inverse=np.argsort(perm)
    root=int(np.flatnonzero(parents<0)[0])
    directions=[];lengths=[]
    for anchor,subtree in zip(anchors,subtrees):
        far=subtree[int(np.argmax(da[anchor,subtree]))]
        direction=xyz[far]-xyz[anchor];direction/=np.linalg.norm(direction)
        ref=np.array([0.,0.,1.]) if abs(direction[2])<.9 else np.array([0.,1.,0.])
        perpendicular=np.cross(direction,ref);perpendicular/=np.linalg.norm(perpendicular)
        directions.append(perpendicular);lengths.append(float(da[anchor,far]))
    report=dict(sourceSha256=sha256(HERE/'sources/Ti8.swc'),nNodes=n,branchAnchorIds=anchors,
        affectedNodeIndices=affected,subtrees=subtrees,branchPathLengths=lengths,bendDirections=[d.tolist() for d in directions],
        shuffleSeed=20260915,targetPermutation=perm.tolist(),protocols=dict(PROTOCOLS),cases=[],
        deformationFormula='For each selected subtree: X_new = X_rotated + amplitude * L * sin(pi*s/L)^2 * u, where s is tree distance from fixed anchor, L=max s, u is transverse direction.',
        lengthPreservingControl='Traverse each selected subtree, rebuilding each edge with unchanged length but a Z-axis rotation angle 35 degrees * child path distance / L; anchors fixed.',
        evaluation='True original node identities are used only for diagnostics and aligning difference matrices; never passed as matching costs or constraints.',
        permutationControl='Matched protocol applies the identical target-column permutation to every initial coupling. Fresh protocol regenerates the original seeds in shuffled index order, changing the physical meaning of random starts.')
    view_cases=[]
    for key,label,amplitude,isometric in CASES:
        case_dir=OUT/key;case_dir.mkdir(exist_ok=True)
        bent=xyz.copy()
        for anchor,subtree,u,length in zip(anchors,subtrees,directions,lengths):
            if isometric:
                for i in subtree[1:]:
                    j=parents[i];angle=np.deg2rad(35)*da[anchor,i]/length
                    c,s=np.cos(angle),np.sin(angle)
                    r=np.array([[c,-s,0],[s,c,0],[0,0,1]])
                    bent[i]=bent[j]+r@(xyz[i]-xyz[j])
            else:
                f=amplitude*length*np.sin(np.pi*da[anchor,subtree]/length)**2
                bent[subtree]=xyz[subtree]+f[:,None]*u
        nodes=copy.deepcopy(rotated_nodes)
        for rec,pos in zip(nodes,bent):rec.update(x=float(pos[0]),y=float(pos[1]),z=float(pos[2]))
        paths=[]
        for order,indices in [('ordered',np.arange(n)),('shuffled',perm)]:
            path=case_dir/f'Ti8_{key}_{order}.swc'
            with path.open('w') as f:
                f.write(f'# Synthetic Ti8: 180-degree Z rotation, {label}; {order} file row order.\n')
                for i in indices:
                    r=nodes[i];f.write(f"{r['id']} {r['type']} {r['x']:.17g} {r['y']:.17g} {r['z']:.17g} {r['r']:.17g} {r['parent']}\n")
            paths.append(path)
        # Recompute from written source, then use its exact matrix permutation for
        # ordering control; independently check shuffled SWC reconstruction agrees.
        nodes=read_swc(paths[0]);ab,db,target_edges=metrics(nodes)
        a_shuf,d_shuf,_=metrics(read_swc(paths[1]))
        assert np.array_equal(a_shuf,ab[np.ix_(perm,perm)])
        assert np.max(abs(d_shuf-db[np.ix_(perm,perm)]))<1e-10
        delta_d=db-da;delta_a=ab-aa
        active=aa>0;strain=ab[active]/aa[active]-1
        stats=dict(amplitude=amplitude,lengthPreserving=isometric,maxDisplacement=float(np.linalg.norm(bent-xyz,axis=1).max()),
            rmsDisplacement=float(np.sqrt(np.mean(np.sum((bent-xyz)**2,axis=1)))),maxAdjacencyDifference=float(abs(delta_a).max()),
            maxTreeDistanceDifference=float(abs(delta_d).max()),rmsTreeDistanceDifference=float(np.sqrt(np.mean(delta_d**2))),
            relativeMetricChange=float(np.linalg.norm(delta_d)/np.linalg.norm(da)),maxRelativeEdgeChange=float(abs(strain).max()),
            edgeStrainMin=float(strain.min()),edgeStrainMax=float(strain.max()),affectedNodeCount=len(affected),
            sourceFile=str(paths[0].relative_to(HERE)),shuffledFile=str(paths[1].relative_to(HERE)),
            sourceSha256=sha256(paths[0]),shuffledSha256=sha256(paths[1]))
        stats['trueCorrespondenceGW']=.5*stats['rmsTreeDistanceDifference']
        if amplitude==0:assert stats['maxTreeDistanceDifference']<1e-10
        scale=float(max(da.max(),db.max()));c1=da/scale;c2=db/scale
        base_starts=starts_for(c1,c2,p,root,root)
        protocols=[];all_plans=[];all_initials=[];all_histories=[]
        for protocol,protocol_label in PROTOCOLS:
            order=np.arange(n) if protocol=='ordered' else perm
            truth=np.argsort(order)
            cb=db[np.ix_(order,order)];c2_use=cb/scale
            starts=base_starts if protocol=='ordered' else [(name,t[:,perm]) for name,t in base_starts] if protocol=='shuffled_matched' else starts_for(c1,c2_use,p,root,int(inverse[root]))
            runs=[];plans=[];initials=[];histories=[]
            for name,g0 in starts:
                t,log=ot.gromov.gromov_wasserstein(c1,c2_use,p,p,loss_fun='square_loss',symmetric=True,G0=g0,log=True,
                    armijo=False,max_iter=1000,tol_rel=1e-12,tol_abs=1e-12,numThreads=1)
                assert np.count_nonzero(t)<3000
                loss=support_objective(da,cb,t)
                assert abs(loss-float(log['gw_dist'])*scale**2)<1e-7
                assert np.max(np.diff(log['loss']))<1e-10
                marginal_error=float(max(np.max(abs(t.sum(1)-p)),np.max(abs(t.sum(0)-p))))
                assert np.min(t)>=0 and marginal_error<1e-12
                correct=t[np.arange(n),truth]
                matchmass=float(correct.sum());affectedmass=float(correct[affected].sum()/(len(affected)/n))
                prediction=t.argmax(1)
                run=dict(initialization=name,objective=loss,dGW=float(.5*np.sqrt(loss)),iterations=len(log['loss'])-1,
                    matchedIdMass=matchmass,affectedMatchedMass=affectedmass,argmaxAccuracy=float(np.mean(prediction==truth)),
                    meanCorrespondencePathError=float(np.sum(t*da[:,order])),maxMarginalError=marginal_error,
                    nNonzero=int(np.count_nonzero(t)),finalScaledObjective=float(log['gw_dist']),plan=sparse_plan(t))
                runs.append(run);plans.append(t);initials.append(g0);histories.append([float(x) for x in log['loss']])
            best=int(np.argmin([r['objective'] for r in runs]))
            protocols.append(dict(key=protocol,label=protocol_label,bestRunIndex=best,runs=runs))
            all_plans.append(plans);all_initials.append(initials);all_histories.append(histories)
            print(json.dumps(dict(case=key,protocol=protocol,best=runs[best]['dGW'],bestMatch=runs[best]['matchedIdMass'],
                affectedMatch=runs[best]['affectedMatchedMass'],worstGW=max(r['dGW'] for r in runs))),flush=True)
        plans_np=np.asarray(all_plans)
        equivariance=[dict(initialization=base_starts[k][0],maxPlanDifference=float(np.max(abs(plans_np[0,k]-plans_np[1,k][:,inverse]))),
            distanceDifference=abs(protocols[0]['runs'][k]['dGW']-protocols[1]['runs'][k]['dGW']),
            initialPlanDifference=float(np.max(abs(all_initials[0][k]-all_initials[1][k][:,inverse])))) for k in range(12)]
        stats['maxMatchedStartPlanDifference']=max(r['maxPlanDifference'] for r in equivariance)
        stats['maxMatchedStartDistanceDifference']=max(r['distanceDifference'] for r in equivariance)
        assert max(r['initialPlanDifference'] for r in equivariance)==0
        np.savez_compressed(case_dir/'matrices.npz',adjacency_A=aa,adjacency_B=ab,distance_A=da,distance_B=db,
            delta_adjacency=delta_a,delta_distance=delta_d,coordinates_A=np.array([[r['x'],r['y'],r['z']] for r in source]),
            coordinates_B=bent,node_ids=np.array([r['id'] for r in source]),permutation=perm,mass=p,
            all_transports=plans_np,all_initial_plans=np.asarray(all_initials),affected_indices=np.array(affected))
        for suffix,array in [('delta_adjacency',delta_a),('delta_distance',delta_d),('target_adjacency',ab),('target_distance',db)]:
            with (case_dir/(suffix+'.csv')).open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['source node ID']+[r['id'] for r in source]);
                for r,row in zip(source,array):w.writerow([r['id']]+row.tolist())
        (case_dir/'runs.json').write_text(json.dumps(dict(protocols=protocols,lossHistories=all_histories,equivariance=equivariance),indent=2))
        tree=dict(label='Ti8 target',nodes=nodes,edges=target_edges,n=n,rootIndex=root,masses=p.tolist(),units=original['trees'][0]['units'])
        view_cases.append(dict(key=key,label=label,tree=tree,stats=stats,protocols=protocols))
        report['cases'].append(dict(key=key,label=label,stats=stats,protocols=[dict(key=pr['key'],bestRunIndex=pr['bestRunIndex'],
            runs=[{k:v for k,v in r.items() if k!='plan'} for r in pr['runs']]) for pr in protocols],equivariance=equivariance))
    (OUT/'viewer_data.json').write_text(json.dumps(dict(cases=view_cases,permutation=perm.tolist(),affectedIndices=affected,anchorIds=anchors),separators=(',',':')))
    (OUT/'report.json').write_text(json.dumps(report,indent=2))
    print('Complete: 7 geometries × 3 ordering protocols × 12 starts = 252 GW runs.',flush=True)

if __name__=='__main__':main()
