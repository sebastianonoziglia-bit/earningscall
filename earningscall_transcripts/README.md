# Earnings Call Transcripts

Folder layout:

`earningscall_transcripts/<Company>/<YYYY>/Q<1-4>.txt`

Examples:

- `earningscall_transcripts/Apple/2024/Q4.txt`
- `earningscall_transcripts/Meta_Platforms/2025/Q1.txt`

Generated metadata files:

- `transcript_index.csv`: one row per transcript file
- `company_summary.csv`: coverage summary by company
- `coverage_gaps.csv`: missing quarter map by company/year

Rebuild metadata after adding new transcripts:

```bash
python3 scripts/rebuild_transcript_index.py
```
