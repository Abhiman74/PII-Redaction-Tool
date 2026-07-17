import os
import sys
import tempfile
import pandas as pd
import streamlit as st
from docx import Document

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.redactor import DocxRedactor
from src.replacer import PIIReplacer
from src.detector import HybridDetector, RegexDetector, PresidioDetector, SpacyDetector
from evaluation.evaluate import calculate_metrics

# Set page config
st.set_page_config(
    page_title="PII Redaction Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling via markdown
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F3F4F6;
        border-radius: 8px;
        padding: 1.5rem;
        border-left: 5px solid #3B82F6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1F2937;
    }
    .metric-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        color: #6B7280;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<div class="main-header">🛡️ Enterprise PII Redaction Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Detect and replace sensitive information with realistic fake data, preserving document layout and formatting.</div>', unsafe_allow_html=True)

    # Sidebar: Configuration
    st.sidebar.header("📁 Document Settings")
    uploaded_file = st.sidebar.file_uploader(
        "Upload Source File", 
        type=["docx", "pdf"],
        help="Upload a Microsoft Word (.docx) or PDF document to redact."
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Redaction Filters")
    st.sidebar.write("Select PII types to search and replace:")

    # Map checkboxes to PII types
    redact_names = st.sidebar.checkbox("Full Names (PERSON)", value=True)
    redact_emails = st.sidebar.checkbox("Email Addresses (EMAIL_ADDRESS)", value=True)
    redact_phones = st.sidebar.checkbox("Phone Numbers (PHONE_NUMBER)", value=True)
    redact_orgs = st.sidebar.checkbox("Companies & Orgs (ORG/COMPANY)", value=True)
    redact_locations = st.sidebar.checkbox("Locations & Addresses (GPE/LOC)", value=True)
    redact_ssn = st.sidebar.checkbox("Social Security Numbers (US_SSN)", value=True)
    redact_cards = st.sidebar.checkbox("Credit Cards (CREDIT_CARD)", value=True)
    redact_dob = st.sidebar.checkbox("Dates of Birth (DATE_OF_BIRTH)", value=True)
    redact_ips = st.sidebar.checkbox("IP Addresses (IP_ADDRESS)", value=True)
    redact_pan = st.sidebar.checkbox("Indian PAN Cards (INDIAN_PAN)", value=True)
    redact_pins = st.sidebar.checkbox("Postal Codes (POSTAL_CODE)", value=True)

    st.sidebar.markdown("---")
    run_redaction = st.sidebar.button("🚀 Run Redactor", type="primary", disabled=uploaded_file is None)

    # 1. Global Redaction Execution Block (Runs regardless of active tab)
    if run_redaction and uploaded_file is not None:
        with st.spinner("Processing document... This may take a few moments for large files."):
            try:
                # Create temp directories to store file
                with tempfile.TemporaryDirectory() as tmpdir:
                    input_path = os.path.join(tmpdir, uploaded_file.name)
                    # Save uploaded file locally
                    with open(input_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    docx_path = input_path
                    # If PDF, convert it first
                    if uploaded_file.name.endswith(".pdf"):
                        docx_path = os.path.join(tmpdir, "converted.docx")
                        from pdf2docx import Converter
                        cv = Converter(input_path)
                        cv.convert(docx_path, start=0, end=None)
                        cv.close()

                    # Initialize Redactor
                    redactor = DocxRedactor(use_presidio=True, use_spacy=True)
                    
                    # Custom filter override based on checkboxes
                    active_types = set()
                    if redact_names: active_types.add("PERSON")
                    if redact_emails: active_types.add("EMAIL_ADDRESS")
                    if redact_phones: active_types.add("PHONE_NUMBER")
                    if redact_orgs: active_types.update(["ORG", "COMPANY"])
                    if redact_locations: active_types.update(["GPE", "LOCATION", "LOC", "FAC"])
                    if redact_ssn: active_types.add("US_SSN")
                    if redact_cards: active_types.add("CREDIT_CARD")
                    if redact_dob: active_types.add("DATE_OF_BIRTH")
                    if redact_ips: active_types.add("IP_ADDRESS")
                    if redact_pan: active_types.add("INDIAN_PAN")
                    if redact_pins: active_types.add("POSTAL_CODE")

                    # Override detector detect to filter based on checkboxes
                    original_detect = redactor.detector.detect
                    def filtered_detect(text: str):
                        entities = original_detect(text)
                        return [e for e in entities if e.entity_type in active_types]
                    redactor.detector.detect = filtered_detect

                    # Redact
                    output_path = os.path.join(tmpdir, "redacted.docx")
                    total_redactions = redactor.redact_document(docx_path, output_path)

                    # Save to session state so we can access across re-runs
                    with open(output_path, "rb") as f:
                        st.session_state["redacted_data"] = f.read()
                    st.session_state["redaction_log"] = redactor.redaction_log
                    st.session_state["total_redactions"] = total_redactions
                    st.session_state["processed_filename"] = uploaded_file.name

                    # Save to output folder locally as backup
                    os.makedirs("output", exist_ok=True)
                    backup_path = os.path.join("output", "Red_Herring_Prospectus_Redacted.docx")
                    with open(backup_path, "wb") as f_backup:
                        f_backup.write(st.session_state["redacted_data"])

                    st.balloons()

            except Exception as e:
                st.error(f"Failed to redact document: {e}")
                import traceback
                st.code(traceback.format_exc())

    # 2. Global Success & Download Banner (Always visible at the top once processed)
    if "redacted_data" in st.session_state:
        st.success(f"🎉 Redaction Completed! Processed **{st.session_state['total_redactions']}** PII entities in `{st.session_state['processed_filename']}`.")
        
        # Provide download button
        output_name = st.session_state['processed_filename'].rsplit(".", 1)[0] + "_Redacted.docx"
        st.download_button(
            label="📥 Download Redacted DOCX",
            data=st.session_state["redacted_data"],
            file_name=output_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary"
        )
        st.markdown("---")

    # Tabs
    tab_redact, tab_logs, tab_metrics = st.tabs([
        "🛡️ Document Redactor", 
        "📋 Replacement Logs", 
        "📈 NLP Metrics Dashboard"
    ])

    # REDACT TAB
    with tab_redact:
        if uploaded_file is None:
            st.info("👈 Please upload a PDF or DOCX file in the sidebar to begin.")
        else:
            st.write(f"Loaded: `{uploaded_file.name}` ({uploaded_file.size / 1024:.1f} KB)")
            
            # Show configuration preview
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Configured Detectors")
                detector_status = []
                if redact_names: detector_status.append("✔️ Names (PERSON)")
                if redact_emails: detector_status.append("✔️ Emails")
                if redact_phones: detector_status.append("✔️ Phone Numbers")
                if redact_orgs: detector_status.append("✔️ Organization Names")
                if redact_locations: detector_status.append("✔️ Addresses/Locations")
                if redact_ssn: detector_status.append("✔️ US SSNs")
                if redact_cards: detector_status.append("✔️ Credit Cards (Luhn)")
                if redact_dob: detector_status.append("✔️ Dates of Birth")
                if redact_ips: detector_status.append("✔️ IP Addresses")
                if redact_pan: detector_status.append("✔️ Indian PAN Numbers")
                if redact_pins: detector_status.append("✔️ PIN/Postal Codes")
                st.write(", ".join(detector_status))
                
            with col2:
                st.markdown("### Output Specifications")
                st.write("- **Format**: Microsoft Word (.docx)")
                st.write("- **Consistency**: Every repeating entity maps to the same deterministic fake value")
                st.write("- **Styles**: Preserves fonts, tables, cell structures, headers, and footers")

    # LOGS TAB
    with tab_logs:
        st.markdown("### Replacement Log Mapping")
        st.write("This table logs every unique original entity replaced by the deterministic fake generator.")
        
        if "redaction_log" in st.session_state and st.session_state["redaction_log"]:
            df = pd.DataFrame(st.session_state["redaction_log"], columns=["Original", "Replacement", "Entity Type"])
            df = df.drop_duplicates().reset_index(drop=True)
            st.dataframe(df, use_container_width=True)
        else:
            # Check if there is a saved replacement_log.csv
            if os.path.exists("replacement_log.csv"):
                df = pd.read_csv("replacement_log.csv")
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No redaction logs available. Run the redactor first.")

    # METRICS TAB
    with tab_metrics:
        st.markdown("### NLP Metrics Evaluation Dashboard")
        
        # Check for annotated ground-truth files
        annotated_path = "evaluation/ground_truth_annotated.csv"
        mock_path = "evaluation/ground_truth_mock_annotated.csv"
        
        active_path = None
        if os.path.exists(annotated_path):
            active_path = annotated_path
            st.success("Found manually annotated ground-truth labels. Visualizing final metrics...")
        elif os.path.exists(mock_path):
            active_path = mock_path
            st.warning("Manually annotated full list not found. Displaying sample mock verified evaluation...")
            
        if active_path:
            try:
                df_eval = pd.read_csv(active_path)
                df_eval["Review (TP/FP/FN)"] = df_eval["Review (TP/FP/FN)"].str.strip().str.upper()
                
                # Calculate metrics
                metrics = calculate_metrics(df_eval)
                
                # Render overall metrics in cards
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">Precision</div>
                        <div class="metric-value">{metrics['Precision'] * 100:.2f}%</div>
                        <div class="metric-label" style="font-size:0.75rem;">TP / (TP + FP)</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col2:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left-color: #10B981;">
                        <div class="metric-label">Recall</div>
                        <div class="metric-value">{metrics['Recall'] * 100:.2f}%</div>
                        <div class="metric-label" style="font-size:0.75rem;">TP / (TP + FN)</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col3:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left-color: #8B5CF6;">
                        <div class="metric-label">F1-Score</div>
                        <div class="metric-value">{metrics['F1-score'] * 100:.2f}%</div>
                        <div class="metric-label" style="font-size:0.75rem;">Harmonic Mean</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Classification counts
                st.markdown("---")
                st.markdown("### Classification Counts")
                st.write(f"**True Positives (TP)**: {metrics['TP']} | **False Positives (FP)**: {metrics['FP']} | **False Negatives (FN)**: {metrics['FN']}")
                
                # Per-entity breakdown
                st.markdown("### Per-Entity Metrics Table")
                entity_records = []
                for ent_type, group in df_eval.groupby("Entity Type"):
                    ent_metrics = calculate_metrics(group)
                    entity_records.append({
                        "Entity Type": ent_type,
                        "TP": ent_metrics["TP"],
                        "FP": ent_metrics["FP"],
                        "FN": ent_metrics["FN"],
                        "Precision": f"{ent_metrics['Precision'] * 100:.2f}%",
                        "Recall": f"{ent_metrics['Recall'] * 100:.2f}%",
                        "F1-score": f"{ent_metrics['F1-score'] * 100:.2f}%"
                    })
                st.table(pd.DataFrame(entity_records))
                
                st.markdown("""
                > **Accuracy Disclaimer**: Accuracy is not computed because in Named Entity Recognition, the number of True Negatives 
                > (words that are not PII) is extremely large, making Accuracy a misleading and inflated metric.
                """)
                
            except Exception as e:
                st.error(f"Error computing evaluation stats: {e}")
        else:
            st.info("Evaluation data not found. Run a redaction to generate templates.")

if __name__ == "__main__":
    main()
