# Source SWCs and attribution

`Ti8.swc` and `Ti9.swc` are unchanged selected motor-neuron skeletons from the existing Tony/FANC collection used in the connectionMiner motor-neuron dataset. This repository includes only those two source files and their recorded metadata, not the larger anatomical or transcriptomic dataset.

| Label | Recorded root ID | Original filename |
|---|---|---|
| Ti8 | 648518346477229768 | fanc_production_mar2021_left_t1_skel_72553200314029096.swc |
| Ti9 | 648518346494055054 | fanc_production_mar2021_left_t1_skel_72482831636691164.swc |

Exact source and anatomical crosswalk records are retained in `../selected_provenance.json`; hashes are checked before computation. Historical paths are recorded without the original workstation prefix. The source files are headerless and use unverified native coordinate units. All listed vertices are retained; biological full-arbor completeness has not been independently established.

Synthetic rotated/deformed files elsewhere in the repository are derived from Ti8. Source attribution and terms are inherited; this repository does not assert a new license for the SWCs.
