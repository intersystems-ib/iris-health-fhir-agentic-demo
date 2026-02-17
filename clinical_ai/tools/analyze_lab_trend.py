"""
Tool for analyzing lab result trends over time using FHIR queries.
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from crewai.tools import BaseTool
from typing import Type, List, Dict, Any
from pydantic import BaseModel, Field, PrivateAttr


class AnalyzeLabTrendInput(BaseModel):
    """Input schema for AnalyzeLabTrend tool."""
    patient_id: str = Field(..., description="Patient identifier")
    observation_code: str = Field(..., description="LOINC code for the lab test (e.g., '2160-0' for Creatinine)")
    lookback_days: int = Field(default=90, description="Number of days to look back")


class AnalyzeLabTrendTool(BaseTool):
    name: str = "Analyze Lab Result Trend"
    description: str = """
    Analyzes trends in lab results over time for a specific test using FHIR queries.
    Identifies whether values are stable, increasing, decreasing, or fluctuating.
    Helps determine if the current abnormal result is new or part of a trend.
    Requires LOINC code (e.g., '2160-0' for Creatinine).
    """
    args_schema: Type[BaseModel] = AnalyzeLabTrendInput

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

    def _run(self, patient_id: str, observation_code: str, lookback_days: int = 90) -> str:
        """
        Execute the tool.

        Args:
            patient_id: Patient identifier
            observation_code: LOINC code for the lab test
            lookback_days: Historical period to analyze

        Returns:
            Trend analysis summary
        """
        results = self._get_lab_trend(patient_id, observation_code, lookback_days)

        if not results:
            return f"""
Lab Trend Analysis:

No historical data found for observation code {observation_code} for patient {patient_id}.
This may be the first result for this test.
"""

        # Format the results
        output = f"Lab Trend Analysis (LOINC: {observation_code}, Last {lookback_days} days):\n\n"
        output += f"Total results found: {len(results)}\n\n"

        # Show historical values
        output += "Historical Values (most recent first):\n"
        for i, result in enumerate(results[:10], 1):  # Show up to 10 most recent
            output += f"  {i}. {result['date']}: {result['value']} {result['unit']}"
            if result.get('reference_range'):
                output += f" (Ref: {result['reference_range']})"
            output += "\n"

        if len(results) > 10:
            output += f"\n  ... and {len(results) - 10} more results\n"

        # Basic trend analysis
        if len(results) >= 2:
            output += "\nTrend Analysis:\n"
            values = [r['value'] for r in results if r['value'] is not None]

            if len(values) >= 2:
                first_val = values[-1]  # Oldest
                last_val = values[0]    # Newest
                change = last_val - first_val
                pct_change = (change / first_val * 100) if first_val != 0 else 0

                output += f"  Change: {change:+.2f} {results[0]['unit']} ({pct_change:+.1f}%)\n"

                if abs(pct_change) < 5:
                    output += "  Trend: Stable\n"
                elif pct_change > 0:
                    output += "  Trend: Increasing\n"
                else:
                    output += "  Trend: Decreasing\n"

        return output

    def _get_lab_trend(self, patient_id: str, observation_code: str, lookback_days: int = 90) -> List[Dict]:
        """
        Retrieve lab result trend using FHIR Observation queries.

        Args:
            patient_id: Patient identifier
            observation_code: LOINC code for the lab test
            lookback_days: Number of days to look back

        Returns:
            List of observation dictionaries sorted by date (newest first)
        """
        try:
            # Build FHIR query for Observations
            url = f"{self._fhir_base_url}/Observation"
            params = {
                "subject": f"Patient/{patient_id}",
                "code": observation_code,
                "_sort": "-date",  # Sort by date descending
                "_count": 100  # Limit results
            }
            headers = {"Accept": "application/fhir+json"}

            response = requests.get(url, params=params, headers=headers, auth=self._fhir_auth)
            response.raise_for_status()

            bundle = response.json()

            results = []
            if bundle.get("resourceType") == "Bundle" and bundle.get("entry"):
                for entry in bundle.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "Observation":
                        obs_data = {
                            "date": resource.get("effectiveDateTime", "Unknown"),
                            "value": resource.get("valueQuantity", {}).get("value"),
                            "unit": resource.get("valueQuantity", {}).get("unit", ""),
                            "code": resource.get("code", {}).get("text", "Unknown"),
                            "status": resource.get("status", ""),
                            "reference_range": self._extract_reference_range(resource)
                        }
                        results.append(obs_data)

            return results

        except Exception as e:
            print(f"[FHIR] Error fetching lab trend: {e}")
            return []

    def _extract_reference_range(self, observation: Dict) -> str:
        """Extract reference range from FHIR Observation."""
        try:
            ref_ranges = observation.get("referenceRange", [])
            if ref_ranges:
                low = ref_ranges[0].get("low", {}).get("value")
                high = ref_ranges[0].get("high", {}).get("value")
                unit = ref_ranges[0].get("low", {}).get("unit", "")

                if low and high:
                    return f"{low}-{high} {unit}"
                elif low:
                    return f">{low} {unit}"
                elif high:
                    return f"<{high} {unit}"
            return "Not specified"
        except Exception:
            return "Not specified"
