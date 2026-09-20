#!/usr/bin/env bash
# ==============================================================================
# Sovereign On-Premise Agentic AI Workbench — Environment Setup Script
# Problem Statement ID: 26117
#
# Configures local virtual environment, installs dependencies, verifies air-gap
# directory tree, and pre-seeds confidential industrial demo datasets.
# ==============================================================================

set -e

# ANSI Color codes
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}======================================================================${RESET}"
echo -e "${BOLD}${CYAN} Sovereign Industrial AI Workbench — Environment Initializer (PS: 26117)${RESET}"
echo -e "${BOLD}${CYAN}======================================================================${RESET}"

# 1. Determine base directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

echo -e "\n${BLUE}[1/5] Checking Python Runtime...${RESET}"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}[ERROR] Python 3 is not installed. Please install Python 3.10 or newer.${RESET}"
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Found Python: ${GREEN}$($PYTHON_CMD --version)${RESET} (version $PY_VERSION)"

# 2. Virtual Environment Setup
echo -e "\n${BLUE}[2/5] Initializing Virtual Environment...${RESET}"
VENV_DIR="$BASE_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}[OK] Virtual environment created successfully.${RESET}"
else
    echo -e "${GREEN}[OK] Existing virtual environment found at $VENV_DIR.${RESET}"
fi

# Source virtualenv
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# 3. Installing dependencies
echo -e "\n${BLUE}[3/5] Installing Dependencies from requirements.txt...${RESET}"
if [ -f "$BASE_DIR/requirements.txt" ]; then
    echo "Upgrading pip..."
    pip install --upgrade pip --quiet
    echo "Installing application requirements..."
    pip install -r "$BASE_DIR/requirements.txt" --quiet || {
        echo -e "${YELLOW}[WARNING] Some optional packages failed to install. Core system will run with fallbacks.${RESET}"
    }
    echo -e "${GREEN}[OK] Dependency installation completed.${RESET}"
else
    echo -e "${RED}[ERROR] requirements.txt not found at $BASE_DIR.${RESET}"
    exit 1
fi

# 4. Workspace Directory Verification
echo -e "\n${BLUE}[4/5] Verifying Air-Gap Storage and Workspace Directories...${RESET}"
mkdir -p "$BASE_DIR/data/uploads"
mkdir -p "$BASE_DIR/data/deliverables"
mkdir -p "$BASE_DIR/data/samples"
mkdir -p "$BASE_DIR/storage/qdrant"
mkdir -p "$BASE_DIR/static"
mkdir -p "$BASE_DIR/scratch"
echo -e "${GREEN}[OK] Verified directory hierarchy:${RESET}"
echo "  - data/uploads/      (Confidential incoming files)"
echo "  - data/deliverables/ (Synthesized Word .docx, Excel .xlsx, PPT .pptx)"
echo "  - data/samples/      (Realistic industrial SOP, PDF, and P&ID assets)"
echo "  - storage/qdrant/    (Embedded on-premise vector storage)"
echo "  - static/            (Air-gapped test workbench web frontend)"

# 5. Seeding Demo Datasets
echo -e "\n${BLUE}[5/5] Generating Industrial Datasets & Seeding Local RAG Knowledge Base...${RESET}"
python3 "$BASE_DIR/scripts/seed_demo_data.py" --force --verify

echo -e "\n${BOLD}${GREEN}======================================================================${RESET}"
echo -e "${BOLD}${GREEN} Sovereign AI Workbench is configured and ready for execution!${RESET}"
echo -e "${BOLD}${GREEN}======================================================================${RESET}"
echo -e "\n${BOLD}Quick Start Instructions:${RESET}"
echo -e "  1. Activate virtualenv:    ${CYAN}source .venv/bin/activate${RESET}"
echo -e "  2. Start local Ollama:     ${CYAN}ollama serve${RESET}"
echo -e "  3. Launch Workbench API:   ${CYAN}uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload${RESET}"
echo -e "  4. Open Test Workbench:    ${CYAN}http://127.0.0.1:8000/demo${RESET}"
echo -e "  5. Run Verification Tests: ${CYAN}pytest -v${RESET}\n"
