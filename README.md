# 🛡️ HalluShield AI - Backend

**Intelligent SLM to LLM Escalation System with Hallucination Detection & Correction**

HalluShield automatically routes queries through cost-effective Small Language Models (SLMs) and escalates to premium Large Language Models (LLMs) only when hallucinations are detected, saving costs while maintaining accuracy.

---

## 🎯 Features

- **🚀 SLM-First Architecture**: Start with fast, cheap Groq models (Llama 3.3 70B, Llama 3.1 8B)
- **🎓 Smart Escalation**: Auto-escalate to Gemini/Claude when hallucinations detected
- **🔍 Hallucination Detection**: Real-time claim verification with web evidence
- **✅ Auto-Correction**: Replace hallucinated facts with evidence-backed corrections
- **💰 Cost Optimization**: Save 80%+ on API costs vs. always using premium LLMs
- **📊 Multi-Provider Support**: Groq, Gemini, HuggingFace, Claude with automatic fallbacks
- **🧠 LangGraph Orchestration**: Complex workflow management with state machines

---

## 🏗️ Architecture

### Three-Tier Model System

**Tier 1: SLM (Small Language Models)**
- **Groq**: `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`
- **HuggingFace**: `Mistral-7B-Instruct-v0.3`, `Phi-3-medium-4k-instruct`
- **Cost**: $0.05-0.20 per 1M tokens
- **Speed**: 500-1000 tokens/second
- **Use Case**: Handle 70-80% of queries (simple facts, common knowledge)

**Tier 2: LLM (Large Language Models)**
- **Google Gemini**: `gemini-2.5-flash`, `gemini-2.5-pro`
- **Anthropic Claude**: `claude-sonnet-4-20250514` (fallback)
- **Cost**: $0.50-7.50 per 1M tokens
- **Speed**: 100-200 tokens/second
- **Use Case**: Complex queries, when SLM hallucinates or lacks knowledge

**Tier 3: Verification Layer**
- Claim extraction (regex-based, no ML)
- Evidence retrieval (web search APIs)
- Hallucination verification (Gemini NLI)
- Answer correction and reconstruction

---

## 📦 Installation

### Prerequisites
- Python 3.13+
- PostgreSQL (for memory cache)
- [uv](https://github.com/astral-sh/uv) (package manager)

### Setup

1. **Clone the repository**
```bash
cd MetaMusk-backend-repo
```

2. **Install dependencies with uv**
```bash
uv sync
```

This will install all dependencies from `pyproject.toml`:
- FastAPI, Uvicorn, Pydantic
- LangChain, LangGraph
- Groq, Gemini, Anthropic, HuggingFace SDKs
- Database libraries (PostgreSQL, SQLAlchemy)

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required API keys:
- `GROQ_API_KEY` - Get from [console.groq.com](https://console.groq.com)
- `GEMINI_API_KEY` - Get from [aistudio.google.com](https://aistudio.google.com/apikey)
- `ANTHROPIC_API_KEY` - Get from [console.anthropic.com](https://console.anthropic.com)
- `HF_TOKEN` - Get from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
- `SEARCH_API_KEY` - Get from [search.brave.com/search/api](https://search.brave.com/search/api) or SerpAPI

4. **Start PostgreSQL** (if using Docker)
```bash
docker-compose up -d
```

5. **Run the server**
```bash
uv run uvicorn main:app --reload
```

Or use the start script:
```bash
bash start.sh
```

Server will be available at `http://localhost:8000`

---

## 🚀 API Usage

### 1. Verify Query (Main Endpoint)

**POST** `/verify`

Verify a query with intelligent SLM->LLM routing and hallucination detection.

**Request:**
```json
{
  "query": "When was the Eiffel Tower built?",
  "user_id": "optional-user-id",
  "llm_provider": null,
  "llm_model": null
}
```

**Response:**
```json
{
  "verified_answer": "The Eiffel Tower was built between 1887 and 1889.",
  "original_answer": "The Eiffel Tower was built in 1889.",
  "modifications": [],
  "hallucination_score": 0.0,
  "confidence": 1.0,
  "claim_breakdown": {
    "total_claims": 1,
    "verified": 1,
    "corrected": 0,
    "abstained": 0,
    "flagged": 0
  },
  "decisions": [...],
  "claims": [...],
  "errors": []
}
```

**Example with hallucination:**
```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the population of Tokyo in 2024?"
  }'
```

### 2. Get Statistics

**GET** `/stats`

Get usage statistics including SLM/LLM calls, escalation rate, and cost savings.

**Response:**
```json
{
  "slm_calls": 45,
  "llm_calls": 8,
  "total_calls": 53,
  "escalations": 8,
  "escalation_rate": 0.178,
  "total_cost": 0.0234,
  "cost_saved": 0.1876,
  "avg_cost_per_query": 0.0004
}
```

**Example:**
```bash
curl http://localhost:8000/stats
```

### 3. Health Check

**GET** `/healthz`

Check if the server is running.

**Response:**
```json
{
  "status": "ok"
}
```

---

## 🧩 Components

### 1. **ModelRouter** (`hallushield/model_router.py`)
Multi-provider router supporting Groq (SLM), Gemini (LLM), HuggingFace (SLM fallback), and Claude (LLM fallback).

**Features:**
- Automatic fallbacks between providers
- Cost tracking per tier
- Escalation decision logic
- Usage statistics

### 2. **ClaimExtractor** (`hallushield/claim_extractor.py`)
Extract atomic factual claims from LLM responses using regex patterns (no ML dependencies).

### 3. **EvidenceRetriever** (`hallushield/evidence_retriever.py`)
Retrieve evidence from web search APIs to validate claims.

### 4. **NLIVerifier** (`hallushield/verifier.py`)
Verify claims against evidence using Natural Language Inference.

### 5. **AdaptiveDecisionPolicy** (`hallushield/policy.py`)
Make decisions (ACCEPT, CORRECT, ABSTAIN, FLAG_FOR_HUMAN) based on verification scores.

### 6. **HalluShieldPipeline** (`hallushield/pipeline.py`)
LangGraph-based orchestration pipeline with:
- SLM-first approach
- Claim extraction
- Evidence retrieval
- Verification
- **Escalation check** (new!)
- Policy application
- Answer correction

---

## 🔄 Workflow

```
User Query
    ↓
[1] Call SLM (Groq Llama 3.3 70B)
    ↓
[2] Extract Claims
    ↓
[3] Check Memory Cache
    ↓
[4] Retrieve Evidence (if needed)
    ↓
[5] Verify Claims
    ↓
[6] Check Escalation
    ├─→ High hallucination? → [Escalate to LLM (Gemini)]
    └─→ Low hallucination → [Continue]
    ↓
[7] Apply Policy (ACCEPT/CORRECT/FLAG)
    ↓
[8] Assemble Corrected Answer
    ↓
[9] Update Memory
    ↓
Return Verified Answer
```

---

## ⚡ Escalation Triggers

HalluShield escalates from SLM to LLM when:

1. **SLM expresses uncertainty**: "I don't know", "I'm not sure", etc.
2. **High hallucination rate**: >30% of claims contradicted by evidence
3. **Low verification confidence**: <50% average confidence
4. **Very short response**: <10 words (may indicate lack of knowledge)

---

## 📊 Performance

**Cost Savings Example:**
- Query using only Gemini Pro: **$0.002**
- Query using SLM first (no escalation): **$0.0001** → **95% savings**
- Query using SLM + escalation: **$0.0011** → **45% savings**

**With 80% queries handled by SLM:**
- Average cost per query: **~$0.0005**
- **Total savings: ~75%** vs always using premium LLMs

---

## 🔧 Configuration

Edit `.env` to customize:

```bash
# Choose default SLM model
HALLUSHIELD_SLM_MODEL=llama-3.3-70b-versatile
# Options: llama-3.3-70b-versatile, llama-3.1-8b-instant

# Choose default LLM model
HALLUSHIELD_LLM_MODEL=gemini-2.5-flash
# Options: gemini-2.5-flash, gemini-2.5-pro

# Provider preference
HALLUSHIELD_PROVIDER=groq
# Options: groq, anthropic, openai
```

---

## 🧪 Testing

**Simple factual query (should use SLM only):**
```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of France?"}'
```

**Complex query (should escalate to LLM):**
```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain the quantum mechanical interpretation of wave-particle duality in detail."}'
```

**Check stats after queries:**
```bash
curl http://localhost:8000/stats
```

---

## 📝 Project Structure

```
MetaMusk-backend-repo/
├── main.py                      # FastAPI application
├── pyproject.toml               # Dependencies (uv)
├── .env.example                 # Environment template
├── README.md                    # This file
├── docker-compose.yml           # PostgreSQL setup
├── start.sh                     # Startup script
└── hallushield/
    ├── __init__.py
    ├── model_router.py          # Multi-provider router (NEW!)
    ├── claim_extractor.py       # Claim extraction
    ├── evidence_retriever.py    # Evidence retrieval
    ├── verifier.py              # NLI verification
    ├── policy.py                # Decision policy
    ├── pipeline.py              # LangGraph pipeline (ENHANCED!)
    ├── memory_store.py          # PostgreSQL cache
    ├── state.py                 # State definitions
    └── types.py                 # Pydantic models
```

---

## 🐛 Troubleshooting

**Import errors for LangChain:**
```bash
uv sync --reinstall
```

**API key errors:**
- Check `.env` file has correct API keys
- Ensure keys start with correct prefix (gsk_, AIza, sk-ant-, hf_)

**PostgreSQL connection errors:**
```bash
docker-compose up -d
# Wait for DB to be ready, then restart server
```

**No stats available:**
- Make sure to call `/verify` endpoint first
- Stats are accumulated in memory (reset on server restart)

---

## 📚 API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🎓 Learn More

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **Groq API**: https://console.groq.com/docs
- **Gemini API**: https://ai.google.dev/docs
- **Anthropic API**: https://docs.anthropic.com/

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a PR.

---

**Built with ❤️ using LangChain, LangGraph, and uv**
