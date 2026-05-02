import os
import requests
import time

BASE_URL = "http://localhost:8000"
FAKE_DOCS_DIR = "Fake contracts and reports"
CONTRACT_ID = "EPC_NH44_KA03"

def upload_contract():
    print(f"--- Uploading Base Contract ---")
    file_path = os.path.join(FAKE_DOCS_DIR, "CONTRACT_EPC_NH44_KA03.docx")
    url = f"{BASE_URL}/upload-contract"
    
    with open(file_path, "rb") as f:
        files = {"file": ("CONTRACT_EPC_NH44_KA03.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {
            "contract_id": CONTRACT_ID,
            "contract_type": "EPC",
            "contract_value_inr": 1500000000.0,
            "scp_days": 730,
            "project_name": "NH44 Expansion Package KA-03",
            "location": "Karnataka",
            "contractor_name": "XYZ Constructions"
        }
        print("Sending request to /upload-contract (this may take a minute for LLM parsing)...")
        response = requests.post(url, files=files, data=data)
        
    if response.status_code == 200:
        print("[OK] Contract Uploaded Successfully!")
    else:
        print(f"[FAIL] Failed to upload contract. Status: {response.status_code}. See error_log.txt")
        with open("error_log.txt", "w", encoding="utf-8") as err_file:
            err_file.write(response.text)
        exit(1)

def upload_mpr(filename, prev_pct):
    print(f"\n--- Uploading MPR: {filename} ---")
    file_path = os.path.join(FAKE_DOCS_DIR, filename)
    url = f"{BASE_URL}/upload-mpr"
    
    with open(file_path, "rb") as f:
        files = {"file": (filename, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {
            "contract_id": CONTRACT_ID,
            "prev_actual_pct": prev_pct,
            "audience": "Project Manager"
        }
        print("Sending request to /upload-mpr...")
        response = requests.post(url, files=files, data=data)
        
    if response.status_code == 200:
        print("[OK] MPR Uploaded Successfully!")
        result = response.json()
        print(f"   Risk Score: {result.get('risk', {}).get('score')}")
        print(f"   Risk Label: {result.get('risk', {}).get('label')}")
        return result.get('parsed_mpr', {}).get('actual_physical_pct', 0.0)
    else:
        print(f"[FAIL] Failed to upload MPR: {response.text}")
        return prev_pct

def run():
    print("[START] Starting ContractGuard AI Demo Seeder\n")
    
    # 1. Upload Base Contract
    upload_contract()
    time.sleep(2)
    
    # 2. Upload MPRs chronologically
    mprs = [
        "MPR_A_ON_TRACK_Month3_Day91.docx",
        "MPR_D_VALID_FM_Month5_Day152_Flood.docx",
        "MPR_E_INVALID_FM_LateEoT_Month6_Day183.docx",
        "MPR_B_AT_RISK_Month7_Day214_M1Missed.docx",
        "MPR_C_DEFAULTING_Month14_Day426_LDCap62pct.docx",
        "MPR_F_NEAR_COMPLETE_Bonus_CatchUp_Month22.docx"
    ]
    
    prev_pct = 0.0
    for mpr in mprs:
        prev_pct = upload_mpr(mpr, prev_pct)
        time.sleep(1)
        
    print("\n[DONE] Demo Seeding Complete! Please check the React Dashboard.")

if __name__ == "__main__":
    run()
