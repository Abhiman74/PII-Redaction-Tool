# Evaluation Report: PII Redaction Tool

This report describes the evaluation methodology, metric definitions, and architectural considerations for validating the performance of the PII Redaction Tool.

---

## 1. Evaluation Methodology

PII detection is fundamentally a **Named Entity Recognition (NER) / Information Extraction** task rather than a document-level classification task. In NER, we identify spans of text (intervals of characters) and assign them to specific semantic categories (e.g. `PERSON`, `EMAIL_ADDRESS`).

To evaluate this system scientifically:
1. **Annotation Template Generation**: The hybrid detector scans the document and produces predictions including start/end offsets, original text, and entity types. These are exported to `evaluation/ground_truth_template.csv`.
2. **Human-in-the-Loop Review**: A human reviewer inspects the document alongside the template and classifies each prediction as either a True Positive (`TP`) or a False Positive (`FP`). Additionally, any missed PII occurrences are recorded as False Negatives (`FN`).
3. **Metrics Calculation**: The evaluation script `evaluation/evaluate.py` reads the reviewed CSV file and computes overall and per-entity metrics.

---

## 2. Definitions and Formulae

### True Positive (TP)
An entity predicted by the tool that is indeed a sensitive PII token of the assigned type.
*Example: Predicting "Kushal Subbayya Hegde" as `PERSON` in a promoter context.*

### False Positive (FP)
An entity predicted by the tool that is either not PII, or has been assigned to the incorrect entity type.
*Example: Redacting "SEBI ICDR Regulations" as `ORG` (when it is a regulation document/law rather than an active corporate organization).*

### False Negative (FN)
A sensitive PII token present in the document that the tool completely failed to detect.
*Example: Failing to detect a phone number or a specific personal name in a densely nested footnote run.*

### True Negative (TN)
All non-PII tokens (words/characters) in the document that were correctly left unredacted.
*Note: In NER tasks, the count of True Negatives is virtually infinite or extremely large (proportional to the number of words/tokens in the document).*

---

### Mathematical Formulae

#### Precision
Precision measures the accuracy of positive predictions (i.e. of the entities we redacted, how many were actually PII).
$$\text{Precision} = \frac{TP}{TP + FP}$$

#### Recall
Recall measures the completeness of positive detections (i.e. of all the actual PII in the document, how many did we successfully find and redact).
$$\text{Recall} = \frac{TP}{TP + FN}$$

#### F1-Score
F1-score is the harmonic mean of Precision and Recall, providing a single balanced metric that penalizes extreme imbalances between the two.
$$F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

---

## 3. Why Accuracy is Misleading for NER

In classification tasks, Accuracy is defined as:
$$\text{Accuracy} = \frac{TP + TN}{TP + TN + FP + FN}$$

For NER, using Accuracy is highly discouraged and misleading in standard NLP literature (such as MUC, CoNLL, and SemEval) for the following reasons:

1. **Class Imbalance (TN Dominance)**: The vast majority of text in any document (often $>98\%$) consists of normal, non-PII tokens (nouns, verbs, prepositions). This makes $TN$ extremely large. As a result, even a completely naive model that redacts absolutely nothing will have an Accuracy of $>98\%$, despite having a Recall of $0.0$.
2. **Tokenization Ambiguity**: Defining a single "negative" token is subjective. Does a space or punctuation count as a True Negative? This makes calculating a stable value for $TN$ mathematically arbitrary.
3. **Truthfulness in Reporting**:
   > [!IMPORTANT]
   > Accuracy cannot be truthfully computed because a complete set of true negatives requires fully annotated ground-truth labels for every token in the document. Precision, Recall, and F1-score are the industry-accepted evaluation metrics for PII and entity extraction.

---

## 4. How to Run the Evaluation Pipeline

1. Run the main redactor script to generate the redacted document and the ground-truth template:
   ```bash
   python main.py
   ```
2. Open `evaluation/ground_truth_template.csv` in a spreadsheet editor or text editor.
3. Verify each row. Change the `Review (TP/FP/FN)` value to `TP` or `FP`. Add any missed entities from the document as new rows with `FN` in that column.
4. Save the file as `evaluation/ground_truth_annotated.csv`.
5. Run the evaluation script:
   ```bash
   python evaluation/evaluate.py
   ```
