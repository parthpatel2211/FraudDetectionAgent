# 🛡️ AI-Powered Fraud Detection System

An intelligent fraud investigation platform that combines machine learning, graph analytics, and LLM-powered case summarization to detect and investigate suspicious financial transactions in real-time.

<img width="1286" height="437" alt="image" src="https://github.com/user-attachments/assets/8f026618-a8f7-449e-b5ce-5ad07702e87d" />


## ✨ Features

- **🤖 ML-Based Anomaly Detection**: Uses Isolation Forest algorithm to identify suspicious transaction patterns
- **🕸️ Graph Analytics**: Builds relationship graphs between transactions, customers, accounts, devices, and IP addresses
- **📊 Smart Case Clustering**: Automatically groups related anomalous transactions into investigable cases
- **💬 AI-Powered Summaries**: Generates natural language narratives and recommendations using LLMs
- **🔌 MCP Integration**: Exposes fraud detection tools via Model Context Protocol for AI agent workflows
- **⚡ Real-time Analysis**: REST API for immediate transaction screening
- **🎨 Interactive Dashboard**: React-based UI for case management and investigation

## 🏗️ Architecture

```
┌─────────────────┐
│  Frontend (React)│
│   + Material-UI  │
└────────┬─────────┘
         │ HTTP/REST
┌────────▼─────────┐
│   Flask Backend  │
│  + CORS Support  │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼────────┐
│  MCP │  │  Fraud    │
│Server│  │  Engine   │
└──────┘  └───┬───────┘
              │
    ┌─────────┼─────────┐
    │         │         │
┌───▼───┐ ┌──▼──┐ ┌───▼────┐
│Scikit │ │Graph│ │OpenAI  │
│ Learn │ │ NX  │ │   API  │
└───────┘ └─────┘ └────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 16+
- OpenAI API key (optional, for LLM summaries)

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-api-key-here"
export OPENAI_MODEL="gpt-4o-mini"
export DEBUG="true"

# Run Flask server
python app.py
```

The API will be available at `http://localhost:8000`

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The UI will be available at `http://localhost:5173`

### MCP Server Setup

```bash
# Run the MCP server
fastmcp run backend/mcp_server.py
```

## 📡 API Endpoints

### Health Check
```http
GET /health
```

### Analyze Transactions
```http
POST /api/transactions/analyze
Content-Type: application/json

[
  {
    "id": "tx_001",
    "customer_id": "cust_123",
    "account_id": "acct_456",
    "merchant_id": "merch_789",
    "amount": 1500.00,
    "currency": "USD",
    "timestamp": "2025-01-15T14:30:00Z",
    "channel": "WEB",
    "device_id": "dev_abc",
    "ip_address": "192.168.1.1",
    "country": "US"
  }
]
```

**Response:**
```json
[
  {
    "case_id": "uuid-string",
    "customer_id": "cust_123",
    "primary_account_id": "acct_456",
    "risk_score": 0.85,
    "signals": [
      {
        "name": "graph-connected-anomalies",
        "score": 0.85,
        "explanation": "Cluster of anomalous transactions sharing customers, devices, or IPs."
      }
    ],
    "transactions": [...]
  }
]
```

### Summarize Case
```http
POST /api/cases/summary
Content-Type: application/json

{
  "case_id": "uuid-string",
  "customer_id": "cust_123",
  "primary_account_id": "acct_456",
  "risk_score": 0.85,
  "signals": [...],
  "transactions": [...]
}
```

## 🔧 MCP Tools

### `analyze_transactions`
Analyzes a batch of transactions and returns detected fraud cases with risk scores and signals.

### `summarize_case`
Generates investigator-ready natural language summaries with narratives and recommendations.

## 🧠 How It Works

1. **Feature Engineering**: Extracts temporal, frequency, and behavioral features from transactions
2. **Anomaly Detection**: Uses Isolation Forest to score transactions for unusual patterns
3. **Graph Construction**: Builds a network connecting transactions through shared entities (customers, devices, IPs)
4. **Case Clustering**: Identifies connected components in the anomaly subgraph
5. **Risk Scoring**: Aggregates anomaly scores across clustered transactions
6. **LLM Summarization**: Generates human-readable case narratives and action recommendations

## 📊 Data Models

### Transaction
- `id`: Unique transaction identifier
- `customer_id`: Customer identifier
- `account_id`: Account identifier
- `merchant_id`: Merchant identifier
- `amount`: Transaction amount
- `currency`: Currency code (default: USD)
- `timestamp`: Transaction timestamp (ISO 8601)
- `channel`: Transaction channel (POS, WEB, MOBILE)
- `device_id`: Device identifier (optional)
- `ip_address`: IP address (optional)
- `country`: Country code (optional)

### Case
- `case_id`: Unique case identifier
- `customer_id`: Primary customer
- `primary_account_id`: Primary account
- `transactions`: List of suspicious transactions
- `risk_score`: Normalized risk score (0-1)
- `signals`: List of fraud signals detected

## 🛠️ Configuration

Environment variables (`.env` file):

```env
DEBUG=false
HOST=0.0.0.0
PORT=8000
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
FRONTEND_ORIGIN=http://localhost:5173
```

