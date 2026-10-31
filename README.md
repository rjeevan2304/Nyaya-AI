# Nyaya.ai 🏛️

**Nyaya.ai** is an AI-powered legal research platform tailored for Indian case law. It provides intelligent semantic search and AI summarization across judgements using vector embeddings and large language models.

---

## ✨ Features

- **Semantic Legal Search**: Natural language query matching powered by vector embeddings (`all-MiniLM-L6-v2`) via Qdrant.
- **Smart Filtering**: Filter case law by court (Supreme Court, High Courts) and decision year.
- **AI Case Analysis**: Synthesized case holding, summaries, and key legal takeaways powered by Anthropic's Claude.
- **Containerized Architecture**: Production-ready setup with Docker, Docker Compose, FastAPI, and Nginx.

---

## 🛠️ Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), Python 3.11, [Uvicorn](https://www.uvicorn.org/)
- **Vector Database**: [Qdrant](https://qdrant.tech/)
- **Embeddings**: [Sentence-Transformers](https://www.sbert.net/) (`all-MiniLM-L6-v2`)
- **LLM Provider**: [Anthropic Claude](https://www.anthropic.com/)
- **Frontend**: Clean and responsive HTML5/CSS3/JavaScript interface
- **Reverse Proxy / Deployment**: Nginx, Docker & Docker Compose

---

## 📂 Project Structure

```
nyaya-ai/
├── backend/
│   ├── main.py              # FastAPI server & search API endpoints
│   ├── ingest.py            # Script to vectorize & ingest cases into Qdrant
│   ├── bulk_ingest.py       # Batch ingestion utility
│   ├── download_data.py     # Script to fetch/prepare case law datasets
│   └── requirements.txt     # Python dependencies
├── data/
│   └── cases.json           # Sample Indian case law records
├── frontend/
│   └── index.html           # Web user interface
├── nginx/
│   └── nginx.conf           # Production Nginx reverse-proxy configuration
├── docker-compose.yml       # Local development setup (Qdrant)
├── docker-compose.prod.yml  # Production deployment setup
├── Dockerfile               # Backend container image
├── setup.sh                 # One-click setup script (macOS)
├── start.sh                 # Application start script
└── push-to-server.sh        # Deployment helper script
```

---

## 🚀 Getting Started

### Prerequisites

- **macOS / Linux / Windows (WSL2)**
- **Python 3.11+**
- **Docker & Docker Desktop** (running)
- **Anthropic API Key** (optional, for AI summarization features)

### 1. Automatic Setup (macOS)

Run the included setup script:

```bash
bash setup.sh
```

This will:
1. Verify Homebrew and Python 3.11.
2. Create a virtual environment and install backend dependencies.
3. Generate `.env` from `.env.example`.
4. Spin up the Qdrant vector database and ingest case records.

### 2. Manual Setup

If you prefer to configure manually:

1. **Clone the repository:**
   ```bash
   git clone git@github.com:rjeevan2304/Nyaya-AI.git
   cd Nyaya-AI
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Add your `ANTHROPIC_API_KEY` in `.env`:
   ```env
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   QDRANT_URL=http://localhost:6333
   ```

3. **Start the Qdrant database:**
   ```bash
   docker-compose up -d
   ```

4. **Set up Python environment:**
   ```bash
   cd backend
   python3.11 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Ingest case data:**
   ```bash
   python ingest.py
   ```

---

## 🏃 Running the Application

To launch the app:

```bash
bash start.sh
```

Or manually:

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at: **[http://localhost:8000](http://localhost:8000)**

---

## 🚢 Production Deployment

For deploying to a VPS (e.g., Hetzner / AWS / DigitalOcean):

```bash
bash push-to-server.sh <YOUR_SERVER_IP>
```

The production configuration uses `docker-compose.prod.yml` and `nginx/nginx.conf` for reverse proxying traffic and SSL termination.

---

## 📄 License

This project is open-source. Feel free to use and adapt it for legal research and technology development.
