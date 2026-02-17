"""
Tool for fetching patient clinical context from IRIS FHIR server.
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from crewai.tools import BaseTool
from typing import Type, Dict, Any
from pydantic import BaseModel, Field, PrivateAttr


class FetchPatientContextInput(BaseModel):
    """Input schema for FetchPatientContext tool."""
    patient_id: str = Field(..., description="Patient identifier")
    test_name: str = Field(..., description="Lab test name to focus context")


class FetchPatientContextTool(BaseTool):
    name: str = "Fetch Patient Clinical Context"
    description: str = """
    Retrieves relevant patient clinical context from IRIS FHIR server including:
    - Previous lab results for the same test
    - Related lab results
    - Active medications
    - Known clinical conditions
    - Recent vital signs

    Uses FHIR $everything operation to get comprehensive patient data.
    """
    args_schema: Type[BaseModel] = FetchPatientContextInput

    # Use PrivateAttr for instance attributes
    _fhir_base_url: str = PrivateAttr()
    _fhir_auth: Any = PrivateAttr()

    def __init__(self, **kwargs):
        """Initialize FHIR connection settings."""
        super().__init__(**kwargs)
        host = os.getenv("IRIS_HOST", "localhost")
        fhir_port = os.getenv("IRIS_FHIR_PORT", "52774")
        username = os.getenv("IRIS_USERNAME", "_SYSTEM")
        password = os.getenv("IRIS_PASSWORD", "SYS")

        self._fhir_base_url = f"http://{host}:{fhir_port}/interop/fhir/r4"
        self._fhir_auth = HTTPBasicAuth(username, password)

    def _run(self, patient_id: str, test_name: str) -> str:
        """
        Execute the tool.

        Args:
            patient_id: Patient identifier
            test_name: Lab test name

        Returns:
            Formatted patient context as string
        """
        try:
            # Use FHIR $everything operation to get all patient data
            url = f"{self._fhir_base_url}/Patient/{patient_id}/$everything"
            headers = {"Accept": "application/fhir+json"}

            response = requests.get(url, headers=headers, auth=self._fhir_auth)
            response.raise_for_status()

            bundle = response.json()

            # Parse the bundle to extract relevant context
            context = {
                "patient_id": patient_id,
                "recent_labs": [],
                "active_medications": [],
                "conditions": [],
                "recent_vitals": {}
            }

            if bundle.get("resourceType") == "Bundle" and bundle.get("entry"):
                for entry in bundle.get("entry", []):
                    resource = entry.get("resource", {})
                    resource_type = resource.get("resourceType")

                    # Extract Observations (labs, vitals)
                    if resource_type == "Observation":
                        self._parse_observation(resource, context)

                    # Extract MedicationRequests
                    elif resource_type == "MedicationRequest":
                        self._parse_medication(resource, context)

                    # Extract Conditions
                    elif resource_type == "Condition":
                        self._parse_condition(resource, context)

            # Format context for agent consumption
            return self._format_context(context)

        except Exception as e:
            return f"Error fetching patient context: {e}"

    def _parse_observation(self, observation: Dict, context: Dict):
        """Parse FHIR Observation into context structure."""
        try:
            code_text = observation.get("code", {}).get("text", "Unknown")
            value = observation.get("valueQuantity", {})
            value_str = f"{value.get('value')} {value.get('unit', '')}" if value else "N/A"
            date = observation.get("effectiveDateTime", "Unknown date")

            category = observation.get("category", [{}])[0].get("coding", [{}])[0].get("code", "")

            if "laboratory" in category.lower():
                context["recent_labs"].append(f"{code_text}: {value_str} ({date})")
            elif "vital-signs" in category.lower():
                context["recent_vitals"][code_text] = value_str
            else:
                context["recent_labs"].append(f"{code_text}: {value_str} ({date})")
        except Exception as e:
            print(f"[FHIR] Error parsing observation: {e}")

    def _parse_medication(self, medication: Dict, context: Dict):
        """Parse FHIR MedicationRequest into context structure."""
        try:
            status = medication.get("status", "")
            if status in ["active", "on-hold"]:
                med_code = medication.get("medicationCodeableConcept", {})
                med_text = med_code.get("text") or med_code.get("coding", [{}])[0].get("display", "Unknown medication")
                dosage = medication.get("dosageInstruction", [{}])[0].get("text", "")

                if dosage:
                    context["active_medications"].append(f"{med_text} - {dosage}")
                else:
                    context["active_medications"].append(med_text)
        except Exception as e:
            print(f"[FHIR] Error parsing medication: {e}")

    def _parse_condition(self, condition: Dict, context: Dict):
        """Parse FHIR Condition into context structure."""
        try:
            clinical_status = condition.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "")
            if clinical_status in ["active", "recurrence", "relapse"]:
                cond_code = condition.get("code", {})
                cond_text = cond_code.get("text") or cond_code.get("coding", [{}])[0].get("display", "Unknown condition")
                onset = condition.get("onsetDateTime", "")

                if onset:
                    context["conditions"].append(f"{cond_text} (since {onset})")
                else:
                    context["conditions"].append(cond_text)
        except Exception as e:
            print(f"[FHIR] Error parsing condition: {e}")

    def _format_context(self, context: Dict) -> str:
        """Format context dictionary as readable string."""
        output = f"Patient ID: {context['patient_id']}\n\n"

        if context.get("recent_labs"):
            output += "Recent Lab Results:\n"
            for lab in context["recent_labs"]:
                output += f"  - {lab}\n"
            output += "\n"

        if context.get("active_medications"):
            output += "Active Medications:\n"
            for med in context["active_medications"]:
                output += f"  - {med}\n"
            output += "\n"

        if context.get("conditions"):
            output += "Clinical Conditions:\n"
            for cond in context["conditions"]:
                output += f"  - {cond}\n"
            output += "\n"

        if context.get("recent_vitals"):
            output += "Recent Vitals:\n"
            for vital, value in context["recent_vitals"].items():
                output += f"  - {vital}: {value}\n"

        return output
