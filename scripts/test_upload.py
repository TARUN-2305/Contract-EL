"""Test contract upload via the API."""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

client = httpx.Client(timeout=300.0)
with open('Fake contracts and reports/CONTRACT_EPC_NH44_KA03.docx', 'rb') as f:
    r = client.post(
        'http://127.0.0.1:8000/upload-contract',
        files={'file': ('CONTRACT_EPC_NH44_KA03.docx', f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')},
        data={
            'contract_id': 'CONTRACT_001',
            'contract_type': 'EPC',
            'contract_value_inr': '250000000',
            'scp_days': '730',
            'project_name': 'NH-44 Karnataka Road Widening',
            'location': 'NH-44, Karnataka'
        }
    )
print(r.status_code)
print(json.dumps(r.json(), indent=2))
