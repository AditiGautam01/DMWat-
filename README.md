# DMWat

An AI-powered data pipeline and web UI that connects a **local IBM Db2** database to **IBM watsonx.ai** for intelligent data analytics. Users can browse their database schema, summarize tables, ask natural-language questions about their data, and generate + execute SQL from plain English — all through a modern web interface.

The project also integrates with IBM Maximo (via mocks and REST API connections) to pull work orders and asset data, and includes handling for Aircraft Predictive Maintenance datasets.

## Key Features
- **Db2 Integration**: Connects to a local Db2 `SAMPLE` database using Windows implicit authentication.
- **Watsonx.ai Powered**: Utilizes `ibm/granite-3-8b-instruct` for natural language processing, data summarization, and SQL generation.
- **Maximo Integration**: Mocks and integrates IBM Maximo API for asset management and work orders.
- **Aircraft Predictive Maintenance**: Ingests and processes specialized predictive maintenance datasets.
- **Modern UI**: A vanilla HTML/CSS/JS frontend featuring a clean, responsive design tailored for data interaction.

## Architecture & Technology Stack
- **Database**: IBM Db2 for LUW
- **AI Service**: IBM watsonx.ai (`ibm/granite-3-8b-instruct` model)
- **Backend Framework**: FastAPI + Uvicorn
- **Integration**: `maximo_client.py` and `maximo_mock.py` for API data fetching
- **Frontend**: Vanilla JS, HTML, Custom CSS (Google Fonts: Inter, Phosphor Icons)

## Project Structure
```
DMWat/
├── api.py                    # FastAPI server (REST endpoints + static mount)
├── db2_watsonx_pipeline.py   # Core pipeline logic (Db2 ↔ watsonx.ai)
├── maximo_client.py          # Real IBM Maximo API client
├── maximo_mock.py            # Synthetic mocked data client for testing
├── test_local_db2.py         # Driver validation script
├── context.md                # In-depth architectural details
├── static/                   # Frontend assets
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .env.example              # Environment variable template
└── aircraft_predictive_maintenance (1).xlsx # Sample dataset
```

## Setup Instructions

1. **Install Python Dependencies**
   ```bash
   pip install ibm_db fastapi uvicorn python-dotenv requests
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your WATSONX_API_KEY and WATSONX_PROJECT_ID
   ```
   *Note: Ensure your Db2 instance has the `DB2_DLL_PATH` properly set under Windows.*

3. **Validate Db2 Connectivity**
   ```bash
   python test_local_db2.py
   ```

4. **Start the Web Server**
   ```bash
   python api.py
   ```
   Open `http://127.0.0.1:8000` in your browser.

## Documentation
For a precise breakdown of the architectural diagram, technical decisions, and API endpoints, refer to `context.md`.
