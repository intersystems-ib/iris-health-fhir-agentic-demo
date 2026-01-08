"""
Main entrypoint for the Lab Follow-up Recommendation Agent.

This script is triggered when an abnormal lab result is detected.
It orchestrates the CrewAI workflow and returns structured JSON.

Per ARCHITECTURE.md - Execution Model:
1. IRIS receives a FHIR Observation (lab result)
2. IRIS persists the Observation in FHIR repository
3. IRIS triggers this Python process
4. CrewAI executes the workflow as a library
5. CrewAI returns structured JSON
6. IRIS persists results into SQL tables (Cases, CaseRecommendations, CaseEvidences)

IMPORTANT: CrewAI does NOT own persistence. IRIS is the system of record.

Usage:
    python clinical_ai/main.py --observation-id "obs-creatinine-001"
    python clinical_ai/main.py --observation-id "obs-creatinine-001" --case-id "custom-uuid"
"""

import argparse
import sys
import uuid
import json
import os
from dotenv import load_dotenv

# Support both direct script execution and module import
# When running as a script (python clinical_ai/main.py), add parent dir to path
if __name__ == "__main__" and __package__ is None:
    # Add the parent directory to sys.path so we can import clinical_ai as a package
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    __package__ = "clinical_ai"

from clinical_ai.crew import LabFollowupCrew
from clinical_ai.fhir_utils import fetch_observation_from_fhir


def main():
    """Main execution entrypoint."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Lab Follow-up Recommendation Agent - Agentic AI Demo"
    )
    parser.add_argument(
        "--observation-id",
        required=True,
        help="FHIR Observation ID (e.g., 'obs-creatinine-001')"
    )
    parser.add_argument(
        "--case-id",
        help="Optional case ID (UUID). If not provided, one will be generated."
    )

    args = parser.parse_args()

    # ========================================================================
    # Fetch Observation from FHIR Server
    # ========================================================================
    try:
        observation_data = fetch_observation_from_fhir(args.observation_id)
    except Exception as e:
        print(f"❌ Error fetching observation from FHIR server: {e}")
        sys.exit(1)

    # ========================================================================
    # Setup
    # ========================================================================
    case_id = args.case_id or str(uuid.uuid4())
    patient_ref = observation_data["patient_ref"]
    observation_ref = observation_data["observation_ref"]

    lab_result = {
        "test_name": observation_data["test_name"],
        "value": observation_data["value"],
        "unit": observation_data["unit"],
        "status": observation_data["status"]
    }

    print("\n" + "=" * 80)
    print("🏥 Lab Follow-up Recommendation Agent")
    print("    InterSystems IRIS for Health + CrewAI")
    print("=" * 80)
    print(f"Case ID:            {case_id}")
    print(f"Patient:            {patient_ref}")
    print(f"Observation:        {observation_ref}")
    print(f"Lab Test:           {lab_result['test_name']}")
    print(f"Value:              {lab_result['value']} {lab_result['unit']}")
    print(f"Status:             {lab_result['status']}")
    print("=" * 80)

    # ========================================================================
    # Execute CrewAI Workflow
    # ========================================================================
    # CrewAI is used strictly as a Python library
    # No CLI commands, no crewai run, no project templates
    # ========================================================================
    print("\n🤖 Initializing CrewAI workflow...\n")

    crew = LabFollowupCrew(
        case_id=case_id,
        patient_ref=patient_ref,
        trigger_observation_ref=observation_ref,
        lab_result=lab_result
    )

    result = crew.run()

    if not result:
        print("\n❌ Workflow failed: Could not generate structured output")
        sys.exit(1)

    # ========================================================================
    # Display Results
    # ========================================================================
    print("\n" + "=" * 80)
    print("📋 RESULTS")
    print("=" * 80)

    assessment = result.get("assessment", {})
    recommendations = result.get("recommendations", [])
    evidence = result.get("evidence", [])

    print(f"\n🎯 Assessment:")
    print(f"   Risk Level:  {assessment.get('risk_level', 'N/A')}")
    print(f"   Confidence:  {assessment.get('confidence', 'N/A')}")
    print(f"   Reasoning:   {assessment.get('reasoning_summary', 'N/A')}")

    print(f"\n💡 Recommendations ({len(recommendations)}):")
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. [{rec.get('action_type', 'N/A')}] {rec.get('action_text', 'N/A')}")
        if rec.get('timeframe'):
            print(f"      Timeframe: {rec.get('timeframe')}")

    print(f"\n📚 Evidence ({len(evidence)}):")
    for i, ev in enumerate(evidence, 1):
        print(f"   {i}. {ev.get('guideline_id', 'N/A')} (similarity: {ev.get('similarity', 0):.3f})")
        print(f"      Chunk: {ev.get('chunk_id', 'N/A')}")
        excerpt = ev.get('excerpt', 'N/A')
        if len(excerpt) > 100:
            excerpt = excerpt[:100] + "..."
        print(f"      \"{excerpt}\"")

    # ========================================================================
    # Output JSON
    # ========================================================================
    # Per ARCHITECTURE.md: CrewAI returns structured JSON
    # Step 6 (persistence to IRIS) would be handled by IRIS externally
    # ========================================================================
    print("\n" + "=" * 80)
    print("📄 JSON OUTPUT")
    print("=" * 80)
    print("\nStructured JSON (ready for IRIS persistence):\n")
    print(json.dumps(result, indent=2))

    print("\n" + "=" * 80)
    print("💡 Next Step: IRIS Persistence")
    print("=" * 80)
    print("\nThis JSON would be persisted by IRIS into:")
    print("  • clinicalai_data.Cases")
    print("  • clinicalai_data.CaseRecommendations")
    print("  • clinicalai_data.CaseEvidences")
    print("\nPersistence should be handled by:")
    print("  • IRIS Business Process (ObjectScript)")
    print("  • IRIS REST endpoint")
    print("  • IRIS Interoperability Production")

    # ========================================================================
    # Success
    # ========================================================================
    print("\n" + "=" * 80)
    print("✅ Lab Follow-up Agent Completed Successfully")
    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
