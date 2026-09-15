"""Same 12-start GW method on Ti8 and a genuine 180-degree rigid rotation."""
import base64
import copy
import csv
import json
from pathlib import Path

import numpy as np
import ot
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path

from compute_gw import support_objective, sha256

HERE = Path(__file__).resolve().parent
OUT = HERE / 'rotation_180'

def read_swc(path):
    records = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        i, t, x, y, z, r, parent = line.split()
        records.append(dict(id=int(i), type=int(t), x=float(x), y=float(y), z=float(z), r=float(r), parent=int(parent)))
    return records

def metrics(nodes):
    xyz = np.array([[r['x'], r['y'], r['z']] for r in nodes])
    index = {r['id']: i for i, r in enumerate(nodes)}
    a = np.zeros((len(nodes), len(nodes)))
    edges = []
    for i, r in enumerate(nodes):
        if r['parent'] == -1:
            continue
        j = index[r['parent']]
        w = float(np.linalg.norm(xyz[i] - xyz[j]))
        a[i, j] = a[j, i] = w
        edges.append([i, j, w])
    d = shortest_path(csr_matrix(a), directed=False, method='D')
    assert len(edges) == len(nodes) - 1 and np.isfinite(d).all()
    return a, d, edges

def write_matrix(name, a, ids):
    with (OUT / name).open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['SWC node ID'] + ids)
        for i, row in zip(ids, a):
            w.writerow([i] + row.tolist())

def main():
    OUT.mkdir(exist_ok=True)
    original = json.loads((HERE / 'analysis.json').read_text())
    source = HERE / 'sources/Ti8.swc'
    nodes_a = read_swc(source)
    xyz = np.array([[r['x'], r['y'], r['z']] for r in nodes_a])
    centroid = xyz.mean(axis=0)
    rotation = np.diag([-1., -1., 1.])
    rotated = (xyz - centroid) @ rotation.T + centroid
    swc = OUT / 'Ti8_rotated_180_z.swc'
    with swc.open('w') as f:
        f.write('# Ti8 duplicate rotated 180 degrees around Z through its node centroid.\n')
        f.write('# Native coordinate units unverified; all node IDs and parent IDs retained.\n')
        for r, pos in zip(nodes_a, rotated):
            f.write(f"{r['id']} {r['type']} {pos[0]:.17g} {pos[1]:.17g} {pos[2]:.17g} {r['r']:.17g} {r['parent']}\n")
    # Re-read the actual exported SWC; derive both adjacency and distance anew.
    nodes_b = read_swc(swc)
    aa, da, ea = metrics(nodes_a)
    ab, db, eb = metrics(nodes_b)
    n = len(nodes_a)
    p = np.ones(n) / n
    scale = max(da.max(), db.max())
    c1, c2 = da / scale, db / scale
    root = original['trees'][0]['rootIndex']
    starts = [('independent_product', np.outer(p, p))]
    for name in ['root_distance', 'mean_distance']:
        v1 = c1[root] if name == 'root_distance' else c1 @ p
        v2 = c2[root] if name == 'root_distance' else c2 @ p
        starts.append((name, ot.emd(p, p, (v1[:, None] - v2[None, :]) ** 2, numThreads=1)))
    for seed in range(9):
        costs = np.random.default_rng(seed).random((n, n))
        starts.append((f'random_emd_seed_{seed}', ot.emd(p, p, costs, numThreads=1)))
    runs, plans, histories = [], [], []
    for name, initial in starts:
        t, log = ot.gromov.gromov_wasserstein(c1, c2, p, p, loss_fun='square_loss', symmetric=True,
            G0=initial, log=True, armijo=False, max_iter=1000, tol_rel=1e-12, tol_abs=1e-12, numThreads=1)
        # Direct nonnegative sum is stable near zero; subtractive expansion cancels.
        loss = support_objective(da, db, t)
        row_error, col_error = np.max(np.abs(t.sum(1) - p)), np.max(np.abs(t.sum(0) - p))
        assert np.min(t) >= 0 and max(row_error, col_error) < 1e-12
        assert abs(loss - float(log['gw_dist']) * scale ** 2) < 1e-8
        assert np.max(np.diff(log['loss'])) < 1e-10
        run = dict(initialization=name, objective=loss, dGW=float(.5 * np.sqrt(loss)), rmsDistortion=float(np.sqrt(loss)),
            iterations=len(log['loss'])-1, finalScaledObjective=float(log['gw_dist']), rowMarginalMaxError=float(row_error),
            colMarginalMaxError=float(col_error), nNonzero=int(np.count_nonzero(t)), stoppedBeforeMaxIterations=len(log['loss'])-1<1000,
            matchedIdMass=float(np.trace(t)))
        runs.append(run); plans.append(t); histories.append([float(v) for v in log['loss']])
        print(json.dumps(run), flush=True)
    best = int(np.argmin([r['objective'] for r in runs]))
    t = plans[best]
    identity_objective = support_objective(da, db, np.diag(p))
    report = dict(rotationDegrees=180, axis='Z', centerDefinition='arithmetic mean of all original node coordinates',
        centroid=centroid.tolist(), rotationMatrix=rotation.tolist(), coordinateFormula='XYZ_B = (XYZ_A - centroid) @ R.T + centroid',
        maxAdjacencyDifference=float(np.max(abs(aa-ab))), maxTreeDistanceDifference=float(np.max(abs(da-db))),
        identityObjective=identity_objective, identityDistance=float(.5*np.sqrt(identity_objective)),
        matchedIdMass=float(np.trace(t)), maxIdentityTransportDifference=float(np.max(abs(t-np.diag(p)))),
        sourceSha256=sha256(source), rotatedSwcSha256=sha256(swc), nodesRetained=n,
        method='Same uniform masses, tree distances, 12 feasible initializations, loss, solver, scaling and tolerances as Ti8/Ti9. No imposed node-ID correspondence.',
        interpretation='Rigid rotation preserves segment lengths and tree distances: exact GW is zero. Numeric residuals are floating-point roundoff. The reported transport is solver output, not an injected identity plan.')
    assert report['maxTreeDistanceDifference'] < 1e-10
    assert runs[best]['dGW'] < 1e-10 and report['maxIdentityTransportDifference'] < 1e-12
    assert np.array_equal([r['id'] for r in nodes_a], [r['id'] for r in nodes_b])
    assert np.array_equal([r['parent'] for r in nodes_a], [r['parent'] for r in nodes_b])
    trees = []
    for label, nodes, edges, distance in [('Ti8',nodes_a,ea,da), ('Ti8 180°',nodes_b,eb,db)]:
        tree = copy.deepcopy(original['trees'][0])
        tree.update(label=label,nodes=nodes,edges=edges,distanceUpperF32=base64.b64encode(np.asarray(distance[np.triu_indices(n,1)],dtype='<f4').tobytes()).decode())
        tree['provenance']['experiment'] = 'Original Ti8' if label=='Ti8' else 'Synthetic 180-degree Z rotation of Ti8 about centroid'
        if label!='Ti8':
            tree['provenance']['sourcePath']=str(swc.relative_to(HERE))
            tree['provenance']['sourceRelativePath']=str(swc.relative_to(HERE))
            tree['provenance']['sourceSha256']=sha256(swc)
            tree['provenance']['originalFilename']=swc.name
            tree['provenance']['coordinateFrame']='Synthetic rotation in source native frame'
        trees.append(tree)
    ii,jj = np.where(t>0)
    gw = {k:copy.deepcopy(v) for k,v in original['gw'].items() if k not in ['coupling','runs']}
    gw.update(runs[best],bestRunIndex=best,nStarts=len(runs),runs=runs,p=p.tolist(),q=p.tolist(),
        coupling=[dict(i=int(i),j=int(j),mass=float(t[i,j])) for i,j in zip(ii,jj)], commonNumericalScale=float(scale),
        selfIdentityObjective=identity_objective,caveat='Rotation invariance gives an analytic exact distance of zero; numerical residual is roundoff.')
    const,h1,h2=ot.gromov.init_matrix(c1,c2,p,p,'square_loss')
    gradient=ot.gromov.gwggrad(const,h1,h2,t)
    gw['scaledFrankWolfeGap']=float(np.sum(gradient*(t-ot.emd(p,p,gradient,numThreads=1))))
    payload=copy.deepcopy(original)
    payload.update(title='Ti8 vs its 180-degree rotated duplicate',trees=trees,gw=gw,rotation=report)
    payload['method'].update(nodeReduction='none; all 202 source nodes retained in each tree',coordinates=report['coordinateFormula'])
    (OUT/'analysis.json').write_text(json.dumps(payload,separators=(',',':'),allow_nan=False))
    (OUT/'verification.json').write_text(json.dumps(report,indent=2))
    (OUT/'runs.json').write_text(json.dumps({'runs':runs,'lossHistories':histories,'bestRunIndex':best},indent=2))
    np.savez_compressed(OUT/'matrices.npz',adjacency_A=aa,adjacency_B=ab,distance_A=da,distance_B=db,transport=t,mass_A=p,mass_B=p,
        coordinates_A=xyz,coordinates_B=rotated,rotation_matrix=rotation,rotation_center=centroid,
        node_ids_A=np.array([r['id'] for r in nodes_a]),node_ids_B=np.array([r['id'] for r in nodes_b]),all_run_transports=np.stack(plans))
    ids=[r['id'] for r in nodes_a]
    for name,array in [('Ti8_weighted_adjacency',aa),('Ti8_rotated_weighted_adjacency',ab),('Ti8_tree_distance',da),('Ti8_rotated_tree_distance',db),('transport',t)]:
        write_matrix(name+'.csv',array,ids)
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
