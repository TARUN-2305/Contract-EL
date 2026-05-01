# ContractGuard AI

ContractGuard AI is a multi-agent system designed for automated parsing, compliance checking, risk prediction, and explanation of EPC contracts and MPRs (Monthly Progress Reports).

## Features
- **Contract Parsing:** Parses DOCX and PDF contracts and extracts data into a JSON rule store.
- **MPR Validation:** Extracts structured data from DOCX/Markdown MPRs and compares against rules.
- **Compliance Engine:** Assesses 15 distinct rules (e.g., LD calculation, EOT rules).
- **Risk Prediction:** Utilizes an XGBoost model for long-term project failure prediction.
- **Explainer & Dashboards:** Persona-based dashboards for Managers, Engineers, Auditors, and Contractor Reps.

## Setup

1. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Set up Postgres:
Ensure Postgres is installed and running on port 5432, and the `pgvector` extension is available.
Update your `.env` file with credentials:
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/contractguard
KEY1=gsk_your_groq_key_here
TAVILY_API_KEY=tvly_your_tavily_key
OPENWEATHERMAP_API_KEY=your_openweathermap_key
```

3. Initialize the database:
```bash
python scripts/init_db.py
```

## Running the Application

You can use the provided `startup.sh` or run the commands manually:

1. Start the API Server (Background):
```bash
uvicorn api.main:app --reload --port 8000
```

2. Start the Streamlit Dashboard:
```bash
streamlit run dashboard.py
```
