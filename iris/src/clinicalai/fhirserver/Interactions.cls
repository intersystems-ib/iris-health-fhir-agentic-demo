Class clinicalai.fhirserver.Interactions Extends HS.FHIRServer.Storage.Json.Interactions
{

/// @API Notification that a request in about to be dispatched.  The Interactions object
/// may use this to manage any session information or other bookkeeping.  By default, no processing
/// is performed.
/// @Input pFHIRService  The instance of HS.FHIRServer.Service that invoked this method
/// @Input pFHIRRequest  The request about to be processed
/// @Input pFHIRResponse The response about to be returned
Method OnAfterRequest(pFHIRService As HS.FHIRServer.API.Service, pFHIRRequest As HS.FHIRServer.API.Data.Request, pFHIRResponse As HS.FHIRServer.API.Data.Response)
{
    if (pFHIRRequest.RequestMethod="POST") && (pFHIRRequest.RequestPath="Observation") {
        if pFHIRResponse.Status=201 {
            set sc = ##class(Ens.Director).CreateBusinessService("FHIR Observation In", .service)
            if ($isobject(service)) {
                set sc = service.ProcessInput(pFHIRResponse.Id, .output)
            }
        }
    }
}

}
