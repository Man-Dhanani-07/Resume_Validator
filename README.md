# Resume Validator API

An intelligent resume validation system built with FastAPI and LangGraph that analyzes resumes for authenticity, completeness, and quality using AI-powered agents.

## 🚀 Features

- **16 Specialized AI Agents** for comprehensive resume analysis
- **LangGraph Pipeline** for sequential workflow processing
- **Smart Caching System** - Extract once, analyze multiple times
- **REST API** with FastAPI
- **SQLite Database** for result persistence
- **Interactive API Documentation** with Swagger UI

## 📋 Available Agents

| Agent | Endpoint | Description |
|-------|----------|-------------|
| Classify | `/agent/classify` | Document type classification |
| Extract | `/agent/extract` | Structured data extraction |
| Validate | `/agent/validate` | Schema validation |
| Keywords | `/agent/keywords` | Suspicious keyword detection |
| Gaps | `/agent/gaps` | Employment gap analysis |
| Overlaps | `/agent/overlaps` | Overlapping job dates |
| Academics | `/agent/academics` | Academic timeline validation |
| Percentages | `/agent/percentages` | Invalid percentage detection |
| Future Dates | `/agent/future-dates` | Future date flags |
| Skills | `/agent/skills` | Skills presence check |
| Tenure | `/agent/tenure` | Job-hopping detection |
| Duplicates | `/agent/duplicates` | Duplicate entry detection |
| Seniority | `/agent/seniority` | Seniority mismatch analysis |
| Integrity | `/agent/integrity` | Full structural integrity check |
| LLM Score | `/agent/llm-score` | Semantic quality scoring |
| Risk | `/agent/risk` | Comprehensive risk assessment |
| Full Pipeline | `/agent/full-pipeline` | Complete LangGraph workflow |

## 🛠️ Tech Stack

- **FastAPI** - Modern web framework
- **LangGraph** - AI workflow orchestration
- **SQLAlchemy** - Database ORM
- **Pydantic** - Data validation
- **PyPDF2** - PDF parsing
- **Anthropic Claude** - LLM integration

## 📦 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Man-Dhanani-07/Resume_Validator.git
cd Resume_Validator
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
cd enterprise-ai-engine
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the `enterprise-ai-engine` directory:

```env
ANTHROPIC_API_KEY=your_api_key_here
DATABASE_URL=sqlite:///./resume_validator.db
```

## 🚀 Running the Application

### Start the FastAPI Server

```bash
cd enterprise-ai-engine
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Access the Application

- **API Base URL**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📖 API Usage

### 1. Upload Resume

```bash
POST /resume/upload
Content-Type: multipart/form-data

{
  "file": <resume.pdf>,
  "job_description": "Optional job description"
}
```

**Response:**
```json
{
  "resume_id": 1,
  "filename": "resume.pdf",
  "status": "uploaded"
}
```

### 2. Run Individual Agent

```bash
POST /agent/extract
Content-Type: application/json

{
  "resume_id": 1,
  "force_reextract": false
}
```

### 3. Run Full Pipeline

```bash
POST /agent/full-pipeline
Content-Type: application/json

{
  "resume_id": 1,
  "job_description": "Optional JD"
}
```

### 4. Get All Results

```bash
GET /agent/results/{resume_id}
```

## 🏗️ Project Structure

```
enterprise-ai-engine/
├── app/
│   ├── agents/           # AI agent implementations
│   │   ├── classifier.py
│   │   ├── extractor.py
│   │   ├── validator.py
│   │   ├── resume_integrity.py
│   │   ├── resume_judge.py
│   │   └── risk.py
│   ├── config/           # Configuration settings
│   ├── db/               # Database models & repository
│   ├── graph/            # LangGraph workflow
│   │   ├── nodes.py
│   │   ├── state.py
│   │   └── workflow.py
│   ├── routers/          # API endpoints
│   │   ├── agents.py
│   │   └── upload.py
│   └── main.py           # FastAPI application
├── pdf/                  # Sample resumes
├── requirements.txt
└── resume_ui.html        # Frontend interface
```

## 🔄 Workflow Architecture

```
Upload Resume → Extract (LLM) → Cache in DB → Run Agents (Use Cache)
                                              ↓
                    Classify → Process → Validate → Risk → Decision
```

### Smart Caching
- First agent call: Extracts data via LLM (~10-15s)
- Subsequent calls: Use cached data (~1-2s each)
- **Performance**: 400s → 30s for running all agents

## 🎯 Decision Logic

| Risk Level | Decision | Criteria |
|------------|----------|----------|
| LOW | APPROVE | Risk score < 30, High confidence |
| MEDIUM | REVIEW | Risk score 30-60, Manual review needed |
| HIGH | REJECT | Risk score > 60, Critical issues found |
| CRITICAL | REJECT | Validation failed or not a resume |

## 🧪 Testing

Sample test resumes are included in:
- `pdf/AI_resume/` - AI-generated resumes
- `pdf/Claude-pdf/` - Test cases (approve/reject/review)
- `pdf/FAKE_resume/` - Suspicious resumes

## 🔐 Security

- Environment variables for sensitive data
- Input validation with Pydantic
- SQL injection protection via SQLAlchemy ORM
- CORS middleware configured

## 📊 Database Schema

### Tables
- `resume_uploads` - Uploaded resume metadata
- `agent_results` - Individual agent execution results
- `extracted_data_cache` - Cached extraction results

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License.

## 👤 Author

**Man Dhanani**
- GitHub: [@Man-Dhanani-07](https://github.com/Man-Dhanani-07)

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- LangGraph for workflow orchestration
- Anthropic for Claude AI capabilities

## 📞 Support

For issues and questions, please open an issue on GitHub.

---

**Note**: This project requires an Anthropic API key for LLM functionality. Get yours at [anthropic.com](https://www.anthropic.com/).
