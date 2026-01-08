/// 
Class clinicalai.bp.FollowUpAI Extends Ens.BusinessProcessBPL
{

/// BPL Definition
XData BPL [ XMLNamespace = "http://www.intersystems.com/bpl" ]
{
<process language='objectscript' request='clinicalai.msg.ClinicalAgenticReq' response='Ens.StringResponse' height='2000' width='2000' >
<context>
<property name='agentRsp' type='Ens.StringContainer' instantiate='0' deletewithcontext='0' />
<property name='persistRsp' type='Ens.StringContainer' instantiate='0' deletewithcontext='0' />
<property name='reportRsp' type='Ens.StringContainer' instantiate='0' deletewithcontext='0' />
</context>
<sequence xend='200' yend='550' >
<call name='Agentic Evaluation' target='Clinical Agentic Evaluation' async='0' timeout='"PT500S"' xpos='200' ypos='250' >
<annotation><![CDATA[Call Clinical Agentic Evaluation]]></annotation>
<request type='clinicalai.msg.ClinicalAgenticReq' >
<assign property="callrequest.TriggerObservationRef" value="request.TriggerObservationRef" action="set" />
</request>
<response type='Ens.StringContainer' >
<assign property="context.agentRsp" value="callresponse" action="set" />
</response>
</call>
<call name='Clinical AI Persistence' target='Clinical AI Persistence' async='0' timeout='"PT60S"' xpos='200' ypos='350' >
<annotation><![CDATA[Persist response of Agentic Evaluation]]></annotation>
<request type='Ens.StringContainer' >
<assign property="callrequest" value="context.agentRsp" action="set" />
</request>
<response type='Ens.StringContainer' >
<assign property="context.persistRsp" value="callresponse" action="set" />
</response>
</call>
<call name='Clinical DiagnosticReport' target='Clinical DiagnosticReport' async='1' xpos='200' ypos='450' >
<annotation><![CDATA[Generate and store FHIR DiagnosticReport]]></annotation>
<request type='clinicalai.msg.ClinicalReportReq' >
<assign property="callrequest.AgentRsp" value="context.agentRsp.StringValue" action="set" />
<assign property="callrequest.CaseId" value="context.persistRsp.StringValue" action="set" />
</request>
<response type='Ens.StringContainer' >
<assign property="context.reportRsp" value="callresponse" action="set" />
</response>
</call>
</sequence>
</process>
}

Storage Default
{
<Type>%Storage.Persistent</Type>
}

}
