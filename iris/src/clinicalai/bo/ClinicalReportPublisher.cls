Class clinicalai.bo.ClinicalReportPublisher Extends Ens.BusinessOperation
{

Parameter INVOCATION = "Queue";

/// FHIR Server Base URL
Property FHIRServerURL As %String(MAXLEN = 512) [ InitialExpression = "/interop/fhir/r4" ];

Parameter SETTINGS = "FHIRServerURL:Basic";

/// Publish a FHIR DiagnosticReport based on the AI agent response
/// Receives a ClinicalReportReq with the agent response and case ID
/// Returns an Ens.StringContainer with the DiagnosticReport resource ID
Method PublishDiagnosticReport(pRequest As clinicalai.msg.ClinicalReportReq, Output pResponse As Ens.StringContainer) As %Status
{
	Set tSC = $$$OK
	Set pResponse = ##class(Ens.StringContainer).%New()

	Try {
		// Parse the agent response JSON
		Set agentRsp = ##class(%DynamicObject).%FromJSON(pRequest.AgentRsp)

		// Extract data from agent response
		Set caseId = agentRsp.%Get("case_id")
		Set createdAt = agentRsp.%Get("created_at")
		Set patientRef = agentRsp.%Get("patient_ref")
		Set triggerObsRef = agentRsp.%Get("trigger_observation_ref")

		Set assessment = agentRsp.%Get("assessment")
		Set riskLevel = assessment.%Get("risk_level")
		Set confidence = assessment.%Get("confidence")
		Set reasoningSummary = assessment.%Get("reasoning_summary")

		Set metadata = agentRsp.%Get("metadata")
		Set modelName = metadata.%Get("model_name")
		Set guidelineVersion = metadata.%Get("guideline_version")

		// Build conclusion text from reasoning summary
		Set conclusion = "AI follow-up evaluation indicates a "_riskLevel_" risk of worsening renal function. "_reasoningSummary

		// Build recommended actions text for presentedForm
		Set recommendations = agentRsp.%Get("recommendations")
		Set actionsText = "RECOMMENDED ACTIONS:"_$c(10)
		Set iter = recommendations.%GetIterator()
		While iter.%GetNext(.key, .rec) {
			Set actionText = rec.%Get("action_text")
			Set timeframe = rec.%Get("timeframe")
			Set actionsText = actionsText_"- "_actionText_" (Timeframe: "_timeframe_")"_$c(10)
		}

		// Base64 encode the actions text for presentedForm
		set actionsText = $zconvert(actionsText, "O", "UTF8")
		Set encodedActions = $system.Encryption.Base64Encode(actionsText)

		// Convert ISO 8601 timestamp to FHIR format (keep as-is)
		Set effectiveDateTime = createdAt
		Set issued = createdAt

		// Build the DiagnosticReport FHIR resource
		Set diagnosticReport = {
			"resourceType": "DiagnosticReport",
			"status": "final",
			"category": [
				{
					"coding": [
						{
							"system": "http://terminology.hl7.org/CodeSystem/v2-0074",
							"code": "LAB",
							"display": "Laboratory"
						}
					]
				}
			],
			"code": {
				"coding": [
					{
						"system": "http://example.org/fhir/CodeSystem/ai-report-types",
						"code": "ai-followup-evaluation",
						"display": "AI Follow-up Evaluation"
					}
				],
				"text": "AI-based follow-up evaluation for abnormal laboratory result"
			},
			"subject": {
				"reference": (patientRef)
			},
			"effectiveDateTime": (effectiveDateTime),
			"issued": (issued),
			"result": [
				{
					"reference": (triggerObsRef)
				}
			],
			"conclusion": (conclusion),
			"conclusionCode": [
				{
					"coding": [
						{
							"system": "http://example.org/fhir/CodeSystem/ai-risk-level",
							"code": (riskLevel),
							"display": (..FormatRiskLevel(riskLevel))
						}
					]
				}
			],
			"presentedForm": [
				{
					"contentType": "text/plain",
					"language": "en",
					"data": (encodedActions)
				}
			],
			"extension": [
				{
					"url": "http://example.org/fhir/StructureDefinition/ai-evaluation-metadata",
					"extension": [
						{
							"url": "caseId",
							"valueString": (caseId)
						},
						{
							"url": "confidence",
							"valueString": (confidence)
						},
						{
							"url": "model",
							"valueString": (modelName)
						},
						{
							"url": "guidelineVersion",
							"valueString": (guidelineVersion)
						}
					]
				}
			]
		}

		set ^zaft($i(^zaft))=diagnosticReport.%ToJSON()

		// Create FHIR client
		Set clientObj = ##class(HS.FHIRServer.RestClient.FHIRService).CreateInstance(..FHIRServerURL)
		Do clientObj.SetResponseFormat("JSON")

		// Create the DiagnosticReport in the FHIR server
		Set response = clientObj.Create("DiagnosticReport", diagnosticReport.%ToJSON())

		// Check response status
		If (response.Status'=201) {
			$$$ThrowStatus($$$ERROR($$$GeneralError, "Error creating DiagnosticReport. Status: "_response.Status))
		}

		// Extract the resource ID from the response
		Set resourceId = response.Id

		// Set response with the resource ID
		Set pResponse.StringValue = resourceId

		$$$LOGINFO("Successfully published DiagnosticReport with ID: "_resourceId_" for CaseId: "_caseId)

	} Catch ex {
		Set tSC = ex.AsStatus()
	}

	Quit tSC
}

/// Helper method to format risk level for display
ClassMethod FormatRiskLevel(riskLevel As %String) As %String
{
	Set formatted = $Replace(riskLevel, "-", " ")
	Set formatted = $ZConvert($Extract(formatted, 1), "U")_$Extract(formatted, 2, *)
	Quit formatted
}

XData MessageMap
{
<MapItems>
  <MapItem MessageType="clinicalai.msg.ClinicalReportReq">
    <Method>PublishDiagnosticReport</Method>
  </MapItem>
</MapItems>
}

}
