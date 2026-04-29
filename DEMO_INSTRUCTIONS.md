# ContractGuard AI — Manual Demonstration Catalogue
## Step-by-Step Instructions for All 5 Persona Scenarios

> **Both servers must be running before you start.**
> - API:       http://localhost:8000
> - Dashboard: http://localhost:8501
>
> If they are not running, open two PowerShell terminals in the project folder and run:
> ```
> # Terminal 1 — API
> .\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
>
> # Terminal 2 — Dashboard
> .\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.port 8501
> ```

---

## 📁 Test File Location
All `.docx` scenario files are in:
```
C:\Users\tarun\.gemini\antigravity\scratch\Main_EL_Contract_Guard\Fake contracts and reports\
```

| File | Scenario | Key Signal |
|------|----------|------------|
| `MPR_A_ON_TRACK_Month3_Day91.docx` | A — On Track | Day 91, Actual 13.1%, Labour 103%, 0 NCRs |
| `MPR_B_AT_RISK_Month7_Day214_M1Missed.docx` | B — At Risk | Day 214, Actual 18.4% vs Planned 29.3%, Milestone 1 missed |
| `MPR_C_DEFAULTING_Month14_Day426_LDCap62pct.docx` | C — Defaulting | Day 426, Actual 34.2%, Labour 36.5%, 7 NCRs, 42d payment delay |
| `MPR_D_VALID_FM_Month5_Day152_Flood.docx` | D — Valid FM | Day 152, 512mm rainfall, EoT justified |
| `MPR_E_INVALID_FM_LateEoT_Month6_Day183.docx` | E — Invalid FM | Day 183, 384mm rainfall, EoT submitted late |
| `MPR_F_NEAR_COMPLETE_Bonus_CatchUp_Month22.docx` | F — Near Complete | Day 672, Actual 97.8%, Bonus eligible |

---

## 🎭 PERSONA 1 — Contract Manager (Scenario C: Defaulting)

**Goal:** Show a contract manager how the system flags a severely delayed contract approaching LD cap.

### Steps:
1. Open browser → go to **http://localhost:8501**
2. Wait for the dashboard to fully load (sidebar should show "ContractGuard AI")
3. **Sidebar — Role:** Click the role dropdown → Select **"Contract Manager"**
4. **Sidebar — Contract ID:** Clear the field → Type: `NHAI/KA/EPC/2025/KA-03`
5. Scroll down to the **"📊 MPR Compliance Analysis"** section
6. Click **"Browse files"** (the file uploader)
7. Navigate to: `Fake contracts and reports\` → Select **`MPR_C_DEFAULTING_Month14_Day426_LDCap62pct.docx`**
8. Leave **"Previous Month Actual Progress"** = `0.0`
9. Click **"🔍 Run Full Analysis"**
10. ⏳ Wait 30–90 seconds for the Groq LLM to respond
11. 📸 **Screenshot 1:** The 4 metric tiles (Risk Score, Compliance Events, LD Accrued, Time to Default)
12. 📸 **Screenshot 2:** The S-Curve chart (large gap between planned and actual lines)
13. 📸 **Screenshot 3:** The SHAP bar chart (top risk drivers in red = labour, NCRs, payment delay)
14. 📸 **Screenshot 4:** Expand "📄 Compliance Report Preview" → screenshot the AI narrative

**What to expect:**
- Risk Score: HIGH (≥ 0.7)
- Compliance Events: Multiple CRITICAL
- LD Accrued: Significant (close to cap)
- S-Curve: Actual far below planned at Day 426
- SHAP: Labour utilisation (36.5%) and NCRs (7) as top drivers

---

## 🎭 PERSONA 2 — Project Manager (Scenario B: At Risk)

**Goal:** Show a project manager the early warning system catching a missed milestone.

### Steps:
1. **Sidebar — Role:** Change to **"Project Manager"**
2. Scroll to the **MPR Upload** section
3. Click **"Browse files"** → Select **`MPR_B_AT_RISK_Month7_Day214_M1Missed.docx`**
4. Leave **Previous Month Actual Progress** = `0.0`
5. Click **"🔍 Run Full Analysis"**
6. ⏳ Wait 30–90 seconds
7. 📸 **Screenshot 5:** Metric tiles (note the variance: Planned 29.3% vs Actual 18.4%)
8. 📸 **Screenshot 6:** S-Curve showing divergence at Day 214 (today's marker vs SCD line)
9. 📸 **Screenshot 7:** SHAP chart highlighting payment delay (18 days) and GFC drawings (17 pending)
10. 📸 **Screenshot 8:** Compliance Report showing Milestone 1 breach language

**What to expect:**
- Risk Score: MEDIUM-HIGH (0.5–0.7)
- Variance: −10.9%
- Time to Default: Estimated (days remaining before LD cap)
- Key SHAP drivers: Physical progress variance, GFC drawings pending, payment streak

---

## 🎭 PERSONA 3 — Site Engineer (Scenario A: On Track)

**Goal:** Show baseline/green project — the system confirms compliance, no alerts.

### Steps:
1. **Sidebar — Role:** Change to **"Site Engineer"**
2. Scroll to the **MPR Upload** section
3. Click **"Browse files"** → Select **`MPR_A_ON_TRACK_Month3_Day91.docx`**
4. Leave **Previous Month Actual Progress** = `0.0`
5. Click **"🔍 Run Full Analysis"**
6. ⏳ Wait 30–90 seconds
7. 📸 **Screenshot 9:** Metric tiles (LOW risk, 0 NCRs, LD = ₹0)
8. 📸 **Screenshot 10:** S-Curve with actual tracking closely to planned at Day 91
9. 📸 **Screenshot 11:** SHAP chart — all factors green/low contribution
10. 📸 **Screenshot 12:** Compliance Report — clean report, no critical events

**What to expect:**
- Risk Score: LOW (< 0.3)
- Labour Utilisation: 103.5% (over-staffed for acceleration)
- 0 NCRs, 0 payment delays
- S-Curve: Actual slightly above or matching planned

---

## 🎭 PERSONA 4 — Auditor (Scenario D: Valid Force Majeure — Flood)

**Goal:** Show the auditor how the system validates a legitimate EoT claim based on rainfall data.

### Steps:
1. **Sidebar — Role:** Change to **"Auditor"**
2. Scroll to the **MPR Upload** section
3. Click **"Browse files"** → Select **`MPR_D_VALID_FM_Month5_Day152_Flood.docx`**
4. Leave **Previous Month Actual Progress** = `0.0`
5. Click **"🔍 Run Full Analysis"**
6. ⏳ Wait 30–90 seconds
7. 📸 **Screenshot 13:** Metric tiles — note medium risk despite FM (system is conservative)
8. 📸 **Screenshot 14:** SHAP — weather anomaly score should appear as a significant factor (512mm = score ~1.7)
9. 📸 **Screenshot 15:** Compliance Report Preview — look for FM/weather language and EoT recommendation
10. 📸 **Screenshot 16:** The Role-Specific Panel at the bottom (Auditor panel shows audit checklist)

**What to expect:**
- Risk Score: MEDIUM (system hedges pending EoT approval)
- Weather anomaly score: High (512mm >> baseline)
- Compliance report: Should mention Force Majeure clause, recommend EoT review
- Labour: 84.7% (reduced due to weather)

---

## 🎭 PERSONA 5 — Contractor Rep (Scenario F: Near Complete + Bonus)

**Goal:** Show the contractor's perspective on a successfully completed project with catch-up bonus potential.

### Steps:
1. **Sidebar — Role:** Change to **"Contractor Rep"**
   *(may be labeled "Contractor" or "Contractor Representative" — pick the closest match)*
2. Scroll to the **MPR Upload** section
3. Click **"Browse files"** → Select **`MPR_F_NEAR_COMPLETE_Bonus_CatchUp_Month22.docx`**
4. Set **"Previous Month Actual Progress"** = `95.0` (project was at 95% last month)
5. Click **"🔍 Run Full Analysis"**
6. ⏳ Wait 30–90 seconds
7. 📸 **Screenshot 17:** Metric tiles — LOW risk, very low LD, Day 672 of 730
8. 📸 **Screenshot 18:** S-Curve showing actual (97.8%) nearly at 100%, ahead of some planned scenarios
9. 📸 **Screenshot 19:** SHAP — only 2 NCRs show as minor risk factors
10. 📸 **Screenshot 20:** Role-specific "Contractor Rep" panel if available — shows payment status

**What to expect:**
- Risk Score: LOW (< 0.2)
- Day 672 of 730 contract days
- Actual Physical: 97.8%
- Labour: 96.7%, GFC: 0 pending
- Compliance: Clean or near-clean

---

## 📸 Screenshot Naming Convention

Save your screenshots with these names for the catalogue:
```
P1_ContractManager_Defaulting_metrics.png
P1_ContractManager_Defaulting_scurve.png
P1_ContractManager_Defaulting_shap.png
P1_ContractManager_Defaulting_report.png

P2_ProjectManager_AtRisk_metrics.png
P2_ProjectManager_AtRisk_scurve.png
P2_ProjectManager_AtRisk_shap.png
P2_ProjectManager_AtRisk_report.png

P3_SiteEngineer_OnTrack_metrics.png
P3_SiteEngineer_OnTrack_scurve.png
P3_SiteEngineer_OnTrack_shap.png
P3_SiteEngineer_OnTrack_report.png

P4_Auditor_ValidFM_metrics.png
P4_Auditor_ValidFM_shap.png
P4_Auditor_ValidFM_report.png
P4_Auditor_ValidFM_panel.png

P5_ContractorRep_NearComplete_metrics.png
P5_ContractorRep_NearComplete_scurve.png
P5_ContractorRep_NearComplete_shap.png
P5_ContractorRep_NearComplete_panel.png
```

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| "API Error 500" | Check Terminal 1 (API server) for error logs |
| "Connection error" | API may have crashed — restart Terminal 1 |
| Analysis spinner runs forever | Groq API key may be rate-limited — wait 60s and retry |
| No SHAP chart shown | Risk predictor returned no top_factors — still valid, just no chart |
| "Please upload an MPR file" warning | File wasn't attached — click Browse Files again |
| Dashboard shows old results | Reload the page (F5) and re-upload |

---

## 🌐 Direct API Test (Optional)

You can also test the API directly from PowerShell:
```powershell
$filePath = "Fake contracts and reports\MPR_B_AT_RISK_Month7_Day214_M1Missed.docx"
$fileBytes = [System.IO.File]::ReadAllBytes((Resolve-Path $filePath))
$boundary = [System.Guid]::NewGuid().ToString()
# Use curl or Postman with multipart/form-data pointing to:
# POST http://localhost:8000/upload-mpr
# Fields: file (docx), contract_id, prev_actual_pct, audience
```

Or simply visit **http://localhost:8000/docs** for the interactive Swagger UI.

---

*Generated by ContractGuard AI — Phase 1 Document Ingestion Pipeline*
*All 6 scenarios verified: `python -m scripts.smoke_test_mpr` → ALL OK*
