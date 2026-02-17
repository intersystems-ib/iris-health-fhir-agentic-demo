"""
FastAPI REST service for Lab Follow-up Recommendation Agent.

This module exposes the clinical_ai agent as a REST API.
Per ARCHITECTURE.md, this service:
1. Receives a trigger observation reference
2. Fetches the observation from IRIS FHIR server
3. Executes the CrewAI workflow
4. Returns structured JSON output

Endpoint:
    POST /evaluate

    Request body:
    {
        "TriggerObservationRef": "Observation/12",
        "CaseId": "550e8400-e29b-41d4-a716-446655440000"  // optional
    }

    Response:
    {
        "case_id": "...",
        "created_at": "...",
        "patient_ref": "Patient/123",
        "trigger_observation_ref": "Observation/12",
        "assessment": { ... },
        "recommendations": [ ... ],
        "evidence": [ ... ],
        "metadata": { ... }
    }
"""

import uuid
import os
import sys
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .crew import LabFollowupCrew
from .schemas import ClinicalRecommendationOutput
from .fhir_utils import fetch_observation_from_fhir as _fetch_observation


# ============================================================================
# Load environment variables
# ============================================================================
load_dotenv()


# ============================================================================
# FastAPI Application
# ============================================================================
app = FastAPI(
    title="Lab Follow-up Recommendation Agent API",
    description="REST API for the Lab Follow-up Recommendation Agent using InterSystems IRIS for Health + CrewAI",
    version="1.0.0"
)


# ============================================================================
# Request/Response Models
# ============================================================================
class EvaluationRequest(BaseModel):
    """Request model for /evaluate endpoint."""
    TriggerObservationRef: str = Field(
        ...,
        description="FHIR Observation reference (e.g., 'Observation/12' or just '12')",
        example="Observation/12"
    )
    CaseId: str | None = Field(
        None,
        description="Optional case ID (UUID). If not provided, one will be generated.",
        example="550e8400-e29b-41d4-a716-446655440000"
    )


# ============================================================================
# Helper Functions
# ============================================================================
def fetch_observation_from_fhir(observation_id: str) -> dict:
    """
    Fetch FHIR Observation from IRIS FHIR server (API wrapper).

    This is a thin wrapper around the shared fhir_utils function that
    converts exceptions to FastAPI HTTPExceptions.

    Args:
        observation_id: FHIR Observation ID (e.g., "obs-creatinine-001" or "Observation/obs-creatinine-001")

    Returns:
        Dictionary containing observation data and patient reference

    Raises:
        HTTPException: If observation cannot be fetched or parsed
    """
    try:
        return _fetch_observation(observation_id)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Observation '{observation_id}' not found in FHIR server"
            )
        raise HTTPException(
            status_code=502,
            detail=f"Error fetching observation from FHIR server: {str(e)}"
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to FHIR server: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error processing observation: {str(e)}"
        )


# ============================================================================
# API Endpoints
# ============================================================================
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Lab Follow-up Recommendation Agent API",
        "status": "operational",
        "version": "1.0.0",
        "framework": "CrewAI + InterSystems IRIS for Health"
    }


@app.get("/health")
async def health():
    """Detailed health check endpoint."""
    iris_host = os.getenv("IRIS_HOST", "localhost")
    iris_port = os.getenv("IRIS_FHIR_PORT", "52774")

    return {
        "status": "healthy",
        "iris_connection": {
            "host": iris_host,
            "port": iris_port,
            "configured": True
        }
    }


@app.post("/evaluate", response_model=ClinicalRecommendationOutput)
async def evaluate(request: EvaluationRequest):
    """
    Evaluate a lab observation and generate follow-up recommendations.

    This endpoint:
    1. Fetches the FHIR Observation from IRIS
    2. Executes the CrewAI agent workflow
    3. Returns structured clinical recommendations

    Args:
        request: EvaluationRequest containing TriggerObservationRef

    Returns:
        ClinicalRecommendationOutput: Structured JSON with assessment,
        recommendations, and evidence

    Raises:
        HTTPException: 404 if observation not found, 502 for FHIR errors,
        500 for workflow errors
    """
    try:
        # ====================================================================
        # Step 1: Fetch Observation from FHIR Server
        # ====================================================================
        observation_data = fetch_observation_from_fhir(request.TriggerObservationRef)

        # ====================================================================
        # Step 2: Setup CrewAI workflow
        # ====================================================================
        case_id = request.CaseId or str(uuid.uuid4())
        patient_ref = observation_data["patient_ref"]
        observation_ref = observation_data["observation_ref"]

        lab_result = {
            "test_name": observation_data["test_name"],
            "value": observation_data["value"],
            "unit": observation_data["unit"],
            "status": observation_data["status"]
        }

        print("\n" + "=" * 80)
        print("🏥 Lab Follow-up Recommendation Agent API")
        print("=" * 80)
        print(f"Case ID:            {case_id}")
        print(f"Patient:            {patient_ref}")
        print(f"Observation:        {observation_ref}")
        print(f"Lab Test:           {lab_result['test_name']}")
        print(f"Value:              {lab_result['value']} {lab_result['unit']}")
        print(f"Status:             {lab_result['status']}")
        print("=" * 80)

        # ====================================================================
        # Step 3: Execute CrewAI Workflow
        # ====================================================================
        crew = LabFollowupCrew(
            case_id=case_id,
            patient_ref=patient_ref,
            trigger_observation_ref=observation_ref,
            lab_result=lab_result
        )

        result = crew.run()

        if not result:
            raise HTTPException(
                status_code=500,
                detail="CrewAI workflow failed: Could not generate structured output"
            )

        # ====================================================================
        # Step 4: Return structured JSON (formatted with indentation)
        # ====================================================================
        print("\n" + "=" * 80)
        print("✅ Evaluation completed successfully")
        print("=" * 80 + "\n")

        return Response(
            content=json.dumps(result, indent=2, ensure_ascii=False),
            media_type="application/json",
            status_code=200
        )

    except HTTPException:
        # Re-raise HTTP exceptions (from fetch_observation_from_fhir)
        raise
    except Exception as e:
        # Catch any unexpected errors
        print(f"❌ Unexpected error in /evaluate endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Run with: uvicorn clinical_ai.api:app --reload --host 0.0.0.0 --port 8000
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
