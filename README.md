# Premium PII Redaction Tool

A production-quality, modular, and extensible PII Redaction Tool designed for processing large Microsoft Word (DOCX) documents. The tool detects sensitive data (such as names, emails, phones, companies, addresses, SSNs, credit cards, dates of birth, IP addresses, and PAN card numbers) and replaces them with realistic, deterministic fake data while preserving the original document's typography, styles, tables, headers, footers, hyperlinks, and layouts.

---

## 1. Architecture and Approach

The system employs a **modular pipeline** divided into four main layers:

```
[ Input DOCX ] ──> [ DocxRedactor ] ──> [ HybridDetector ] ──> [ PIIReplacer ] ──> [ Output Redacted DOCX ]
                          │                    │                    │
                   (Para/Table Walk)     (Regex + NLP)      (Faker + Stable Hash)
```

1. **Document Traverser (`src/redactor.py`)**: Walks through standard body paragraphs, tables, nested cell paragraphs, section headers/footers, and embedded shapes/textboxes. It modifies XML text at the **run level** to prevent layout or styling loss.
2. **Hybrid Detection Engine (`src/detector.py`)**: Combines:
   - **Microsoft Presidio Analyzer**: Performs NLP-based entity extraction for standard PII types.
   - **spaCy (`en_core_web_lg`)**: Detects context-dependent entities like persons, companies, locations, and facilities.
   - **Regex Detectors**: High-precision matching of standardized formats (Emails, Phone numbers, SSNs, Credit Cards, IPv4/IPv6, Indian PAN Cards, and Postal Codes).
   - **Conflict Resolver**: Applies a greedy interval scheduling algorithm to resolve overlapping or nested entity spans.
3. **Deterministic Replacer (`src/replacer.py`)**: Uses `Faker` to generate fake data. It computes a stable cryptographic hash of the original text as a seed to ensure that **the same original value is always replaced with the same fake value** across all sections of the document.
4. **Evaluation Pipeline (`evaluation/`)**: Automatically generates a ground-truth CSV template and calculates micro-level Precision, Recall, and F1-score once reviewed.

---

## 2. Setup and Installation

### Prerequisites
- Python 3.11+
- Virtual environment tool (standard `venv`)

### Installation Instructions

1. Clone or navigate to the project directory:
   ```bash
   cd pii-redaction
   ```

2. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Download the required spaCy model (if it wasn't pre-installed during pip installation):
   ```bash
   python -m spacy download en_core_web_lg
   ```

---

## 3. Running Instructions

### Execution

To run the redaction engine on the Red Herring Prospectus:
```bash
python main.py
```

This command will:
1. Locate the source PDF in the workspace (or look for `input/Red Herring Prospectus.docx`).
2. Convert it automatically to `input/Red Herring Prospectus.docx` using `pdf2docx` (if the DOCX is missing).
3. Redact the document and save it to `output/Red_Herring_Prospectus_Redacted.docx`.
4. Export the deduplicated replacement log to `replacement_log.csv`.
5. Generate the annotation template at `evaluation/ground_truth_template.csv`.

### Running Tests

To run the automated unit tests:
```bash
pytest
```

### Running Evaluation

After completing step 3, you can run the evaluation script to view the metrics:
```bash
python evaluation/evaluate.py
```

---

## 4. Design Tradeoffs & Limitations

### Tradeoffs
- **NLP vs. Rules**: spaCy's NER model `en_core_web_lg` provides great general semantic coverage but can introduce false positives (e.g. classifying product names as organizations). To mitigate this, custom high-precision regex detectors override NLP predictions for structured data (like emails, phone numbers, and SSNs).
- **Run-Level Text Modification**: Splitting paragraphs into runs means a multi-word entity might be split across separate XML tags (e.g. `Kushal ` in one run, `Subbayya Hegde` in another). The redactor resolves this by mapping the entity offsets back to individual runs, writing the replacement to the first run, and clearing the text in subsequent overlapping runs, preserving formatting at the cost of slight XML structure modification.

### Limitations
- **Image-Based PII**: PII embedded inside bitmap images (like the scanned PAN card on page 121) is not redacted since the tool processes DOCX XML elements. For image redaction, an OCR-based pixel masking step is required.
- **Context-Free Dates**: Dates like "December 10, 2025" in the document header are classified as general dates (`DATE`) unless surrounded by birth-related keywords, in which case they are treated as `DATE_OF_BIRTH` to avoid unnecessary over-redaction of standard business dates.
