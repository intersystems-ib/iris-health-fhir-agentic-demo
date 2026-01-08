Class clinicalai.ClinicalEventOrchestration Extends Ens.Production
{

XData ProductionDefinition
{
<Production Name="clinicalai.ClinicalEventOrchestration" TestingEnabled="true" LogGeneralTraceEvents="true">
  <Description></Description>
  <ActorPoolSize>2</ActorPoolSize>
  <Item Name="Clinical Agentic Evaluation" Category="" ClassName="clinicalai.bo.ClinicalAgenticOperation" PoolSize="1" Enabled="true" Foreground="false" Comment="" LogTraceEvents="false" Schedule="">
    <Setting Target="Adapter" Name="HTTPPort">8000</Setting>
    <Setting Target="Adapter" Name="HTTPServer">host.docker.internal</Setting>
    <Setting Target="Adapter" Name="URL">/evaluate</Setting>
    <Setting Target="Adapter" Name="ResponseTimeout">300</Setting>
  </Item>
  <Item Name="FHIR Observation In" Category="" ClassName="clinicalai.bs.FHIRObservationIn" PoolSize="0" Enabled="true" Foreground="false" Comment="" LogTraceEvents="false" Schedule="">
    <Setting Target="Host" Name="TargetConfigName">FollowUp AI Process</Setting>
  </Item>
  <Item Name="FollowUp AI Process" Category="" ClassName="clinicalai.bp.FollowUpAI" PoolSize="1" Enabled="true" Foreground="false" Comment="" LogTraceEvents="false" Schedule="">
  </Item>
  <Item Name="Clinical AI Persistence" Category="" ClassName="clinicalai.bo.ClinicalAiPersistence" PoolSize="1" Enabled="true" Foreground="false" Comment="" LogTraceEvents="false" Schedule="">
  </Item>
  <Item Name="Clinical DiagnosticReport" Category="" ClassName="clinicalai.bo.ClinicalReportPublisher" PoolSize="1" Enabled="true" Foreground="false" Comment="" LogTraceEvents="false" Schedule="">
  </Item>
</Production>
}

}
