"""
Gradio UI for Clinical AI Demo.

One screen, one story, clear states:
1. Submit a clinical event (Observation)
2. System is working (polling status)
3. Here is what happened, why, and where it lives in IRIS
"""

import gradio as gr
import requests
import json
import time
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from requests.auth import HTTPBasicAuth

# Import IRIS client for SQL queries
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from clinical_ai.iris_client import IRISClient


# ============================================================================
# Configuration
# ============================================================================
FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "http://localhost:52773/interop/fhir/r4")
FHIR_USERNAME = os.getenv("IRIS_USERNAME", "superuser")
FHIR_PASSWORD = os.getenv("IRIS_PASSWORD", "SYS")
PATIENT_ID = "1"  # Fixed for demo

# IRIS Portal URLs
IRIS_PRODUCTION_URL = "http://localhost:52773/csp/healthshare/interop/EnsPortal.ProductionConfig.zen?PRODUCTION=clinicalai.ClinicalEventOrchestration"
IRIS_MESSAGE_VIEWER_URL = "http://localhost:52773/csp/healthshare/interop/EnsPortal.MessageViewer.zen?$NAMESPACE=INTEROP&"
IRIS_SQL_EXPLORER_URL = "http://localhost:52773/csp/sys/exp/%25CSP.UI.Portal.SQL.Home.zen?$NAMESPACE=INTEROP"


# ============================================================================
# FHIR Helper Functions
# ============================================================================
def post_observation(value: float, timestamp: str) -> Tuple[bool, str, Optional[str]]:
    """
    Post a creatinine observation to FHIR server.

    Returns:
        Tuple of (success: bool, message: str, observation_id: Optional[str])
    """
    try:
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "2160-0",
                        "display": "Creatinine [Mass/volume] in Serum or Plasma"
                    }
                ],
                "text": "Serum creatinine"
            },
            "subject": {
                "reference": f"Patient/{PATIENT_ID}"
            },
            "effectiveDateTime": timestamp,
            "valueQuantity": {
                "value": value,
                "unit": "mg/dL",
                "system": "http://unitsofmeasure.org",
                "code": "mg/dL"
            },
            "interpretation": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": "H"
                        }
                    ]
                }
            ]
        }

        url = f"{FHIR_BASE_URL}/Observation"
        headers = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
            "Prefer": "return=representation"
        }
        auth = HTTPBasicAuth(FHIR_USERNAME, FHIR_PASSWORD)

        print(f"Posting observation to {url}")
        print(f"Auth: {FHIR_USERNAME}:***")

        response = requests.post(url, json=observation, headers=headers, auth=auth, timeout=10)

        # Check for error response
        if not response.ok:
            error_detail = f"HTTP {response.status_code}"
            try:
                error_body = response.json()
                if isinstance(error_body, dict):
                    # Try to get FHIR OperationOutcome details
                    if error_body.get("resourceType") == "OperationOutcome":
                        issues = error_body.get("issue", [])
                        if issues:
                            diagnostics = issues[0].get("diagnostics", "")
                            severity = issues[0].get("severity", "")
                            error_detail = f"HTTP {response.status_code} - {severity}: {diagnostics}"
                    else:
                        error_detail = f"HTTP {response.status_code} - {error_body}"
            except:
                error_detail = f"HTTP {response.status_code} - {response.text[:200]}"

            return False, f"Error posting observation: {error_detail}", None

        result = response.json()
        observation_id = result.get("id")

        print(f"Successfully created observation: {observation_id}")
        return True, f"Observation/{observation_id}", observation_id

    except requests.exceptions.Timeout:
        return False, "Error posting observation: Request timeout", None
    except requests.exceptions.ConnectionError as e:
        return False, f"Error posting observation: Cannot connect to FHIR server - {str(e)}", None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error posting observation: {str(e)}", None


def poll_diagnostic_report(observation_id: str, max_attempts: int = 30, delay: int = 2) -> Optional[Dict[str, Any]]:
    """
    Poll for DiagnosticReport referencing the given observation.

    Returns:
        DiagnosticReport resource if found, None otherwise
    """
    url = f"{FHIR_BASE_URL}/DiagnosticReport"
    params = {"result": f"Observation/{observation_id}"}
    headers = {"Accept": "application/fhir+json"}
    auth = HTTPBasicAuth(FHIR_USERNAME, FHIR_PASSWORD)

    for attempt in range(max_attempts):
        try:
            response = requests.get(url, params=params, headers=headers, auth=auth)
            response.raise_for_status()

            bundle = response.json()
            total = bundle.get("total", 0)

            if total > 0 and bundle.get("entry"):
                # Found the DiagnosticReport
                return bundle["entry"][0]["resource"]

            # Not found yet, wait and try again
            time.sleep(delay)
        except Exception as e:
            print(f"Error polling DiagnosticReport: {e}")
            time.sleep(delay)

    return None


def extract_case_id_from_report(diagnostic_report: Dict[str, Any]) -> Optional[str]:
    """
    Extract caseId from DiagnosticReport extension.

    Looks for nested extension structure:
    extension[].url == "http://example.org/fhir/StructureDefinition/ai-evaluation-metadata"
      -> extension[].url == "caseId"
         -> valueString
    """
    extensions = diagnostic_report.get("extension", [])

    for ext in extensions:
        # Check if this is the ai-evaluation-metadata extension
        if "ai-evaluation-metadata" in ext.get("url", ""):
            # Look for nested caseId extension
            nested_extensions = ext.get("extension", [])
            for nested_ext in nested_extensions:
                if nested_ext.get("url") == "caseId":
                    case_id = nested_ext.get("valueString")
                    if case_id:
                        print(f"Found caseId in extension: {case_id}")
                        return case_id

    # Fallback: try top-level extension with direct caseId URL
    for ext in extensions:
        if ext.get("url") == "http://intersystems.com/fhir/extension/case-id":
            case_id = ext.get("valueString")
            if case_id:
                print(f"Found caseId in top-level extension: {case_id}")
                return case_id

    # Fallback: try identifier
    identifiers = diagnostic_report.get("identifier", [])
    for identifier in identifiers:
        if identifier.get("system") == "http://intersystems.com/fhir/case-id":
            case_id = identifier.get("value")
            if case_id:
                print(f"Found caseId in identifier: {case_id}")
                return case_id

    print("⚠️  Warning: Could not find caseId in DiagnosticReport")
    return None


# ============================================================================
# SQL Helper Functions
# ============================================================================
def get_case_data(case_id: str) -> Optional[Dict[str, Any]]:
    """Fetch Case data from IRIS SQL."""
    try:
        with IRISClient() as client:
            sql = """
                SELECT CaseId, TriggerObservationRef, RiskLevel, Confidence,
                       ReasoningSummary, CreatedAt, PatientRef
                FROM clinicalai_data.Cases
                WHERE CaseId = ?
            """
            result = client.query_one(sql, [case_id])
            return result
    except Exception as e:
        print(f"Error fetching case data: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_recommendations(case_id: str) -> list:
    """Fetch Recommendations from IRIS SQL."""
    try:
        with IRISClient() as client:
            sql = """
                SELECT ActionType, ActionText, Timeframe
                FROM clinicalai_data.CaseRecommendations
                WHERE CaseId = ?
            """
            results = client.query(sql, [case_id])
            return results
    except Exception as e:
        print(f"Error fetching recommendations: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_evidence(case_id: str) -> list:
    """Fetch Evidence from IRIS SQL."""
    try:
        with IRISClient() as client:
            sql = """
                SELECT GuidelineId, ChunkId, Similarity, Excerpt
                FROM clinicalai_data.CaseEvidences
                WHERE CaseId = ?
            """
            results = client.query(sql, [case_id])
            return results
    except Exception as e:
        print(f"Error fetching evidence: {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================================================
# UI Formatting Functions
# ============================================================================
def format_status_message(message: str, timestamp: str = None) -> str:
    """Format a single status message with timestamp."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    return f"[{timestamp}] {message}"


def append_status(current_status: str, new_message: str) -> str:
    """Append a new status message to the history."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] {new_message}"

    if current_status:
        return f"{current_status}\n{formatted_message}"
    return formatted_message


def format_diagnostic_report(report: Dict[str, Any]) -> str:
    """Format DiagnosticReport summary."""
    try:
        report_id = report.get("id", "Unknown")
        conclusion = report.get("conclusion", "No summary available")

        output = f"""## Clinical Output (FHIR)

✅ **DiagnosticReport created:** `DiagnosticReport/{report_id}`

### Summary
{conclusion}

---
"""
        return output
    except Exception as e:
        return f"Error formatting DiagnosticReport: {str(e)}"


def format_case_sql(case_data: Optional[Dict[str, Any]]) -> str:
    """Format Case SQL data."""
    if not case_data:
        return "**AI Case stored in IRIS**\n\nNo case data found."

    return f"""**AI Case stored in IRIS**

| Field | Value |
|-------|-------|
| Case ID | `{case_data.get('CaseId', 'N/A')}` |
| Patient | `{case_data.get('PatientRef', 'N/A')}` |
| Trigger Observation | `{case_data.get('TriggerObservationRef', 'N/A')}` |
| Risk Level | {case_data.get('RiskLevel', 'N/A')} |
| Confidence | {case_data.get('Confidence', 'N/A')} |
| Created At | {case_data.get('CreatedAt', 'N/A')} |

**Reasoning Summary:**
{case_data.get('ReasoningSummary', 'N/A')}
"""


def format_recommendations_sql(recommendations: list) -> str:
    """Format Recommendations SQL data."""
    if not recommendations:
        return "**Persisted recommendations**\n\nNo recommendations found."

    output = "**Persisted recommendations**\n\n"
    for i, rec in enumerate(recommendations, 1):
        action_type = rec.get('ActionType', 'N/A')
        action_text = rec.get('ActionText', 'N/A')
        timeframe = rec.get('Timeframe', 'N/A')

        output += f"{i}. **{action_type}** ({timeframe})\n"
        output += f"   {action_text}\n\n"

    return output


def format_evidence_sql(evidence: list) -> str:
    """Format Evidence SQL data."""
    if not evidence:
        return "**Guideline evidence used by the AI**\n\nNo evidence found."

    output = "**Guideline evidence used by the AI**\n\n"
    for i, ev in enumerate(evidence, 1):
        similarity = ev.get('Similarity', 0)
        excerpt = ev.get('Excerpt', 'N/A')
        guideline_id = ev.get('GuidelineId', 'N/A')
        chunk_id = ev.get('ChunkId', 'N/A')

        if len(excerpt) > 200:
            excerpt = excerpt[:200] + "..."

        output += f"""**Evidence {i}**
- **Guideline:** {guideline_id}
- **Chunk ID:** {chunk_id}
- **Similarity:** {similarity:.4f}
- **Excerpt:** {excerpt}

---
"""

    return output


def format_iris_links() -> str:
    """Format IRIS portal links."""
    return """**IRIS Integration**

🔗 [IRIS Production]({})

🔗 [Message Viewer]({})

🔗 [SQL Explorer]({})
""".format(IRIS_PRODUCTION_URL, IRIS_MESSAGE_VIEWER_URL, IRIS_SQL_EXPLORER_URL)


# ============================================================================
# Main Workflow Function
# ============================================================================
def trigger_ai_workflow(value: float, timestamp: str):
    """
    Main workflow function that:
    1. Posts observation
    2. Polls for DiagnosticReport
    3. Fetches SQL data
    4. Returns all UI updates
    """
    status_history = ""

    # Step 1: Post observation
    status_history = append_status(status_history, "🚀 Posting observation to FHIR server...")
    yield (
        status_history,
        "",  # results
        "",  # case_sql
        "",  # recommendations_sql
        "",  # evidence_sql
        ""   # fhir_json
    )

    success, message, observation_id = post_observation(value, timestamp)

    if not success:
        status_history = append_status(status_history, f"❌ {message}")
        yield (
            status_history,
            "",  # results
            "",  # case_sql
            "",  # recommendations_sql
            "",  # evidence_sql
            ""   # fhir_json
        )
        return

    observation_ref = message
    status_history = append_status(status_history, f"✅ Observation created: {observation_ref}")
    status_history = append_status(status_history, "⏳ AI evaluation in progress...")
    status_history = append_status(status_history, "   📊 Retrieving patient context...")
    status_history = append_status(status_history, "   📖 Evaluating clinical guidelines...")
    status_history = append_status(status_history, "   🤖 Generating follow-up report...")

    yield (
        status_history,
        "",  # results
        "",  # case_sql
        "",  # recommendations_sql
        "",  # evidence_sql
        ""   # fhir_json
    )

    # Step 2: Poll for DiagnosticReport
    # Give it some time before starting to poll
    time.sleep(2)

    status_history = append_status(status_history, "🔍 Waiting for DiagnosticReport...")
    yield (
        status_history,
        "",  # results
        "",  # case_sql
        "",  # recommendations_sql
        "",  # evidence_sql
        ""   # fhir_json
    )

    diagnostic_report = poll_diagnostic_report(observation_id)

    if not diagnostic_report:
        status_history = append_status(status_history, "❌ Timeout waiting for DiagnosticReport. The AI workflow may still be processing.")
        yield (
            status_history,
            "",  # results
            "",  # case_sql
            "",  # recommendations_sql
            "",  # evidence_sql
            ""   # fhir_json
        )
        return

    report_id = diagnostic_report.get("id")
    status_history = append_status(status_history, f"✅ DiagnosticReport found: DiagnosticReport/{report_id}")

    # Step 3: Extract case ID from DiagnosticReport
    status_history = append_status(status_history, "🔎 Extracting case ID from DiagnosticReport...")
    yield (
        status_history,
        "",  # results
        "",  # case_sql
        "",  # recommendations_sql
        "",  # evidence_sql
        ""   # fhir_json
    )

    case_id = extract_case_id_from_report(diagnostic_report)

    if not case_id:
        status_history = append_status(status_history, "⚠️  Warning: Could not find caseId in DiagnosticReport extensions")
        results_output = format_diagnostic_report(diagnostic_report)
        fhir_json_output = json.dumps(diagnostic_report, indent=2)

        yield (
            status_history,
            results_output,
            "**AI Case stored in IRIS**\n\nCaseId not found in DiagnosticReport",
            "**Persisted recommendations**\n\nCaseId not found",
            "**Guideline evidence used by the AI**\n\nCaseId not found",
            fhir_json_output
        )
        return

    status_history = append_status(status_history, f"✅ Found caseId: {case_id}")

    # Step 4: Fetch SQL data
    status_history = append_status(status_history, "💾 Fetching data from IRIS SQL tables...")
    yield (
        status_history,
        "",  # results
        "",  # case_sql
        "",  # recommendations_sql
        "",  # evidence_sql
        ""   # fhir_json
    )

    case_data = get_case_data(case_id)
    recommendations = get_recommendations(case_id)
    evidence = get_evidence(case_id)

    status_history = append_status(status_history, f"✅ Retrieved {len(recommendations)} recommendations and {len(evidence)} evidence items")

    # Step 5: Format results
    results_output = format_diagnostic_report(diagnostic_report)
    case_sql_output = format_case_sql(case_data)
    recommendations_sql_output = format_recommendations_sql(recommendations)
    evidence_sql_output = format_evidence_sql(evidence)
    fhir_json_output = json.dumps(diagnostic_report, indent=2)

    status_history = append_status(status_history, "🎉 Evaluation completed successfully!")

    # Final update
    yield (
        status_history,
        results_output,
        case_sql_output,
        recommendations_sql_output,
        evidence_sql_output,
        fhir_json_output
    )


# ============================================================================
# Gradio UI with Custom CSS
# ============================================================================
custom_css = """
/* Add more padding to all Gradio components */
.gradio-container {
    padding: 20px !important;
}

/* Add padding to groups (section cards) */
.gr-group {
    padding: 25px !important;
    margin: 15px 0 !important;
}

/* Add padding to markdown content */
.markdown {
    padding: 15px !important;
}

/* Add padding to textboxes and inputs */
.gr-textbox, .gr-number {
    padding: 12px !important;
}

/* Add padding to buttons */
.gr-button {
    padding: 12px 24px !important;
    margin: 10px 0 !important;
}

/* Add padding to accordions */
.gr-accordion {
    margin: 10px 0 !important;
}

.gr-accordion .label-wrap {
    padding: 12px 16px !important;
}

.gr-accordion .gr-panel {
    padding: 20px !important;
}

/* Status log styling */
.status-log {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.8;
    background-color: #f5f5f5;
    padding: 20px !important;
    border-radius: 5px;
    max-height: 400px;
    overflow-y: auto;
    white-space: pre-wrap;
}

/* IRIS links styling */
.iris-links {
    font-size: 14px;
    padding: 15px !important;
    line-height: 2;
}

.iris-links a {
    display: block;
    margin: 8px 0;
    padding: 5px 0;
}

/* Code blocks (FHIR JSON) */
.gr-code {
    padding: 15px !important;
}
"""

def create_ui():
    """Create and configure the Gradio interface."""

    with gr.Blocks(title="Clinical AI Demo - Lab Follow-up Recommendation", theme=gr.themes.Soft(), css=custom_css) as demo:
        gr.Markdown("""
        # 🏥 Clinical AI Demo - Lab Follow-up Recommendation

        **One clinical action → one AI workflow → one explainable outcome**
        """)

        with gr.Row():
            with gr.Column(scale=3):
                # ================================================================
                # Section 1: Submit a Clinical Event
                # ================================================================
                with gr.Group():
                    gr.Markdown("""
                    ## 📝 Submit a Clinical Event
                    Submit a new lab result to trigger the AI follow-up evaluation.
                    """)

                    gr.Markdown(f"**Patient:** Patient/{PATIENT_ID} (fixed for demo)")
                    gr.Markdown("**Observation type:** Creatinine (fixed for demo)")

                    value_input = gr.Number(
                        label="Value (mg/dL)",
                        value=2.1,
                        precision=1
                    )

                    timestamp_input = gr.Textbox(
                        label="Date/Time (ISO 8601 with timezone)",
                        value=datetime.now(timezone.utc).isoformat(),
                    )

                    submit_btn = gr.Button("🚀 Post Observation (Trigger AI)", variant="primary", size="lg")

                # ================================================================
                # Section 2: Workflow Status
                # ================================================================
                with gr.Group():
                    gr.Markdown("""
                    ## 📊 Workflow Status
                    """)

                    status_output = gr.Textbox(
                        label="Status Log",
                        value="Waiting for a clinical event...",
                        lines=12,
                        max_lines=12,
                        interactive=False,
                        elem_classes=["status-log"]
                    )

                # ================================================================
                # Section 3: Results & Explainability
                # ================================================================
                with gr.Group():
                    gr.Markdown("""
                    ## 📋 Results & Explainability
                    """)

                    results_output = gr.Markdown("")

                    with gr.Accordion("View DiagnosticReport (FHIR JSON)", open=False):
                        fhir_json_output = gr.Code(language="json", label="DiagnosticReport JSON")

                    gr.Markdown("---")
                    gr.Markdown("### 🔍 Explainability & Persistence (IRIS SQL)")

                    with gr.Accordion("1) Case (SQL)", open=True):
                        case_sql_output = gr.Markdown("")

                    with gr.Accordion("2) Recommendations (SQL)", open=True):
                        recommendations_sql_output = gr.Markdown("")

                    with gr.Accordion("3) Evidence (SQL)", open=True):
                        evidence_sql_output = gr.Markdown("")

            # Right sidebar
            with gr.Column(scale=1):
                with gr.Accordion("🔗 IRIS Integration", open=True):
                    gr.Markdown(
                        f"""**This workflow is fully orchestrated and persisted in InterSystems IRIS.**

[🔗 IRIS Production]({IRIS_PRODUCTION_URL})

[🔗 Message Viewer]({IRIS_MESSAGE_VIEWER_URL})

[🔗 SQL Explorer]({IRIS_SQL_EXPLORER_URL})
""",
                        elem_classes=["iris-links"]
                    )

        # ====================================================================
        # Event Handlers
        # ====================================================================
        submit_btn.click(
            fn=trigger_ai_workflow,
            inputs=[value_input, timestamp_input],
            outputs=[
                status_output,
                results_output,
                case_sql_output,
                recommendations_sql_output,
                evidence_sql_output,
                fhir_json_output
            ]
        )

    return demo


# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
