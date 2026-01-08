"""
CrewAI orchestration for Lab Follow-up Recommendation workflow.

This module defines the crew (team of agents) and coordinates their execution.
CrewAI is used as a library, not via CLI (per ARCHITECTURE.md).

The crew returns structured JSON matching ClinicalRecommendationOutput schema.
"""

import json
from crewai import Crew, Process
from .agents import create_agents
from .tasks import create_tasks
from .schemas import ClinicalRecommendationOutput


class LabFollowupCrew:
    """
    Orchestrates the multi-agent workflow for lab result follow-up.

    Per ARCHITECTURE.md, the crew consists of:
    - Context Agent: Retrieves patient clinical context from FHIR
    - Guidelines Agent: Searches clinical evidence via RAG (Vector DB)
    - Reasoning Agent: Generates follow-up recommendations

    Key characteristics:
    - CrewAI is used strictly as a Python library
    - The workflow is sequential (Process.sequential)
    - Returns structured JSON (does NOT persist to database)
    - IRIS handles all persistence after receiving the JSON
    """

    def __init__(
        self,
        case_id: str,
        patient_ref: str,
        trigger_observation_ref: str,
        lab_result: dict
    ):
        """
        Initialize the crew with case information.

        Args:
            case_id: Unique identifier for this case (UUID)
            patient_ref: FHIR patient reference (e.g., "Patient/123")
            trigger_observation_ref: FHIR observation reference (e.g., "Observation/987")
            lab_result: Dictionary containing lab result details:
                - test_name: Name of the lab test
                - value: Numeric value
                - unit: Unit of measurement
                - status: Status (e.g., "abnormal", "critical")
        """
        self.case_id = case_id
        self.patient_ref = patient_ref
        self.trigger_observation_ref = trigger_observation_ref
        self.lab_result = lab_result

        # Create agents
        self.agents = create_agents()

        # Create tasks
        self.tasks = create_tasks(
            agents=self.agents,
            case_id=case_id,
            patient_ref=patient_ref,
            trigger_observation_ref=trigger_observation_ref,
            lab_result=lab_result
        )

    def run(self) -> dict:
        """
        Execute the crew workflow.

        The workflow runs sequentially:
        1. Context Agent gathers patient data
        2. Guidelines Agent performs RAG search
        3. Reasoning Agent synthesizes and produces recommendations

        Returns:
            Dictionary containing the structured JSON output matching
            ClinicalRecommendationOutput schema, or None if parsing fails.

        The output includes:
        - case_id, created_at, patient_ref, trigger_observation_ref
        - assessment (risk_level, confidence, reasoning_summary)
        - recommendations (list of follow-up actions)
        - evidence (list of guideline references)
        - metadata (workflow execution details)
        """
        print("\n" + "=" * 70)
        print("🚀 Starting Lab Follow-up Agent Crew")
        print("=" * 70)
        print(f"Case ID: {self.case_id}")
        print(f"Patient: {self.patient_ref}")
        print(f"Observation: {self.trigger_observation_ref}")
        print(f"Lab Test: {self.lab_result.get('test_name', 'Unknown')}")
        print("=" * 70 + "\n")

        # Create and execute crew
        crew = Crew(
            agents=list(self.agents.values()),
            tasks=self.tasks,
            process=Process.sequential,  # Execute tasks in order
            verbose=True
        )

        # Execute workflow
        raw_result = crew.kickoff()

        print("\n" + "=" * 70)
        print("✅ Crew Execution Completed")
        print("=" * 70 + "\n")

        # Parse the result
        # CrewAI returns the output of the final task (reasoning agent)
        # which should be a JSON string matching ClinicalRecommendationOutput
        result = self._parse_crew_output(raw_result)

        if result:
            print("📋 Structured output successfully parsed")
            return result
        else:
            print("⚠️  Warning: Could not parse structured output")
            print("Raw output:")
            print(raw_result)
            return None

    def _parse_crew_output(self, raw_result) -> dict:
        """
        Parse the crew output into structured JSON.

        The Reasoning Agent should return valid JSON matching
        ClinicalRecommendationOutput schema. This method handles:
        - String outputs containing JSON
        - Direct JSON objects
        - Markdown code blocks with JSON

        Args:
            raw_result: Raw output from crew.kickoff()

        Returns:
            Parsed dictionary or None if parsing fails
        """
        try:
            # Case 1: raw_result is already a dict
            if isinstance(raw_result, dict):
                return raw_result

            # Case 2: raw_result is a string containing JSON
            if isinstance(raw_result, str):
                # Try to extract JSON from markdown code blocks
                if "```json" in raw_result or "```" in raw_result:
                    # Extract content between ``` markers
                    start = raw_result.find("```json")
                    if start == -1:
                        start = raw_result.find("```")
                    if start != -1:
                        start = raw_result.find("\n", start) + 1
                        end = raw_result.find("```", start)
                        if end != -1:
                            json_str = raw_result[start:end].strip()
                            return json.loads(json_str)

                # Try direct JSON parsing
                return json.loads(raw_result)

            # Case 3: Try converting to string first
            return json.loads(str(raw_result))

        except json.JSONDecodeError as e:
            print(f"[Crew] JSON parsing error: {e}")
            print(f"[Crew] Raw result type: {type(raw_result)}")
            return None
        except Exception as e:
            print(f"[Crew] Unexpected error parsing output: {e}")
            return None
