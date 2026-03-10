# GVSE Repository Layout

This repository is organized into `docs`, `code`, `data`, `analysis`, and `results`.

- Keep raw data immutable in `data/raw`.
- Use `data/interim` for temporary cleaned or synchronized files.
- Use `data/processed` for analysis-ready datasets.
- Keep scripts and source code under `code/<modality>`.
- Store generated figures/tables in `results`.

## Trial Randomization
- Install the experiment-script dependency with `.\.venv\Scripts\pip install -r .\code\experiment\requirements.txt`.
- Run the generator with `.\code\experiment\run_trial_randomizer.bat`.
- Output PDFs are written to `results/trial_orders`.

## Legacy Migration
- Legacy Data Files moved to data/legacy_data_files/Data Files.
- Legacy matlab moved to nalysis/kinematics/matlab_legacy/matlab.
- Legacy GVS_Analysis_Dist moved to nalysis/reaching/gvs_analysis_dist_legacy/GVS_Analysis_Dist.

