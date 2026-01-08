Class clinicalai.bo.ClinicalAiPersistence Extends Ens.BusinessOperation
{

/// Persist the CrewAI agent response to IRIS database tables
/// Receives an Ens.StringContainer with the JSON response
/// Returns an Ens.StringContainer with the CaseId
Method PersistAgentResponse(pRequest As Ens.StringContainer, Output pResponse As Ens.StringContainer) As %Status
{
	Set tSC = $$$OK
	Set pResponse = ##class(Ens.StringContainer).%New()

	Try {
		// Parse JSON from StringContainer
		Set jsonString = pRequest.StringValue
		Set dynObj = ##class(%DynamicObject).%FromJSON(jsonString)

		// Extract Case data
		Set caseId = dynObj.%Get("case_id")
		Set createdAtISO = dynObj.%Get("created_at")

		// Convert ISO 8601 timestamp to IRIS format
		// Remove 'Z' and 'T' to convert "2026-01-10T15:00:00Z" to "2026-01-10 15:00:00"
		Set createdAt = $Replace(createdAtISO, "T", " ")
		Set createdAt = $Replace(createdAt, "Z", "")

		Set patientRef = dynObj.%Get("patient_ref")
		Set triggerObsRef = dynObj.%Get("trigger_observation_ref")

		Set assessment = dynObj.%Get("assessment")
		Set riskLevel = assessment.%Get("risk_level")
		Set confidence = assessment.%Get("confidence")
		Set reasoningSummary = assessment.%Get("reasoning_summary")

		// Start transaction
		TSTART
		Try {
			// 1. Insert into Cases table
			Set sql = "INSERT INTO clinicalai_data.Cases "_
					 "(CaseId, CreatedAt, PatientRef, TriggerObservationRef, RiskLevel, Confidence, ReasoningSummary, OutputJson) "_
					 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"

			Set statement = ##class(%SQL.Statement).%New()
			$$$ThrowOnError(statement.%Prepare(sql))

			Set result = statement.%Execute(caseId, createdAt, patientRef, triggerObsRef, riskLevel, confidence, reasoningSummary, jsonString)
			If result.%SQLCODE < 0 {
				Throw ##class(%Exception.SQL).CreateFromSQLCODE(result.%SQLCODE, result.%Message)
			}

			// 2. Insert recommendations
			Set recommendations = dynObj.%Get("recommendations")
			Set iter = recommendations.%GetIterator()
			While iter.%GetNext(.key, .rec) {
				Set actionType = rec.%Get("action_type")
				Set actionText = rec.%Get("action_text")
				Set timeframe = rec.%Get("timeframe")

				Set sql = "INSERT INTO clinicalai_data.CaseRecommendations "_
						 "(CaseId, ActionType, ActionText, Timeframe) "_
						 "VALUES (?, ?, ?, ?)"

				Set stmt2 = ##class(%SQL.Statement).%New()
				Set status = stmt2.%Prepare(sql)
				$$$ThrowOnError(status)

				Set result = stmt2.%Execute(caseId, actionType, actionText, timeframe)
				If result.%SQLCODE < 0 {
					Throw ##class(%Exception.SQL).CreateFromSQLCODE(result.%SQLCODE, result.%Message)
				}
			}

			// 3. Insert evidence
			Set evidence = dynObj.%Get("evidence")
			Set iter = evidence.%GetIterator()
			While iter.%GetNext(.key, .ev) {
				Set guidelineId = ev.%Get("guideline_id")
				Set chunkId = ev.%Get("chunk_id")
				Set similarity = ev.%Get("similarity")
				Set excerpt = ev.%Get("excerpt")

				Set sql = "INSERT INTO clinicalai_data.CaseEvidences "_
						 "(CaseId, GuidelineId, ChunkId, Similarity, Excerpt) "_
						 "VALUES (?, ?, ?, ?, ?)"

				Set stmt3 = ##class(%SQL.Statement).%New()
				Set status = stmt3.%Prepare(sql)
				$$$ThrowOnError(status)

				Set result = stmt3.%Execute(caseId, guidelineId, chunkId, similarity, excerpt)
				If result.%SQLCODE < 0 {
					Throw ##class(%Exception.SQL).CreateFromSQLCODE(result.%SQLCODE, result.%Message)
				}
			}

			// Commit transaction
			TCOMMIT

			// Set the response with the CaseId
			Set pResponse.StringValue = caseId

			$$$LOGINFO("Successfully persisted Clinical AI agent response for CaseId: "_caseId)

		} Catch ex {
			// Rollback on error
			TROLLBACK
			Throw ex
		}

	} Catch ex {
		Set tSC = ex.AsStatus()
	}

	Quit tSC
}

XData MessageMap
{
<MapItems>
  <MapItem MessageType="Ens.StringContainer">
    <Method>PersistAgentResponse</Method>
  </MapItem>
</MapItems>
}

}
