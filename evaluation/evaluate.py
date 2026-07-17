import os
import sys
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("evaluate")

def calculate_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate Precision, Recall, and F1-score from ground-truth annotations.
    """
    # Group by review status
    counts = df["Review (TP/FP/FN)"].value_counts()
    
    tp = int(counts.get("TP", 0))
    fp = int(counts.get("FP", 0))
    fn = int(counts.get("FN", 0))
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1-score": f1
    }

def main():
    # Paths
    template_path = "evaluation/ground_truth_template.csv"
    annotated_path = "evaluation/ground_truth_annotated.csv"
    mock_path = "evaluation/ground_truth_mock_annotated.csv"

    active_path = None
    if os.path.exists(annotated_path):
        active_path = annotated_path
        logger.info("Found manually annotated ground-truth labels at '%s'. Running evaluation...", active_path)
    elif os.path.exists(mock_path):
        active_path = mock_path
        logger.info("Manually annotated full list not found. Using sample mock verified annotations at '%s' for pipeline demonstration...", active_path)
    else:
        logger.warning("No annotated ground-truth file found.")
        print("\n=======================================================")
        print("EVALUATION NOTICE:")
        print("Metrics cannot be truthfully computed without ground-truth labels.")
        print(f"Please review and annotate the generated template at:\n  {template_path}")
        print("Set the 'Review (TP/FP/FN)' column to TP, FP, or add custom rows for FN, and save as:")
        print(f"  {annotated_path}")
        print("=======================================================\n")
        sys.exit(0)

    try:
        df = pd.read_csv(active_path)
        if "Review (TP/FP/FN)" not in df.columns:
            logger.error("Required column 'Review (TP/FP/FN)' missing in '%s'.", active_path)
            sys.exit(1)
            
        # Clean reviews
        df["Review (TP/FP/FN)"] = df["Review (TP/FP/FN)"].str.strip().str.upper()
        
        # Overall metrics
        metrics = calculate_metrics(df)
        
        print("\n=======================================================")
        print("PII REDACTION EVALUATION REPORT")
        print("=======================================================")
        print(f"Source file: {active_path}")
        print(f"Total annotated records: {len(df)}")
        print("-------------------------------------------------------")
        print(f"True Positives (TP):  {metrics['TP']}")
        print(f"False Positives (FP): {metrics['FP']}")
        print(f"False Negatives (FN): {metrics['FN']}")
        print("-------------------------------------------------------")
        print(f"Precision:            {metrics['Precision']:.4f}")
        print(f"Recall:               {metrics['Recall']:.4f}")
        print(f"F1-score:             {metrics['F1-score']:.4f}")
        
        # Per-entity metrics
        print("-------------------------------------------------------")
        print("PER-ENTITY METRICS:")
        print("-------------------------------------------------------")
        print(f"{'Entity Type':<20} | {'TP':<5} | {'FP':<5} | {'FN':<5} | {'Precision':<10} | {'Recall':<10} | {'F1-score':<10}")
        print("-" * 78)
        
        for ent_type, group in df.groupby("Entity Type"):
            ent_metrics = calculate_metrics(group)
            print(f"{ent_type:<20} | {ent_metrics['TP']:<5} | {ent_metrics['FP']:<5} | {ent_metrics['FN']:<5} | "
                  f"{ent_metrics['Precision']:<10.4f} | {ent_metrics['Recall']:<10.4f} | {ent_metrics['F1-score']:<10.4f}")
        print("=======================================================\n")

        print("Accuracy Notice:")
        print("Accuracy is generally not considered an appropriate metric for Named Entity Recognition and PII detection")
        print("because the number of True Negatives is extremely large compared to positive entities.")
        print("A complete set of true negatives requires fully annotated ground-truth labels for every token in the document.")
        print("Accuracy cannot be truthfully computed because a complete set of true negatives requires fully annotated ground-truth labels.")
        print()

    except Exception as e:
        logger.error("Failed to read or compute metrics: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
