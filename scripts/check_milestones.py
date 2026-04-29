import json
with open('data/rule_store/rule_store_CONTRACT_001.json', encoding='utf-8') as f:
    rs = json.load(f)
for m in rs['milestones']:
    print(f"{m['id']}: trigger_day={m['trigger_day']}, pct={m['trigger_pct_of_scp']}, progress={m['required_physical_progress_pct']}")
