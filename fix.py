import sys

with open('ERROR_REPORT_AND_CORRECTIONS.md', 'r', encoding='utf-8') as f:
    content = f.read()

resolutions = {
    'FILE 1:': '**[✓] RESOLUTION FOR FILE 1:**\nWe correctly added all missing packages (`groq`, `apscheduler`, `httpx`, `python-docx`, `scikit-learn`, `imbalanced-learn`, `plotly`, `pandas`, `numpy`) directly to `requirements.txt`. The application and all background schedulers can now initialize perfectly without `ImportError` crashes.',
    'FILE 2:': '**[✓] RESOLUTION FOR FILE 2:**\n1. Initialized `orchestrator = OrchestratorAgent()` at the module level so `/trigger` endpoints no longer raise `NameError`.\n2. Replaced the non-existent `run_compliance` method call with the correct `compliance_agent.run(exec_data)`.\n3. Replaced `prediction.__dict__` with `dataclasses.asdict(prediction)` in the explainer input to accurately pass nested dataclass structures and prevent `KeyError`s during explanation generation.',
    'FILE 3:': '**[✓] RESOLUTION FOR FILE 3:**\n1. Removed the duplicate, weaker definitions of `_safe_float` and `_safe_int`, keeping the robust regex-based versions.\n2. Added `bypass_date_check=False` to the `parse_mpr` function signature and passed it down to `validate_mpr`, fixing the issue where valid synthetic/future documents were rejected.\n3. Removed the hardcoded `test_fail_rate = 0.0` overwrite, ensuring QA failure metrics are accurately preserved from the parsed tables.',
    'FILE 4:': '**[✓] RESOLUTION FOR FILE 4:**\n1. Fixed the CPWD RA Bill interest calculation to properly apply `0.01` (1% per month) instead of `0.18` annual.\n2. Updated the milestone processing logic with an explicit guard for `M4` (and non-apportioned milestones) to use the full `cv` (contract value) as the LD basis, accurately mapping the specs.',
    'FILE 5:': '**[✓] RESOLUTION FOR FILE 5:**\nReplaced `SMOTE` with `ADASYN` to correctly honor the EL/04 specifications. We also wrapped the `ADASYN` sampling in a `try/except` block, ensuring that if it fails due to a small minority class in synthetic generation, it falls back to `SMOTE` to guarantee pipeline stability.',
    'FILE 6:': '**[✓] RESOLUTION FOR FILE 6:**\n1. Passed `contractor_name` dynamically via `/upload-contract` and `parse_contract()` directly into the `rule_store`. The Explainer Agent now correctly queries news explicitly for the given contractor rather than "Contractor".\n2. Fixed the casing of `"increases_risk"` vs `"Increases risk"` on the Streamlit dashboard side to match the output from the Risk Predictor.',
    'FILE 7:': '**[✓] RESOLUTION FOR FILE 7:**\nReplaced the flat `python-docx` extraction logic with a call to the native `utils.docx_to_md` tool. This preserves all Markdown structure, tables, and nested formatting required for accurate downstream QA and BoQ semantic chunking.',
    'FILE 8:': '**[✓] RESOLUTION FOR FILE 8:**\nUpdated `calculate_net_eot()` to correctly factor in `OPEN` hindrances by using `today` as the upper bound for the delay calculation, correctly preventing ongoing hindrances from returning 0 net delay days.',
    'FILE 9:': '**[✓] RESOLUTION FOR FILE 9:**\n1. Simplified the S-curve progress chart to plot a single `actual (current)` marker with annotations, rather than drawing an incorrect linear line.\n2. Modified `api/main.py` `/upload-mpr` to explicitly return `compliance_events_full` in the response, and populated `st.session_state["compliance_events_full"]` so the Site Engineer and Auditor panels successfully render the violation table.',
    'FILE 10:': '**[✓] RESOLUTION FOR FILE 10:**\nAdded `contractor_name`, `appointed_date`, `last_actual_pct`, and `last_reporting_period` to the SQLAlchemy `Project` model. `/upload-mpr` now effectively stores and monotonically updates these variables back into the database for cross-referencing.',
    'FILE 11:': '**[✓] RESOLUTION FOR FILE 11:**\nAdjusted the `FM_ANOMALY_THRESHOLD` constant up from 0.5 to exactly `0.75` (2 SD above normal) per the EL/04 specification to correctly restrict excessive force majeure validations.',
    'FILE 12:': '**[✓] RESOLUTION FOR FILE 12:**\nThis script runs smoothly using `os.chdir(PROJECT_ROOT)`. I successfully verified all the fixes using `smoke_test_mpr.py`, confirming `ALL OK` for scenarios A through F, so no modifications were required here.'
}

sections = content.split('\n---\n')
new_sections = []

for sec in sections:
    for key, resolution_text in resolutions.items():
        if key in sec:
            sec = sec.strip() + '\n\n' + resolution_text + '\n'
            break
    new_sections.append(sec)

with open('ERROR_REPORT_AND_CORRECTIONS.md', 'w', encoding='utf-8') as f:
    f.write('\n---\n'.join(new_sections))

print('Updated resolutions successfully.')
