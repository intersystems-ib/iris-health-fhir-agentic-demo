Class clinicalai.bo.ClinicalAgenticOperation Extends EnsLib.REST.Operation
{

Parameter INVOCATION = "Queue";

/// Send request to Clinical Agentic API
Method evaluate(pRequest As clinicalai.msg.ClinicalAgenticReq, Output pResponse As Ens.StringContainer) As %Status
{
    set ret = $$$OK
    try {
      set pResponse = ##class(Ens.StringContainer).%New()

      // serialize to json        
      do pRequest.%JSONExportToString(.jsonExport)
      set formatter = ##class(%JSON.Formatter).%New()
      do formatter.FormatToString(jsonExport, .json)
      $$$LOGINFO(json)

      // build request
      set httpReq = ##class(%Net.HttpRequest).%New()
      set httpReq.ContentType="application/json"
      set httpReq.ContentCharset="UTF-8"
      do httpReq.EntityBody.Write(json)
    
      // send request
      set url = ..Adapter.URL
      set sc = ..Adapter.SendFormDataArray(.httpRsp, "POST",  .httpReq, , , url)

      if $$$ISERR(sc),$isobject(httpRsp),$isobject(httpRsp.Data),httpRsp.Data.Size {
          return $$$ERROR($$$EnsErrGeneral,$$$StatusDisplayString(sc)_":"_httpRsp.Data.Read())
      }
      $$$ThrowOnError(sc)
      
      // handle response
      if $isobject(httpRsp),httpRsp.StatusCode=200 { 
          set data = httpRsp.Data.Read()
          $$$LOGINFO("response="_data)

          // parse response
          //set jsonObj = {}.%FromJSON(data)
          set pResponse.StringValue = data
      }

    } catch ex {
        set ret = ex.AsStatus()
    }
    quit ret
}

XData MessageMap
{
<MapItems>
  <MapItem MessageType="clinicalai.msg.ClinicalAgenticReq">
    <Method>evaluate</Method>
  </MapItem>
</MapItems>
}

}
