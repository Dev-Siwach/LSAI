# Sovereign On-Premise Agentic AI Workbench (LSAI)

[![Air-Gap Enforcement](https://img.shields.io/badge/Air--Gap-100%25%20Verified%20Local-success.svg)](#air-gap-guarantees)
[![Problem Statement](https://img.shields.io/badge/PS%20ID-26117-blue.svg)](#problem-statement)
[![Hardware Target](https://img.shields.io/badge/Hardware-RTX%204050%206GB%20%2B%2016GB%20RAM-orange.svg)](#hardware-profiles)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20SSE-009688.svg)](#api-reference)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](#testing)

**Problem Statement ID: 26117**  
*Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work.*

LSAI is an enterprise-grade, air-gapped agentic workbench designed for highly confidential engineering, oil & gas refineries, nuclear facilities, PSU compliance, and defense sectors. It operates **100% on-premise** on commodity hardware (optimized for an RTX 4050 6GB VRAM laptop) with provable, runtime-enforced zero external network egress.

---

## Architecture Overview

```
                                  +---------------------------------------+
                                  |         FastAPI REST + SSE            |
                                  | (Air-Gap Interceptor Monitored Core) |
                                  +-------------------+-------------------+
                                                      |
                                       [Stage 1: Plan & Route]
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |       3-Stage Agent Orchestrator      |
                                  |   - Intent Classifier (6 Task Types)  |
                                  |   - Autonomous Model Selector         |
                                  |   - Self-Correction Retry Loop        |
                                  +-------------------+-------------------+
                                                      |
                                       [Stage 2: Tool Execution]
                                                      |
          +-----------------------+-------------------+-----------------------+-----------------------+
          |                       |                   |                       |                       |
          v                       v                   v                       v                       v
+-------------------+   +-------------------+   +-------------------+   +-------------------+   +-------------------+
|  Sandboxed Code   |   |   Embedded RAG    |   |   Doc & Vision    |   |   Spreadsheet &   |   |   File Manager    |
|     Execution     |   |      Qdrant       |   |      Parser       |   |    Excel Engine   |   |     (Jailed)      |
| Subprocess/Docker |   |   BGE-Small-v1.5  |   | Docling / Qwen-VL |   |   openpyxl / CSV  |   | uploads/deliverabl|
+-------------------+   +-------------------+   +-------------------+   +-------------------+   +-------------------+
                                                      |
                                       [Stage 3: Deliverable Synthesis]
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |         Deliverable Generator         |
                                  | - Official PSU .docx Approval Notes   |
                                  | - Verified .xlsx Calculation Sheets   |
                                  | - Executive .pptx Briefing Slides     |
                                  +---------------------------------------+
```

---

## Key Capabilities

1. **Air-Gap Network Interception (`core/network_monitor.py`)**:
   - Monkey-patches Python's low-level `socket.socket.connect`, `connect_ex`, and `socket.create_connection`.
   - Intercepts all outbound non-loopback network calls at the operating system socket layer.
   - Live event ring buffer with SSE streaming (`/api/network/stream`) and active verification probes (`/api/network/verify`).
   - Automatically drops connections to non-whitelisted destinations with HTTP 403 `SecurityException`.

2. **3-Stage Sovereign Orchestrator (`core/orchestrator.py`)**:
   - **Stage 1 (Plan & Route)**: Classifies user prompt into 6 task types (`engineering_calculation`, `vision_pid_inspection`, `scanned_document_ocr`, `code_execution`, `sop_compliance`, `deep_reasoning`), binds appropriate local model profile, and outputs structured execution plan.
   - **Stage 2 (Worker Execution & Self-Correction)**: Executes tool actions with automated self-correction (up to 3 retries on execution or syntax errors).
   - **Stage 3 (Deliverable Synthesis)**: Compiles results into formatted artifacts (.docx, .xlsx, .pptx) complying with PSU Safety Directive standards.

3. **Confidential Tooling Suite**:
   - **Dual-Mode Sandbox (`tools/sandbox.py`)**: Executes Python code in Docker (with `network_mode=none` and read-only mounts) or restricted subprocess with `RLIMIT_AS` memory clamping and socket monkey-patching.
   - **Vector RAG Engine (`tools/rag_engine.py`)**: Embedded Qdrant vector database running entirely on local disk (`storage/qdrant/`) with `BAAI/bge-small-en-v1.5` dense embeddings.
   - **Document & Vision Parser (`tools/doc_parser.py`)**: Extracts text and tables from PDFs, performs local OCR (Tesseract / Qwen-OCR), and normalizes high-resolution P&ID drawings for vision models.
   - **Jailed File Manager (`tools/file_manager.py`)**: Strict path traversal prevention ensuring agent tools can only access `data/uploads/`, `data/deliverables/`, and `data/samples/`.

---

## Hardware Profiles (`config/models.yaml`)

| Profile | Target Hardware | Primary Reasoning | Primary Coding | Primary Vision | RAM / VRAM Budget |
|---|---|---|---|---|---|
| **`laptop_quantized`** (Default) | RTX 4050 6GB VRAM + 16GB RAM | `deepseek-r1:32b` (Q3_K_M) | `qwen2.5-coder:32b` (Q3_K_M) | `qwen2-vl:7b` (Q4_K_M) | 6GB VRAM + 12GB RAM offload |
| **`server_full`** | Dual RTX 4090 / A100 | `deepseek-r1:32b` (FP16) | `qwen2.5-coder:32b` (FP16) | `qwen2-vl:7b` (FP16) | 48GB+ VRAM |
| **`fast_fallback`** | Low-resource / CPU mode | `deepseek-r1:7b` (Q4_K_M) | `qwen2.5-coder:7b` (Q4_K_M) | `qwen2-vl:7b` (Q4_K_M) | < 8GB RAM |

---

## Quick Start & Installation

### 1. Prerequisites
- Linux OS (Ubuntu 22.04+ or similar)
- Python 3.10+ (tested on Python 3.14.7)
- Local Model Runner (e.g. [Ollama](https://ollama.com) or `llama-server`) running on `http://127.0.0.1:11434`

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/Dev-Siwach/LSAI.git
cd LSAI
git checkout backend

# Automated setup (initializes .venv, dependencies, directory hierarchy, and demo datasets):
./scripts/setup_env.sh

# Or manual install:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/seed_demo_data.py --force --verify
```

### 3. Start Local Model Runner
```bash
# Pull quantized models (for laptop_quantized profile on RTX 4050 6GB VRAM)
ollama pull deepseek-r1:32b
ollama pull qwen2.5-coder:32b
ollama pull qwen2-vl:7b

# Ollama serves automatically on localhost:11434
```

### 4. Launch LSAI Backend & Test Workbench
```bash
# Run FastAPI server via Uvicorn
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **`http://127.0.0.1:8000/demo`** in your browser to access the sovereign test workbench with:
- Live Air-Gap Status Shield & Packet Monitor
- Dynamic Model Auto-Selector Badge
- 4 One-Click Demo Scenarios (ASME B31.3 calculation, scanned inspection to Word approval note, multimodal P&ID understanding, live socket intercept probe)
- Real-time 3-stage agent execution terminal (SSE)
- 1-click downloads for verified deliverables (.docx, .xlsx, .pptx, .py)

---

## API Reference

### System & Health
- `GET /`: Workbench overview, active profile, and problem statement metadata.
- `GET /api/health`: Comprehensive health check across air-gap status, local model server reachability, and storage directories.
- `GET /demo`: Interactive workbench demo frontend.

### Agent Orchestration
- `POST /api/agent/run`: Dispatch a task to the 3-stage agent pipeline.
- `GET /api/agent/stream/{task_id}`: Live Server-Sent Events (SSE) streaming reasoning thoughts, tool execution events, and deliverable creation.
- `GET /api/agent/task/{task_id}`: Poll full task execution state, plan steps, and synthesis output.
- `GET /api/agent/tasks`: List recent tasks.
- `POST /api/agent/cancel/{task_id}`: Cancel an in-flight execution pipeline.
- `GET /api/agent/history/{session_id}`: Fetch multi-turn conversation memory.

### Sovereign Network Monitor
- `GET /api/network/stats`: Aggregated metrics (`blocked_requests`, `allowed_requests`, sovereign status).
- `GET /api/network/events`: Retrieve recent socket intercept events.
- `GET /api/network/stream`: Live SSE stream of real-time network interception events.
- `POST /api/network/verify`: Active verification probe attempting external connection to demonstrate air-gap enforcement.

### Document RAG & Deliverables
- `POST /api/rag/upload`: Upload industrial SOPs or manuals and index into embedded Qdrant.
- `POST /api/rag/search`: Dense vector search across ingested technical documentation.
- `GET /api/rag/samples`: List pre-loaded industrial sample files (SOP, scanned PDF report, P&ID schematic).
- `GET /api/deliverables/list`: List generated artifacts.
- `GET /api/deliverables/download/{filename}`: Secure download of verified deliverables (.docx, .xlsx, .pptx, .py).

---

## Testing

The project features a comprehensive test suite covering unit, integration, and security edge-case scenarios:

```bash
# Run complete test suite (106 tests)
pytest -v
```

All 106 tests verify:
- Strict socket air-gap interception and IPv4/IPv6 loopback whitelist validation.
- Path-traversal resistance across file management and download endpoints.
- Self-correction retry loop and stage transition integrity.
- Deliverable artifact formatting (.docx, .xlsx, .pptx, .py) and uniqueness.
- Pre-loaded industrial sample datasets (SOP, PDF inspection report, P&ID drawing) and data seeder script.
- Live serving of the air-gapped test workbench web UI.
- Complete end-to-end execution of all 4 problem statement demo scenarios.
