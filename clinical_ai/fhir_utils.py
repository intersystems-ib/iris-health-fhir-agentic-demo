"""
Utility functions for FHIR operations.

This module provides shared functions for interacting with the IRIS FHIR server.
These are used by both main.py and api.py before the CrewAI workflow begins.
"""

import os
import requests
from requests.auth import HTTPBasicAuth


def fetch_observation_from_fhir(observation_id: str) -> dict:
    """
    Fetch FHIR Observation from IRIS FHIR server.

    This is a pre-workflow utility function that retrieves and parses
    a FHIR Observation before the CrewAI agents start their work.

    Args:
        observation_id: FHIR Observation ID (e.g., "obs-creatinine-001" or "Observation/obs-creatinine-001")

    Returns:
        Dictionary containing:
        - patient_ref: FHIR patient reference (e.g., "Patient/123")
        - observation_ref: Full FHIR observation reference
        - test_name: Human-readable test name
        - value: Numeric value
        - unit: Unit of measurement
        - status: Mapped status (abnormal, critical, normal)
        - observation_data: Full FHIR Observation resource

    Raises:
        requests.exceptions.RequestException: If FHIR server communication fails
    """
    # Extract observation ID if full reference is provided
    if "/" in observation_id:
        observation_id = observation_id.split("/")[-1]

    # Get FHIR server configuration from environment
    host = os.getenv("IRIS_HOST", "localhost")
    fhir_port = os.getenv("IRIS_FHIR_PORT", "52774")
    username = os.getenv("IRIS_USERNAME", "_SYSTEM")
    password = os.getenv("IRIS_PASSWORD", "SYS")

    fhir_base_url = f"http://{host}:{fhir_port}/interop/fhir/r4"
    auth = HTTPBasicAuth(username, password)

    # Fetch the observation
    url = f"{fhir_base_url}/Observation/{observation_id}"
    headers = {"Accept": "application/fhir+json"}

    print(f"📡 Fetching Observation from FHIR server: {observation_id}")
    response = requests.get(url, headers=headers, auth=auth)
    response.raise_for_status()

    observation = response.json()

    # Extract relevant data
    patient_ref = observation.get("subject", {}).get("reference", "Patient/Unknown")

    # Extract lab test details
    code = observation.get("code", {})
    test_name = code.get("text") or code.get("coding", [{}])[0].get("display", "Unknown Test")

    value_quantity = observation.get("valueQuantity", {})
    value = value_quantity.get("value", 0.0)
    unit = value_quantity.get("unit", "")

    # Determine status
    status = observation.get("status", "final")
    interpretation = observation.get("interpretation", [{}])[0].get("coding", [{}])[0].get("code", "")

    # Map interpretation to status
    if interpretation in ["H", "HH", "A", "AA"]:
        result_status = "abnormal"
    elif interpretation in ["L", "LL"]:
        result_status = "abnormal"
    elif interpretation == "C":
        result_status = "critical"
    else:
        result_status = "normal"

    return {
        "patient_ref": patient_ref,
        "observation_ref": f"Observation/{observation_id}",
        "test_name": test_name,
        "value": value,
        "unit": unit,
        "status": result_status,
        "observation_data": observation
    }
