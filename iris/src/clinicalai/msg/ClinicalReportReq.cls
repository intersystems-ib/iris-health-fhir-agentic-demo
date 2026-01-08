Class clinicalai.msg.ClinicalReportReq Extends Ens.Request
{

/// Agent response (JSON)
Property AgentRsp As %String(MAXLEN = "");

/// Case Identifier where Agent reponse is persisted
Property CaseId As %String(MAXLEN = "");

Storage Default
{
<Data name="ClinicalReportReqDefaultData">
<Subscript>"ClinicalReportReq"</Subscript>
<Value name="1">
<Value>AgentRsp</Value>
</Value>
<Value name="2">
<Value>CaseId</Value>
</Value>
</Data>
<DefaultData>ClinicalReportReqDefaultData</DefaultData>
<Type>%Storage.Persistent</Type>
}

}
