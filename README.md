# TrustGate ETL

![TrustGate dashboard](docs/dashboard.png)

**Document-to-warehouse ETL: Loading data with deterministic validation, quarantine, and human review instead of blind trust in AI extraction.**

## Overview
TrustGate is an ETL pipeline designed to extract structured data from documents and safely load it into a data warehouse. It tackles the unreliability of LLM extractions by enforcing strict deterministic validation rules and routing uncertain records to a quarantine zone for human review.

## Key Features
- **AI Extraction:** Extracts invoice/document fields intelligently.
- **Deterministic Validation:** Cross-checks math and formats before loading.
- **Quarantine Zone:** Flags and holds unverified data for human-in-the-loop review.
- **Data Lineage:** Tracks the source of each extracted field.

## Limitations
- **Parsing constraints:** The offline parser currently performs best with text-based PDFs. Scanned documents require OCR integration (e.g., Tesseract or Gemini vision).
- **Validation limits:** Math checks are limited to `Subtotal + Tax = Total`. Complex rules involving dynamic discounts or shipping are not yet handled.
- **API Dependencies:** Gemini integration requires your own API key for live testing.

## Datasets
- Uses the [Northwind Invoices (Apache-2.0)](link-to-dataset-here) dataset for public testing.