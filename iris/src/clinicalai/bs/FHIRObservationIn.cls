Class clinicalai.bs.FHIRObservationIn Extends Ens.BusinessService
{

Property TargetConfigName As Ens.DataType.ConfigName;

Parameter SETTINGS = "TargetConfigName:Basic:selector?context={Ens.ContextSearch/ProductionItems?targets=1&productionName=@productionId},GenerateSuperSessionID:Additional,AlertGracePeriod:Alerting,-FMGCalculation,-FMGCompletionHosts";

/// Override this method to process incoming data. Do not call SendRequestSync/Async() from outside this method (e.g. in a SOAP Service or a CSP page).
Method OnProcessInput(pInput As %RegisteredObject, Output pOutput As %RegisteredObject, ByRef pHint As %String) As %Status
{
    set request = ##class(clinicalai.msg.ClinicalAgenticReq).%New()
    set request.TriggerObservationRef = pInput
	quit ..SendRequestAsync(..TargetConfigName, request)
}

}
