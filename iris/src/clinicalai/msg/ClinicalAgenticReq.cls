Class clinicalai.msg.ClinicalAgenticReq Extends (Ens.Request, %JSON.Adaptor)
{

Property TriggerObservationRef As %String;

Storage Default
{
<Data name="ClinicalAgenticReqDefaultData">
<Subscript>"ClinicalAgenticReq"</Subscript>
<Value name="1">
<Value>TriggerObservationRef</Value>
</Value>
</Data>
<DefaultData>ClinicalAgenticReqDefaultData</DefaultData>
<Type>%Storage.Persistent</Type>
}

}
