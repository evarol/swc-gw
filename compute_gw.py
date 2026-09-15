#!/usr/bin/env python3
"""Reproduce full-node weighted tree metrics and square-loss GW for Ti8/Ti9.

Run with Python 3.11+ and requirements.txt. All coordinates and lengths retain
the source's unverified native units. No sampling or arbor reduction is used.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import platform
import shutil
from pathlib import Path

import numpy as np
import ot
import scipy
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, shortest_path

OUT = Path(__file__).resolve().parent
REPO = OUT
SOURCE = OUT / "sources"
TARGETS = [("Ti8", "648518346477229768"), ("Ti9", "648518346494055054")]


def read_tsv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tree(label, root_id, crosswalk, inventory):
    geometry_id = "motor_" + root_id
    matches = [r for r in crosswalk if r["canonical_name"] == label and r["geometry_id"] == geometry_id]
    assert len(matches) == 1
    provenance = matches[0]
    assert provenance["cell_class"] == "motor"
    assert float(provenance["contributor_weight"]) == 1.0
    assert sum(r["canonical_name"] == label for r in crosswalk) == 1
    inv = next(r for r in inventory if r["geometry_id"] == geometry_id)
    path = SOURCE / (label + ".swc")
    actual_hash = sha256(path)
    assert actual_hash == inv["source_swc_sha256"] == provenance["source_swc_sha256"]
    records = []
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = raw.split()
        assert len(parts) == 7, raw
        node_id, node_type, x, y, z, radius, parent = parts
        records.append(dict(id=int(node_id), type=int(node_type), x=float(x), y=float(y), z=float(z), r=float(radius), parent=int(parent)))
    n = len(records)
    ids = [r["id"] for r in records]
    assert len(set(ids)) == n
    id_to_index = {v: i for i, v in enumerate(ids)}
    xyz = np.array([[r["x"], r["y"], r["z"]] for r in records], dtype=np.float64)
    radii = np.array([r["r"] for r in records])
    assert np.isfinite(xyz).all() and np.isfinite(radii).all() and (radii >= 0).all()
    roots = [i for i, r in enumerate(records) if r["parent"] == -1]
    assert len(roots) == 1
    adjacency = np.zeros((n, n), dtype=np.float64)
    edges = []
    for i, record in enumerate(records):
        if record["parent"] == -1:
            continue
        j = id_to_index[record["parent"]]
        assert i != j
        length = float(np.linalg.norm(xyz[i] - xyz[j]))
        assert length > 0, "Zero-length edges would require explicit sparse graph handling."
        adjacency[i, j] = adjacency[j, i] = length
        edges.append([i, j, length])
    assert len(edges) == n - 1
    graph = csr_matrix(adjacency)
    assert connected_components(graph, directed=False, return_labels=False) == 1
    distance = shortest_path(graph, directed=False, method="D")
    assert np.isfinite(distance).all()
    assert np.allclose(distance, distance.T, rtol=1e-14, atol=1e-12)
    assert np.all(np.diag(distance) == 0)
    assert np.allclose(distance[adjacency > 0], adjacency[adjacency > 0])
    degree = np.count_nonzero(adjacency, axis=1)
    mass = np.ones(n, dtype=np.float64) / n
    upper = np.asarray(distance[np.triu_indices(n, 1)], dtype="<f4")
    display_error = float(np.max(np.abs(upper.astype(np.float64) - distance[np.triu_indices(n, 1)])))
    payload = dict(label=label, rootId=root_id, geometryId=geometry_id, n=n,
                   nodes=records, edges=edges, masses=mass.tolist(), rootIndex=roots[0],
                   distanceUpperF32=base64.b64encode(upper.tobytes()).decode("ascii"),
                   distanceEncoding="strict upper triangle, row-major i<j; little-endian float32; implicit zero diagonal; mirror to lower triangle",
                   units="native coordinate units (unverified)",
                   stats=dict(nNodes=n, nEdges=len(edges), nRoots=1,
                              nLeaves=int(np.count_nonzero(degree == 1)),
                              nBranchPoints=int(np.count_nonzero(degree >= 3)),
                              totalCableLength=float(adjacency.sum() / 2),
                              diameter=float(distance.max()),
                              meanPairDistance=float(mass @ distance @ mass),
                              minEdgeLength=float(min(e[2] for e in edges)),
                              maxEdgeLength=float(max(e[2] for e in edges)),
                              displayDistanceMaxAbsError=display_error),
                   provenance=dict(sourcePath=str(path.relative_to(OUT)), sourceRelativePath=str(path.relative_to(REPO)),
                                   sourceSha256=actual_hash, originalFilename=inv["source_filename"],
                                   supervoxelId=inv["supervoxel_id"], mappingConfidence=provenance["mapping_confidence"],
                                   coordinateFrame=provenance["coordinate_frame"],
                                   completeness="all source SWC vertices retained; biological full-arbor completeness not independently verified"))
    (OUT / "sources").mkdir(exist_ok=True)
    # Input SWCs are already bundled under sources/.
    with (OUT / (label + "_nodes.csv")).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["matrix_index_0based", "id", "type", "x", "y", "z", "r", "parent", "mass"])
        writer.writeheader()
        for i, r in enumerate(records):
            writer.writerow(dict(matrix_index_0based=i, **r, mass=mass[i]))
    for suffix, matrix in [("weighted_adjacency", adjacency), ("tree_distance", distance)]:
        with (OUT / (label + "_" + suffix + ".csv")).open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["swc_node_id"] + ids)
            for node_id, row in zip(ids, matrix):
                writer.writerow([node_id] + row.tolist())
    return payload, adjacency, distance, mass, provenance, inv


def raw_objective(distance_a, distance_b, coupling, mass_a, mass_b):
    # Separable O(n^2*m+n*m^2) expression, independent of POT's log.
    return float(mass_a @ (distance_a ** 2) @ mass_a + mass_b @ (distance_b ** 2) @ mass_b
                 - 2 * np.sum((distance_a @ coupling @ distance_b.T) * coupling))


def support_objective(distance_a, distance_b, coupling):
    # Direct double sum over coupling support, avoiding a dense n*n*m*m tensor.
    ii, jj = np.where(coupling > 0)
    values = coupling[ii, jj]
    difference = distance_a[ii[:, None], ii[None, :]] - distance_b[jj[:, None], jj[None, :]]
    return float(np.sum(difference ** 2 * values[:, None] * values[None, :]))


def main():
    selected = json.loads((OUT / "selected_provenance.json").read_text())
    crosswalk = [entry["crosswalk"] for entry in selected]
    inventory = [entry["inventory"] for entry in selected]
    trees = [load_tree(label, root_id, crosswalk, inventory) for label, root_id in TARGETS]
    a, b = trees
    ca, cb, p, q = a[2], b[2], a[3], b[3]
    # One common positive rescaling preserves the minimizers and the size mismatch.
    scale = max(float(ca.max()), float(cb.max()))
    c1, c2 = ca / scale, cb / scale
    starts = [("independent_product", p[:, None] * q[None, :])]
    # Feasible plans from one-dimensional structural descriptors and random costs.
    for descriptor in ["root_distance", "mean_distance"]:
        v1 = c1[a[0]["rootIndex"]] if descriptor == "root_distance" else c1 @ p
        v2 = c2[b[0]["rootIndex"]] if descriptor == "root_distance" else c2 @ q
        starts.append((descriptor, ot.emd(p, q, (v1[:, None] - v2[None, :]) ** 2, numThreads=1)))
    for seed in range(9):
        rng = np.random.default_rng(seed)
        starts.append(("random_emd_seed_" + str(seed), ot.emd(p, q, rng.random((len(p), len(q))), numThreads=1)))
    runs = []
    candidates = []
    for name, initial in starts:
        assert np.max(np.abs(initial.sum(axis=1) - p)) < 1e-12
        assert np.max(np.abs(initial.sum(axis=0) - q)) < 1e-12
        coupling, log = ot.gromov.gromov_wasserstein(c1, c2, p, q, loss_fun="square_loss", symmetric=True,
                                                  G0=initial, log=True, armijo=False, max_iter=1000,
                                                  tol_rel=1e-12, tol_abs=1e-12, numThreads=1)
        objective = raw_objective(ca, cb, coupling, p, q)
        direct = support_objective(ca, cb, coupling)
        assert np.isclose(objective, direct, rtol=1e-11, atol=1e-8)
        assert np.isclose(objective, float(log["gw_dist"]) * scale ** 2, rtol=1e-10, atol=1e-8)
        row_error = float(np.max(np.abs(coupling.sum(axis=1) - p)))
        col_error = float(np.max(np.abs(coupling.sum(axis=0) - q)))
        assert min(coupling.ravel()) >= -1e-14 and max(row_error, col_error) < 1e-12
        losses = np.array(log["loss"], dtype=float)
        assert np.max(np.diff(losses)) <= 1e-10
        run = dict(initialization=name, objective=objective, dGW=0.5 * math.sqrt(max(0, objective)),
                   rmsDistortion=math.sqrt(max(0, objective)), iterations=len(losses) - 1,
                   finalScaledObjective=float(log["gw_dist"]), rowMarginalMaxError=row_error,
                   colMarginalMaxError=col_error, nNonzero=int(np.count_nonzero(coupling > 0)),
                   stoppedBeforeMaxIterations=len(losses) - 1 < 1000)
        runs.append(run)
        candidates.append(coupling)
        print(json.dumps(run), flush=True)
    best_index = int(np.argmin([r["objective"] for r in runs]))
    coupling = candidates[best_index]
    best = runs[best_index]
    ii, jj = np.where(coupling > 0)
    sparse = [dict(i=int(i), j=int(j), mass=float(coupling[i, j])) for i, j in zip(ii, jj)]
    const_c, h1, h2 = ot.gromov.init_matrix(c1, c2, p, q, "square_loss")
    gradient = ot.gromov.gwggrad(const_c, h1, h2, coupling)
    linear_minimizer = ot.emd(p, q, gradient, numThreads=1)
    stationarity_gap = float(np.sum(gradient * (coupling - linear_minimizer)))
    assert stationarity_gap >= -1e-10
    assert stationarity_gap < 1e-8
    diagonal_plan = np.diag(p)
    self_objective = raw_objective(ca, ca, diagonal_plan, p, p)
    assert abs(self_objective) < 1e-8
    payload = dict(schemaVersion=1,
                   title="Full-node motor neuron Gromov–Wasserstein comparison: Ti8 ↔ Ti9",
                   trees=[t[0] for t in trees],
                   gw=dict(**best, bestRunIndex=best_index, nStarts=len(runs), runs=runs,
                           coupling=sparse, p=p.tolist(), q=q.tolist(),
                           solver="POT ot.gromov.gromov_wasserstein, conditional gradient, unregularized square_loss",
                           weighting="uniform mass per original SWC node", distanceInput="weighted-tree shortest-path distances",
                           commonNumericalScale=scale, entropyRegularization=0,
                           objectiveFormula="sum_ijkl (D_A[i,k] - D_B[j,l])^2 T[i,j] T[k,l]",
                           distanceConvention="dGW = 0.5 * sqrt(objective); RMS structural distortion = sqrt(objective)",
                           units="native coordinate units (unverified); objective has squared units",
                           caveat="nonconvex local optimization; best of 12 feasible initializations, not a certified global minimum; uniform node masses depend on SWC sampling density",
                           scaledFrankWolfeGap=stationarity_gap,
                           selfIdentityObjective=self_objective,
                           maxIterations=1000, toleranceRelative=1e-12, toleranceAbsolute=1e-12),
                   method=dict(adjacency="symmetric: Euclidean parent–child segment length; zero for nonedges and diagonal",
                               distance="sum of segment lengths on the unique tree path; zero diagonal",
                               matrixOrder="source SWC file row order; node IDs exported without relabeling",
                               nodeReduction="none; all 202 and 193 original vertices retained",
                               coordinates="untransformed native XYZ; 3D layout adjustments affect display only"),
                   environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, POT=ot.__version__),
                   provenance=dict(selectedRecords="selected_provenance.json",
                                   selectedRecordsSha256=sha256(OUT / "selected_provenance.json"),
                                   motorReadme="sources/README.md"))
    (OUT / "analysis.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
    summary = {k: v for k, v in payload.items() if k != "trees"}
    summary["gw"] = {k: v for k, v in payload["gw"].items() if k not in ["coupling", "p", "q"]}
    summary["trees"] = [{k: v for k, v in t[0].items() if k not in ["nodes", "edges", "masses", "distanceUpperF32"]} for t in trees]
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    with (OUT / "transport.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Ti8_swc_node_id / Ti9_swc_node_id"] + [r["id"] for r in b[0]["nodes"]])
        for record, row in zip(a[0]["nodes"], coupling):
            writer.writerow([record["id"]] + row.tolist())
    with (OUT / "transport_sparse.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["i", "j", "mass"])
        writer.writeheader()
        writer.writerows(sparse)
    np.savez_compressed(OUT / "matrices.npz", adjacency_A=a[1], adjacency_B=b[1], distance_A=ca, distance_B=cb,
                        transport=coupling, mass_A=p, mass_B=q,
                        node_ids_A=np.array([r["id"] for r in a[0]["nodes"]], dtype=np.int64),
                        node_ids_B=np.array([r["id"] for r in b[0]["nodes"]], dtype=np.int64))
    (OUT / "selected_provenance.json").write_text(json.dumps([dict(crosswalk=t[4], inventory=t[5]) for t in trees], indent=2) + "\n")
    print("BEST", json.dumps(best), "PAYLOAD_BYTES", (OUT / "analysis.json").stat().st_size, flush=True)


if __name__ == "__main__":
    main()
