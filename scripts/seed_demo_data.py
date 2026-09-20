"""Seed Demo Data Script for Sovereign On-Premise Agentic AI Workbench.

Pre-indexes industrial SOPs and inspection reports into embedded Qdrant
so the RAG engine is immediately searchable on first launch.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import get_settings
from tools.doc_parser import DocParser
from tools.rag_engine import RagEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo_data")


def ensure_samples_exist(force: bool = False) -> None:
    """Ensure sample files exist in data/samples/, generating if necessary."""
    from scripts.generate_samples import generate_all_samples

    settings = get_settings()
    samples_dir = settings.SAMPLES_DIR
    samples_dir.mkdir(parents=True, exist_ok=True)

    sop_file = samples_dir / "refinery_sop_402.txt"
    pid_file = samples_dir / "pid_drawing_sample.png"
    pdf_file = samples_dir / "inspection_report_sample.pdf"

    if force or not (sop_file.exists() and pid_file.exists() and pdf_file.exists()):
        logger.info("Generating or refreshing industrial sample datasets...")
        generate_all_samples()
    else:
        logger.info("Demo sample datasets already present in %s", samples_dir)


def seed_rag_database(force: bool = False) -> dict:
    """Index sample SOP and inspection report into local embedded Qdrant."""
    settings = get_settings()
    samples_dir = settings.SAMPLES_DIR

    sop_file = samples_dir / "refinery_sop_402.txt"
    pdf_file = samples_dir / "inspection_report_sample.pdf"

    stats = {
        "sop_chunks": 0,
        "pdf_chunks": 0,
        "total_chunks": 0,
        "rag_online": False,
    }

    try:
        engine = RagEngine()
        stats["rag_online"] = True
    except Exception as e:
        logger.warning(
            "RagEngine could not be initialized directly (%s). Running in standalone/offline mode.",
            e,
        )
        return stats

    # 1. Ingest Refinery SOP 402
    if sop_file.exists():
        sop_text = sop_file.read_text(encoding="utf-8", errors="replace")
        chunks = engine.ingest_document(
            doc_id="SOP-REF-402-REV4",
            text=sop_text,
            metadata={
                "title": "High-Pressure PSV and Piping Integrity SOP",
                "document_number": "SOP-REF-402-REV4",
                "category": "safety_procedure",
                "standards": ["ASME Sec VIII", "ASME B31.3", "API 520", "API 526", "OISD-132"],
                "source": str(sop_file),
            },
        )
        stats["sop_chunks"] = chunks
        logger.info("Successfully indexed %d chunks for SOP-REF-402-REV4", chunks)

    # 2. Ingest Inspection Report PDF
    if pdf_file.exists():
        parser = DocParser()
        parsed = parser.parse_pdf(str(pdf_file))
        pdf_text = parsed.get("content", "")
        if pdf_text.strip():
            chunks = engine.ingest_document(
                doc_id="BRPC-INSP-AVDU-02-UTG-402",
                text=pdf_text,
                metadata={
                    "title": "AVDU-02 Annual Ultrasonic Thickness Inspection Report 2026",
                    "unit": "AVDU-02",
                    "line": "10-HC-402-CS300",
                    "category": "ndt_inspection",
                    "source": str(pdf_file),
                },
            )
            stats["pdf_chunks"] = chunks
            logger.info("Successfully indexed %d chunks for Inspection Report PDF", chunks)

    stats["total_chunks"] = stats["sop_chunks"] + stats["pdf_chunks"]
    return stats


def verify_knowledge_base() -> bool:
    """Execute test vector queries against embedded Qdrant to confirm retrieval."""
    test_queries = [
        "What is the set pressure for safety relief valve PSV-402?",
        "What is the minimum allowable pipe wall thickness under ASME B31.3?",
        "What was the measured ultrasonic thickness at Elbow E-04?",
    ]

    logger.info("Verifying RAG Knowledge Base retrieval...")
    try:
        engine = RagEngine()
    except Exception as e:
        logger.warning("RagEngine unavailable for active verification: %s", e)
        return False

    all_passed = True
    for q in test_queries:
        results = engine.search(query=q, limit=2)
        print(f"\nQuery: '{q}'")
        if results:
            top_hit = results[0]
            score = top_hit.get("score", 0.0)
            text_snippet = top_hit.get("text", "")[:120].replace("\n", " ")
            print(f"  -> Top Result [Score: {score:.3f}]: {text_snippet}...")
        else:
            print("  -> No matching chunks found.")
            all_passed = False

    return all_passed


def main() -> int:
    """CLI entrypoint for demo data seeding."""
    parser = argparse.ArgumentParser(
        description="Seed local demo data and embedded Qdrant vector database for Sovereign AI Workbench."
    )
    parser.add_argument("--force", action="store_true", help="Force regeneration of sample assets")
    parser.add_argument("--verify", action="store_true", help="Run verification queries after seeding")
    args = parser.parse_args()

    print("======================================================================")
    print(" Sovereign Industrial AI Workbench — Demo Data Seeder (PS ID: 26117)")
    print("======================================================================")

    # Ensure files exist
    ensure_samples_exist(force=args.force)

    # Ingest into RAG
    stats = seed_rag_database(force=args.force)

    print("\n--- Seeding Summary ---")
    print(f"RAG Engine Online:   {stats['rag_online']}")
    print(f"SOP Chunks Indexed:  {stats['sop_chunks']}")
    print(f"PDF Chunks Indexed:  {stats['pdf_chunks']}")
    print(f"Total Chunks:        {stats['total_chunks']}")

    if args.verify:
        if stats["rag_online"]:
            success = verify_knowledge_base()
            if success:
                print("\n[SUCCESS] Knowledge base retrieval verified successfully.")
            else:
                print("\n[WARNING] Some verification queries returned zero results.")
        else:
            print("\n[NOTE] RAG Engine is in offline fallback mode. Verification skipped.")

    print("\nInitialization complete. Sovereign Workbench is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
