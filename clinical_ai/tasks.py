"""
Task definitions for the Lab Follow-up Recommendation workflow.

Tasks are executed sequentially:
1. Context Agent gathers patient data
2. Guidelines Agent performs RAG search
3. Reasoning Agent synthesizes and produces recommendations
"""

from crewai import Task


def create_tasks(
    agents: dict,
    case_id: str,
    patient_ref: str,
    trigger_observation_ref: str,
    lab_result: dict
) -> list:
    """
    Create the sequence of tasks for the workflow.

    Args:
        agents: Dictionary of agent instances
        case_id: Unique case identifier
        patient_ref: FHIR patient reference (e.g., "Patient/123")
        trigger_observation_ref: FHIR observation reference (e.g., "Observation/987")
        lab_result: Lab result details (test_name, value, unit, status)

    Returns:
        List of Task instances
    """

    # ========================================================================
    # Task 1: Gather patient clinical context
    # ========================================================================
    # Agent: Context Agent
    # Purpose: Retrieve relevant patient data from IRIS FHIR repository
    #
    # Expected output:
    # - Previous lab results for this test
    # - Related lab results (electrolytes, kidney function)
    # - Active medications
    # - Known clinical conditions
    # - Recent vital signs
    # ========================================================================
    # Extract patient ID from patient_ref (remove "Patient/" prefix if present)
    patient_id = patient_ref.replace("Patient/", "")

    context_task = Task(
        description=f"""
        Retrieve comprehensive clinical context for the patient.

        **Patient:** {patient_ref}
        **Patient ID (use this with tools):** {patient_id}
        **Trigger Observation:** {trigger_observation_ref}

        **Lab Result:**
        - Test: {lab_result.get('test_name', 'Unknown')}
        - Value: {lab_result.get('value', 'N/A')} {lab_result.get('unit', '')}
        - Status: {lab_result.get('status', 'N/A')}

        **Your Tasks:**
        1. Use the FetchPatientContextTool to retrieve patient context.
           IMPORTANT: Use the patient_id parameter with ONLY the identifier (e.g., "123"),
           NOT the full FHIR reference (e.g., NOT "Patient/123").

           Retrieve:
           - Patient demographics
           - Recent lab results (focus on same test)
           - Active medications
           - Known clinical conditions
           - Recent vital signs

        2. Use the AnalyzeLabTrendTool to analyze trends for this specific test:
           - Is this value stable, increasing, or decreasing?
           - What is the change over time?

        **Output Format:**
        Provide a structured summary of:
        - Patient clinical conditions
        - Recent lab trends
        - Active medications (especially those relevant to kidney function)
        - Any relevant vital signs

        Focus on information that helps understand the clinical significance
        of this abnormal lab result.
        """,
        agent=agents["context"],
        expected_output="Structured patient context including recent labs, trends, medications, and conditions"
    )

    # ========================================================================
    # Task 2: Search clinical guidelines (RAG)
    # ========================================================================
    # Agent: Guidelines Agent
    # Purpose: Find relevant clinical evidence from IRIS Vector DB
    #
    # Expected output:
    # - Guideline excerpts
    # - Chunk IDs
    # - Similarity scores
    # ========================================================================
    guidelines_task = Task(
        description=f"""
        Search clinical guidelines for evidence-based recommendations.

        **Lab Result:**
        - Test: {lab_result.get('test_name', 'Unknown')}
        - Value: {lab_result.get('value', 'N/A')} {lab_result.get('unit', '')}
        - Status: {lab_result.get('status', 'N/A')}

        **Context from Previous Task:**
        Use the patient context provided by the Context Agent to refine your search.

        **Your Tasks:**
        1. Use the SearchClinicalGuidelinesTool to find relevant guidelines addressing:
           - Clinical significance of this abnormal value
           - Recommended follow-up actions
           - Workup or diagnostic considerations
           - Treatment implications

        2. Focus on guidelines relevant to the patient's clinical conditions
           and medication profile.

        **Output Format:**
        Provide a structured list of relevant guideline excerpts including:
        - Guideline ID
        - Chunk ID
        - Similarity score
        - Excerpt text

        Return the top 3-5 most relevant guideline fragments.
        """,
        agent=agents["guidelines"],
        expected_output="List of clinical guideline excerpts with chunk IDs, similarity scores, and relevant text",
        context=[context_task]
    )

    # ========================================================================
    # Task 3: Clinical reasoning and recommendations
    # ========================================================================
    # Agent: Reasoning Agent
    # Purpose: Synthesize context and evidence into actionable recommendations
    #
    # Expected output:
    # - Risk assessment
    # - Follow-up recommendations
    # - Clinical reasoning
    # - Evidence references
    #
    # CRITICAL:
    # - Output must be valid JSON matching ClinicalRecommendationOutput schema
    # - Agent does NOT persist to database (IRIS handles that separately)
    # - Agent only returns structured JSON
    # ========================================================================
    reasoning_task = Task(
        description=f"""
        Synthesize patient context and clinical evidence to generate follow-up recommendations.

        **Case Information:**
        - Case ID: {case_id}
        - Patient: {patient_ref}
        - Trigger Observation: {trigger_observation_ref}

        **Lab Result:**
        - Test: {lab_result.get('test_name', 'Unknown')}
        - Value: {lab_result.get('value', 'N/A')} {lab_result.get('unit', '')}
        - Status: {lab_result.get('status', 'N/A')}

        **Your Tasks:**
        1. Analyze the patient context (from Context Agent)
        2. Review the clinical evidence (from Guidelines Agent)
        3. Identify trends and risk factors
        4. Generate specific follow-up recommendations

        **Assessment:**
        - Determine risk level: low | medium | medium-high | high
        - Determine confidence: low | medium | high
        - Write a concise reasoning summary (2-3 sentences)

        **Recommendations:**
        Generate 1-5 specific, actionable recommendations. Each should have:
        - action_type: repeat_test | med_review | monitor | imaging | referral | lifestyle
        - action_text: Clear, specific action (e.g., "Repeat serum creatinine measurement to confirm trend")
        - timeframe: When to do it (e.g., "7–14 days", "as soon as possible")

        **Evidence:**
        Reference the specific guideline chunks that support your recommendations.
        Include guideline_id, chunk_id, similarity score, and excerpt.

        **CRITICAL REQUIREMENTS:**
        - Frame as clinical decision support, NOT diagnosis
        - Use conservative, evidence-based language
        - Do NOT prescribe medications
        - Do NOT make definitive diagnoses
        - Do NOT persist to database (that is IRIS's responsibility)
        - ONLY return the structured JSON output

        **Output Format:**
        Return a valid JSON object matching this structure:
        {{
          "case_id": "{case_id}",
          "created_at": "<ISO 8601 timestamp>",
          "patient_ref": "{patient_ref}",
          "trigger_observation_ref": "{trigger_observation_ref}",
          "assessment": {{
            "risk_level": "medium-high",
            "confidence": "high",
            "reasoning_summary": "Brief explanation of clinical reasoning..."
          }},
          "recommendations": [
            {{
              "action_type": "repeat_test",
              "action_text": "Specific action description",
              "timeframe": "7–14 days"
            }}
          ],
          "evidence": [
            {{
              "guideline_id": "ckd_creatinine_demo",
              "chunk_id": "ckd_creatinine_demo:section-6",
              "similarity": 0.82,
              "excerpt": "Guideline text excerpt..."
            }}
          ],
          "metadata": {{
            "orchestration_framework": "CrewAI",
            "crew_name": "renal_followup_crew",
            "model_provider": "OpenAI",
            "model_name": "gpt-4.1-mini",
            "guideline_version": "v1",
            "language": "en"
          }}
        }}
        """,
        agent=agents["reasoning"],
        expected_output="Valid JSON object matching ClinicalRecommendationOutput schema with assessment, recommendations, and evidence",
        context=[context_task, guidelines_task]
    )

    return [context_task, guidelines_task, reasoning_task]
