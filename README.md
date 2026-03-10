# GVSE Repository Layout

This repository is organized into `docs`, `code`, `data`, `analysis`, and `results`.

- Keep raw data immutable in `data/raw`.
- Use `data/interim` for temporary cleaned or synchronized files.
- Use `data/processed` for analysis-ready datasets.
- Keep scripts and source code under `code/<modality>`.
- Store generated figures/tables in `results`.

## Legacy Migration
- Legacy Data Files moved to data/legacy_data_files/Data Files.
- Legacy matlab moved to nalysis/kinematics/matlab_legacy/matlab.
- Legacy GVS_Analysis_Dist moved to nalysis/reaching/gvs_analysis_dist_legacy/GVS_Analysis_Dist.

