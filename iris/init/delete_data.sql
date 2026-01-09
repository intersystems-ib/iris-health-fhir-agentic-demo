/* ============================================================================
   Clinical AI Demo - Data Deletion Script (InterSystems IRIS)
   Schema: clinicalai_data

   Purpose:
   - Delete all data from the clinical AI demo tables
   - Maintains referential integrity by deleting in correct order
   - Does NOT drop the tables or schema, only removes data
   ============================================================================ */

-- ----------------------------------------------------------------------------
-- Delete data from tables (reverse order to respect foreign key constraints)
-- ----------------------------------------------------------------------------

-- Delete evidence records first (child table)
DELETE FROM clinicalai_data.CaseEvidences;

-- Delete recommendations (child table)
DELETE FROM clinicalai_data.CaseRecommendations;

-- Delete cases (parent table)
DELETE FROM clinicalai_data.Cases;

-- Delete guideline chunks (independent table)
--DELETE FROM clinicalai_data.GuidelineChunks;

