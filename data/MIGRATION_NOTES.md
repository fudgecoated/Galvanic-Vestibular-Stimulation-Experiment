# Data Migration Notes

Legacy paths were normalized into canonical locations:

- `Data Files/Raw Data Files/Arduino Data/*` -> `data/raw/arduino/*`
- `Data Files/Raw Data Files/Oculus Data/*` -> `data/raw/oculus/*`
- `Data Files/Raw Data Files/matlab data/*` -> `data/raw/force_plate/*`
- `Data Files/Formatted Data Files/Arduino Data/*` -> `data/interim/arduino/*`
- `Data Files/Formatted Data Files/matlab data/*` -> `data/interim/force_plate/*`
- `Data Files/ TA_COPPILOT_121625_01.mat` -> `data/raw/force_plate/TA_COPPILOT_121625_01.mat`
- `Data Files/ TA_COPPILOT_121625_2_01.mat` -> `data/raw/force_plate/TA_COPPILOT_121625_2_01.mat`
- `data/legacy_gvs_data_files/Raw Data Files/Oculus Data/.ipynb_checkpoints/*` -> `data/raw/oculus/.ipynb_checkpoints/*`

These are path-normalization moves only; file contents were not edited.
