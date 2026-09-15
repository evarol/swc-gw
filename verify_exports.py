#!/usr/bin/env python3
"""Check artifact boundary precision, node ordering, hashes and transport."""
import base64
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

out = Path(__file__).resolve().parent
payload = json.loads((out / "analysis.json").read_text())
arrays = np.load(out / "matrices.npz")
checks = {}
for tree, suffix in zip(payload["trees"], ["A", "B"]):
    n, label = tree["n"], tree["label"]
    upper = np.frombuffer(base64.b64decode(tree["distanceUpperF32"]), dtype="<f4")
    assert len(upper) == n * (n - 1) // 2
    restored = np.zeros((n, n))
    restored[np.triu_indices(n, 1)] = upper
    restored += restored.T
    error = float(np.max(np.abs(restored - arrays["distance_" + suffix])))
    assert error <= 8e-6
    assert np.isclose(error, tree["stats"]["displayDistanceMaxAbsError"])
    adjacency = np.zeros((n, n))
    for i, j, length in tree["edges"]:
        adjacency[i, j] = adjacency[j, i] = length
    assert np.array_equal(adjacency, arrays["adjacency_" + suffix])
    assert np.array_equal(np.array(tree["masses"]), arrays["mass_" + suffix])
    assert np.array_equal(np.array([r["id"] for r in tree["nodes"]]), arrays["node_ids_" + suffix])
    source = out / "sources" / (label + ".swc")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == tree["provenance"]["sourceSha256"]
    with (out / (label + "_nodes.csv")).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == n
    for i, (node, row) in enumerate(zip(tree["nodes"], rows)):
        assert int(row["matrix_index_0based"]) == i
        for key in ["id", "type", "parent"]:
            assert int(row[key]) == node[key]
        for key in ["x", "y", "z", "r"]:
            assert float(row[key]) == node[key]
        assert float(row["mass"]) == tree["masses"][i]
    for file_label, array_label in [("weighted_adjacency", "adjacency"), ("tree_distance", "distance")]:
        with (out / (label + "_" + file_label + ".csv")).open() as stream:
            rows = list(csv.reader(stream))
        assert [int(x) for x in rows[0][1:]] == [r["id"] for r in tree["nodes"]]
        assert [int(x[0]) for x in rows[1:]] == [r["id"] for r in tree["nodes"]]
        assert np.array_equal(np.array([r[1:] for r in rows[1:]], dtype=float), arrays[array_label + "_" + suffix])
    checks[label] = dict(nNodes=n, nEdges=len(tree["edges"]), allNodesRetained=True,
                         sourceHashMatched=True, adjacencyRoundtripExact=True,
                         csvRoundtripsExact=True, displayDistanceMaxAbsError=error)
t = np.zeros_like(arrays["transport"])
for item in payload["gw"]["coupling"]:
    t[item["i"], item["j"]] = item["mass"]
assert np.array_equal(t, arrays["transport"])
with (out / "transport.csv").open() as stream:
    rows = list(csv.reader(stream))
assert np.array_equal(np.array([r[1:] for r in rows[1:]], dtype=float), t)
assert [int(x) for x in rows[0][1:]] == arrays["node_ids_B"].tolist()
assert [int(r[0]) for r in rows[1:]] == arrays["node_ids_A"].tolist()
row_error = float(np.max(np.abs(t.sum(axis=1) - arrays["mass_A"])))
col_error = float(np.max(np.abs(t.sum(axis=0) - arrays["mass_B"])))
assert max(row_error, col_error) < 1e-12
ii, jj = np.nonzero(t)
w = t[ii, jj]
distortion = arrays["distance_A"][ii[:, None], ii[None, :]] - arrays["distance_B"][jj[:, None], jj[None, :]]
objective = float(np.sum(distortion ** 2 * w[:, None] * w[None, :]))
assert np.isclose(objective, payload["gw"]["objective"], rtol=1e-12, atol=1e-8)
checks["transport"] = dict(shape=list(t.shape), nonzeroCount=len(ii), sparseRoundtripExact=True,
                           csvRoundtripExact=True, totalMass=float(t.sum()), rowMarginalMaxError=row_error,
                           columnMarginalMaxError=col_error, independentlyRecomputedObjective=objective)
checks["passed"] = True
(out / "verification.json").write_text(json.dumps(checks, indent=2) + "\n")
print(json.dumps(checks, indent=2))
