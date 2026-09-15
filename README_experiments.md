# Linked motor-tree GW experiments

The visualizer contains the original Ti8–Ti9 comparison plus seven rotated/deformed Ti8 comparisons. The deformation study comprises **252 solver runs**: seven geometries, three node-order/initialization protocols, and 12 starts per protocol. Distance means `dGW = 0.5 sqrt(square-loss objective)`; source coordinate units are unverified.

| Experiment | Nodes | GW distance, native units |
|---|---|---|
| Original Ti8 vs Ti9 | 202 × 193 | 12.1623859094 (local optimum estimate) |
| Ti8 vs its 180° rotated duplicate | 202 × 202 | 7.342788 × 10⁻¹⁵ (zero up to roundoff) |

The **Experiment**, **Target order & initialization protocol**, and **GW initialization** selectors switch the actual matrices, skeletons, transport, labels, metrics, and linked interactions. The 5% bow with shuffled target rows opens by default. `index.html#original` opens the original comparison; `index.html#rotation` opens the rotation control. All original vertices are retained.

## Deformation, shuffling, and initialization study

The rotated duplicate has smooth bows applied to three disjoint branch regions, at nominal amplitudes of 2%, 5%, 10%, 20%, and 40% of subtree path length. The first two are mild; larger values deliberately stress recovery. A separate length-preserving bend changes 3D shape without changing the tree metric.

Best runs recover 100% of original-node correspondence mass at 2% and 5%, 98.02% at 10%, 91.58% at 20%, and 80.69% at 40%. Those are results for this synthetic Ti8 experiment, not general deformation thresholds. Random starts often do much worse. Consistently permuting the initial plans alongside the target produces identical unshuffled transports in all 84 matched comparisons.

Read [the detailed study report](deformation_study/README.md) and [summary CSV](deformation_study/summary.csv). The report distinguishes rotation/length invariance, ordering invariance, initialization failures, and the diagnostic cost of the known correspondence.

## Rotation control

Ti8 is duplicated and rotated **180° around the Z axis through its node centroid**. The exported rotated SWC is re-read to recompute both its adjacency and tree-distance matrices. The unchanged GW procedure recovers `T = I/202`: all 202 positive entries match the original nodes to the corresponding rotated nodes. The identity transport was not imposed or injected. Rotation preserves edge lengths and path distances, so the exact mathematical GW distance is zero.

The independent-product, root-distance, and mean-distance initializations recover the identity plan; the nine random starts remain in poorer local solutions. All run plans and loss histories are saved for inspection. See [the rotation report](rotation_180/README.md), [full rotation matrices](rotation_180/matrices.npz), and [rotated SWC](rotation_180/Ti8_rotated_180_z.swc).

## Interactive view

**External browser:** open [index.html](index.html) in Chrome (double-click or drag it into a browser tab). This complete standalone page embeds the data, theme, D3, Three.js, and controls; it works offline without Codex or a local server. All interaction checks are also run against the direct `file://` page with network access disabled, recorded in `checks/external-browser_check.json`.

The view includes complete 3D skeletons, every positive transport connector, both adjacency matrices, both distance matrices, and the full selected transport. Synthetic cases also show **Δ tree distance** and **Δ edge length**, aligned by known node identity to isolate deformation from row shuffling. Their alignment is an evaluation diagnostic, not an input to GW. The target matrix itself retains its selected shuffled order. All seven matrix views share node identity with the 3D view.

- Hover a matrix row label to select that node; a cell selects its row and column nodes. Related matrix rows/columns and 3D nodes update together.
- Hover a 3D node or connector to update the matrix highlights. A single-node selection also highlights its strongest transported counterpart; every positive incident transport remains visible.
- Click/tap a cell or a 3D node/connector to pin a selection; click it again to unpin. The two native node selectors also support keyboard selection and clearing.
- Drag the 3D view to rotate, scroll/pinch to zoom, and right-drag to pan.
- Separated layout independently centers and translates the trees with a common display scale and unchanged orientation. Native layout preserves their original relative coordinates. Neither layout changes the distance calculation or transport.
- Choose a different **GW initialization** to inspect the actual saved transport from that run. Incorrect synthetic-ID connectors have a separate color; selected connections use the shared highlight color.
- The comparison table summarizes the active ordering protocol across all seven geometries. Its experiment buttons switch the displayed case.

Line opacity reflects transport mass, with incorrect synthetic correspondences emphasized. The lines are structural correspondences, not synapses or validated biological homologies. Heatmaps share scales within the two distances and within the two adjacencies. Difference colors encode signed target-minus-source changes. Full-precision weighted edges reconstruct all tree distances in the browser; exported arrays retain float64 precision. Differences smaller than 1e-10 native units are shown as zero in the two difference plots to suppress numerical roundoff.

## Outputs

- [Methods, source identities, and numerical validation](README_compute.md)
- [Full matrices and transport, NumPy archive](matrices.npz)
- [Full transport CSV](transport.csv)
- [Ti8 adjacency](Ti8_weighted_adjacency.csv), [Ti9 adjacency](Ti9_weighted_adjacency.csv)
- [Ti8 tree distances](Ti8_tree_distance.csv), [Ti9 tree distances](Ti9_tree_distance.csv)
- [Independent computation audit](checks/independent_audit.json)
- [Interactive browser checks](checks/browser_check.json)
- [Deformation experiment audit](deformation_study/independent_verification.json)
- [Deformation visualizer checks](checks/deformation_browser_check.json)

## Rebuild the view

`python3 build_viewer.py` embeds the analyses, spatial renderer, and template into `build/viewer-fragment.html`. Shared trees are deduplicated, target shuffling is an explicit permutation, and sparse run plans are losslessly encoded. All source vertices remain present.

`python3 export_browser.py` builds the fragment and embeds the local theme and hash-checked JavaScript dependencies into the offline `index.html`. No network access or host application is required. Dependency versions and hashes are recorded in `browser_vendor/manifest.json`.
