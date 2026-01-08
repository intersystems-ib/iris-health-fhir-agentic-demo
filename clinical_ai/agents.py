"""
Agent definitions for the Lab Follow-up Recommendation workflow.

Three specialized agents as defined in ARCHITECTURE.md:
- Context Agent: Retrieves patient clinical context
- Clinical Guidelines Agent: RAG-based evidence retrieval
- Clinical Reasoning Agent: Decision support and recommendations
"""

from crewai import Agent
from .prompts import (
    CONTEXT_AGENT_ROLE,
    CONTEXT_AGENT_GOAL,
    CONTEXT_AGENT_BACKSTORY,
    GUIDELINES_AGENT_ROLE,
    GUIDELINES_AGENT_GOAL,
    GUIDELINES_AGENT_BACKSTORY,
    REASONING_AGENT_ROLE,
    REASONING_AGENT_GOAL,
    REASONING_AGENT_BACKSTORY
)
from .tools.fetch_patient_context import FetchPatientContextTool
from .tools.search_clinical_guidelines import SearchClinicalGuidelinesTool
from .tools.analyze_lab_trend import AnalyzeLabTrendTool


def create_agents() -> dict:
    """
    Create all agents for the workflow.

    Returns:
        Dictionary mapping agent names to Agent instances
    """

    # ========================================================================
    # Context Agent
    # ========================================================================
    # Retrieves patient clinical context from IRIS FHIR repository
    # Example outputs:
    # - Previous creatinine values
    # - CKD diagnosis
    # - Active medications (NSAIDs, etc.)
    # ========================================================================
    context_agent = Agent(
        role=CONTEXT_AGENT_ROLE,
        goal=CONTEXT_AGENT_GOAL,
        backstory=CONTEXT_AGENT_BACKSTORY,
        tools=[
            FetchPatientContextTool(),
            AnalyzeLabTrendTool()
        ],
        verbose=True,
        allow_delegation=False
    )

    # ========================================================================
    # Clinical Guidelines Agent (RAG)
    # ========================================================================
    # Queries IRIS Vector DB
    # Returns relevant guideline chunks with:
    # - Chunk IDs
    # - Similarity scores
    # - Guideline excerpts
    # ========================================================================
    guidelines_agent = Agent(
        role=GUIDELINES_AGENT_ROLE,
        goal=GUIDELINES_AGENT_GOAL,
        backstory=GUIDELINES_AGENT_BACKSTORY,
        tools=[
            SearchClinicalGuidelinesTool()
        ],
        verbose=True,
        allow_delegation=False
    )

    # ========================================================================
    # Clinical Reasoning Agent
    # ========================================================================
    # Combines context and evidence
    # Identifies trends and risk factors
    # Produces follow-up recommendations as structured JSON
    #
    # IMPORTANT:
    # - Does NOT diagnose
    # - Does NOT prescribe
    # - Does NOT persist to database (IRIS handles persistence)
    # - Provides decision support only
    # - Returns structured JSON matching ClinicalRecommendationOutput schema
    # ========================================================================
    reasoning_agent = Agent(
        role=REASONING_AGENT_ROLE,
        goal=REASONING_AGENT_GOAL,
        backstory=REASONING_AGENT_BACKSTORY,
        tools=[],  # No tools - reasoning agent synthesizes and returns JSON only
        verbose=True,
        allow_delegation=False
    )

    return {
        "context": context_agent,
        "guidelines": guidelines_agent,
        "reasoning": reasoning_agent
    }
