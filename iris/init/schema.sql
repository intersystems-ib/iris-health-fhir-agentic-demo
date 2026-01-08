/* ============================================================================
   Clinical AI Demo - Minimal SQL Schema (InterSystems IRIS)
   Schema: clinicalai_data

   Purpose:
   - Keep the demo simple and explainable
   - Persist Agentic AI results for:
       * What happened (Cases)
       * What to do (CaseRecommendations)
       * Why (CaseEvidences)
       * Knowledge base context (GuidelineChunks)

   This schema is intentionally minimal and demo-oriented.
   ============================================================================ */

-- ----------------------------------------------------------------------------
-- Create schema
-- ----------------------------------------------------------------------------
CREATE SCHEMA clinicalai_data;

-- ----------------------------------------------------------------------------
-- Drop tables (reverse order to avoid FK issues)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS clinicalai_data.CaseEvidences;
DROP TABLE IF EXISTS clinicalai_data.CaseRecommendations;
DROP TABLE IF EXISTS clinicalai_data.Cases;
DROP TABLE IF EXISTS clinicalai_data.GuidelineChunks;

-- ----------------------------------------------------------------------------
-- 1) GuidelineChunks
--    Stores the text chunks used for RAG (embeddings live in IRIS Vector DB)
-- ----------------------------------------------------------------------------
CREATE TABLE clinicalai_data.GuidelineChunks (
  ChunkId        VARCHAR(128)  NOT NULL,
  GuidelineId    VARCHAR(128)  NOT NULL,
  ChunkText      VARCHAR(4000) NOT NULL,
  Embedding   VECTOR(FLOAT, 1536),        -- vector for semantic search
  CreatedAt      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT GuidelineChunksPK PRIMARY KEY (ChunkId)
);

-- ----------------------------------------------------------------------------
-- 2) Cases
--    One row per agent evaluation (triggered by a lab Observation)
-- ----------------------------------------------------------------------------
CREATE TABLE clinicalai_data.Cases (
  CaseId                    VARCHAR(64)   NOT NULL,  -- UUID
  CreatedAt                 TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PatientRef                VARCHAR(128)  NOT NULL,  -- e.g. Patient/123
  TriggerObservationRef    VARCHAR(128)  NOT NULL,  -- e.g. Observation/456
  RiskLevel                 VARCHAR(32),             -- low | medium | high
  Confidence                 VARCHAR(32),             -- low | medium | high
  ReasoningSummary          VARCHAR(4000),
  OutputJson                LONGVARCHAR,              -- full CrewAI output (optional)
  CONSTRAINT CasesPK PRIMARY KEY (CaseId)
);

-- ----------------------------------------------------------------------------
-- 3) CaseRecommendations
--    Concrete follow-up actions suggested by the agent
-- ----------------------------------------------------------------------------
CREATE TABLE clinicalai_data.CaseRecommendations (
  RecommendationId  BIGINT       NOT NULL IDENTITY,
  CaseId            VARCHAR(64)   NOT NULL,
  ActionType        VARCHAR(64)   NOT NULL,  -- repeat_test | med_review | monitor
  ActionText        VARCHAR(2048) NOT NULL,
  Timeframe          VARCHAR(64),             -- e.g. "7–14 days"
  CONSTRAINT CaseRecommendationsPK PRIMARY KEY (RecommendationId),
  FOREIGN KEY (CaseId) REFERENCES clinicalai_data.Cases(CaseId)
);

-- ----------------------------------------------------------------------------
-- 4) CaseEvidences
--    Evidence fragments used to justify the recommendations (RAG explainability)
-- ----------------------------------------------------------------------------
CREATE TABLE clinicalai_data.CaseEvidences (
  EvidenceId    BIGINT        NOT NULL IDENTITY,
  CaseId        VARCHAR(64)   NOT NULL,
  GuidelineId   VARCHAR(128),            -- logical guideline identifier
  ChunkId       VARCHAR(128),            -- reference to GuidelineChunks
  Similarity     DOUBLE,                  -- vector similarity score
  Excerpt        VARCHAR(4000),            -- text shown to humans
  CONSTRAINT CaseEvidencesPK PRIMARY KEY (EvidenceId),
  FOREIGN KEY (CaseId) REFERENCES clinicalai_data.Cases(CaseId)
);