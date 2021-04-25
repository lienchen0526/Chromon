from typing import Dict, List, TypedDict
from typing import Optional, Any, Literal, Union
import enum

Number = Union[int, float]

class Browser(object):
    BrowserContextID = str

class Security(object):
    MixedContentType = Literal[
        'blockable', 
        'optionally-blockable', 
        'none'
    ]
    SecurityState = Literal[
        "unknown", 
        "neutral", 
        "insecure", 
        "secure", 
        "info", 
        "insecure-broken"
    ]
    CertificateId = int

class Runtime(object):
    UniqueDebuggerId = str
    ScriptId = str
    ExecutionContextId = str

    StackTraceId = TypedDict(
        "StackTraceId",
        {
            "id": str,
            "debuggerId": Optional[UniqueDebuggerId]
        }
    )
    CallFrame = TypedDict(
        "CallFrame",
        {
            "functionName": str,
            "scriptId": ScriptId,
            "url": str,
            "lineNumber": int,
            "columnNumber": int
        }
    )
    StackTrace = TypedDict(
        "StackTrace",
        {
            "description": Optional[str],
            "callFrames": List[CallFrame],
            "parent": Optional[dict],
            "parentId": StackTraceId
        }
    )
    pass

class DOM(object):
    BackendNodeId = int

class Debugger(object):
    ScriptLanguage = Literal["JavaScript", "WebAssembly"]
    DebugSymbols = TypedDict(
        "DebugSymbols",
        {
            "type": Literal["None", "SourceMap", "EmbededDWARF", "ExternalDWARF"],
            "externalURL": Optional[str]
        }
    )

class Network(object):

    LoaderId = str
    RequestId = str
    HTTPMethod = Literal[
        "GET", 
        "POST", 
        "DELETE", 
        "HEAD",
        "PUT",
        "CONNECT",
        "OPTIONS",
        "TRACE",
        "PATCH"
    ]
    Headers = Dict[str, Any]
    PostDataEntry = str
    ResourcePriority = Literal[
        "VeryLow", 
        "Low", 
        "Medium", 
        "High", 
        "VeryHigh"
    ]
    ReferrerPolicy = Literal[
        "unsafe-url",
        "no-referrer-when-downgrade", 
        "no-referrer", 
        "origin", 
        "origin-when-cross-origin", 
        "same-origin", 
        "strict-origin", 
        "strict-origin-when-cross-origin"
    ]
    TrustTokenOperationType = Literal[
        "Issuance", 
        "Redemption", 
        "Signing"
    ]
    ResourceType = Literal[
        "Document", "Stylesheet", "Image", 
        "Media", "Font", "Script", "TextTrack", 
        "XHR", "Fetch", "EventSource", "WebSocket", 
        "Manifest", "SignedExchange", "Ping", 
        "CSPViolationReport", "Preflight", "Other"
    ]
    TrustTokenParams = TypedDict(
        "TrustTokenParams",
        {
            "type": TrustTokenOperationType,
            "refreshPolicy": Literal["UseCached", "Refresh"],
            "issuers": Optional[List[str]]
        }
    )
    MonotonicTime = Number
    TimeSinceEpoch = Number
    ServiceWorkerResponseSource = Literal[
        "cache-storage", 
        "http-cache", 
        "fallback-code", 
        "network"
    ]
    CertificateTransparencyCompliance = Literal[
        "unknown", "not-compliant", "compliant"
    ]
    SignedCertificateTimestamp = TypedDict(
        "SignedCertificateTimestamp",
        {
            "status": str,
            "origin": str,
            "logDescription": str,
            "logId": str,
            "timestamp": TimeSinceEpoch,
            "hashAlgorithm": str,
            "signatureAlgorithm": str,
            "signatureData": str
        }
    )
    SecurityDetails = TypedDict(
        "SecurityDetails",
        {
            "protocol": str, # eg. "TLS 1.2", "QUIC"
            "keyExchange": str,
            "keyExchangeGroup": Optional[str],
            "cipher": str,
            "mac": Optional[str], # TLS MAC. Note that AEAD ciphers do not have separate MACs.
            "certificateId": Security.CertificateId,
            "subjectName": str,
            "sanList": List[str],
            "issuer": str,
            "validFrom": TimeSinceEpoch,
            "validTo": TimeSinceEpoch,
            "signedCertificateTimestampList": List[SignedCertificateTimestamp],
            "certificateTransparencyCompliance": CertificateTransparencyCompliance
        }
    )
    ResourceTiming = TypedDict(
        "ResourceTiming",
        {
            "requestTime": Number,
            "proxyStart": Number,
            "proxyEnd": Number,
            "dnsStart": Number,
            "dnsEnd": Number,
            "connectStart": Number,
            "connectEnd": Number,
            "sslStart": Number,
            "sslEnd": Number,
            "workerStart": Number,
            "workerReady": Number,
            "workerFetchStart": Number,
            "workerRespondWithSettled": Number,
            "sendStart": Number,
            "sendEnd": Number,
            "pushStart": Number,
            "pushEnd": Number,
            "receiveHeadersEnd": Number
        }
    )
    Request = TypedDict(
        "Request",
        {
            "url": str,
            "urlFragment": Optional[str],
            "method": HTTPMethod,
            "headers": Headers,
            "postData": Optional[str],
            "hasPostData": Optional[bool],
            "postDataEntries": Optional[List[PostDataEntry]],
            "refererPolicy": ReferrerPolicy,
            "isLinkPreload": Optional[bool],
            "mixedContentType": Optional[Security.MixedContentType],
            "initialPriority": ResourcePriority,
            "trustTokenParams": TrustTokenParams
        }
    )
    Response = TypedDict(
        "Response",
        {
            "url": str,
            "status": int,
            "statusText": str,
            "headers": Headers,
            "headersText": Optional[str],
            "mimeType": str,
            "requestHeaders": Headers,
            "requestHeadersText": str,
            "connectionReused": bool,
            "connectionId": Number,
            "remoteIPAddress": Optional[str],
            "remotePort": Optional[int],
            "fromDiskCache": Optional[bool],
            "fromPrefetchCache": Optional[bool],
            "encodedDataLength": Number,
            "timing": Optional[ResourceTiming],
            "serviceWorkerResponseSource": Optional[ServiceWorkerResponseSource],
            "responseTime": Optional[TimeSinceEpoch],
            "cacheStorageCacheName": Optional[str],
            "protocol": Optional[str],
            "securityState": Security.SecurityState,
            "securityDetails": Optional[SecurityDetails]
        }
    )
    Initiator = TypedDict(
        "Initiator",
        {
            "type": Literal[
                "parser", 
                "script", 
                "preload", 
                "SignedExchange", 
                "preflight", 
                "other"
            ],
            "stack": Optional[Runtime.StackTrace],
            "url": Optional[str],
            "lineNumber": Optional[int],
            "columnNumber": Optional[int],
            "requestId": Optional[RequestId]
        }
    )

class Page(object):
    FrameId = str
    AdFrameType = Literal['none', 'child', 'root']
    SecureContextType = Literal[
        'Secure', 
        'SecureLocalhost', 
        'InsecureScheme', 
        'InsecureAncestor'
    ]
    ClientNavigationReason = Literal[
        'formSubmissionGet', 
        'formSubmissionPost', 
        'httpHeaderRefresh', 
        'scriptInitiated', 
        'metaTagRefresh', 
        'pageBlockInterstitial', 
        'reload', 
        'anchorClick'
    ]
    ClientNavigationDisposition = Literal[
        'currentTab', 
        'newTab', 
        'newWindow', 
        'download'
    ]
    CrossOriginIsolatedContextType = Literal[
        'Isolated', 
        'NotIsolated', 
        'NotIsolatedFeatureDisabled'
    ]
    GatedAPIFeatures = Literal[
        'SharedArrayBuffers', 
        'SharedArrayBuffersTransferAllowed', 
        'PerformanceMeasureMemory', 
        'PerformanceProfile'
    ]
    Frame = TypedDict(
        "Frame",
        {
            "id": FrameId,
            "parentId": Optional[str],
            "loaderId": Network.LoaderId,
            "name": Optional[str],
            "url": str,
            "urlFragment": Optional[str],
            "domainAndRegistry": str,
            "securityOrigin": str,
            "mimeType": str,
            "unreachableUrl": Optional[str],
            "adFrameType": Optional[AdFrameType],
            "secureContextType": SecureContextType,
            "crossOriginIsolatedContextType": CrossOriginIsolatedContextType,
            "gatedAPIFeatures": List[GatedAPIFeatures]
        }
    )
    FrameTree = TypedDict(
        "FrameTree",
        {
            "frame": Frame,
            "childFrames": Optional[list]
        }
    )
    NavigationType = Literal["Navigation", "BackForwardCacheRestore"]

class Target(object):
    TargetID = str # TargetID can be Page.FrameID.
    SessionID = str # The unique session identifier every debugged target connected by python
    ValidTypes = ('page', 'iframe', 'browser', 'script')

    TargetInfo = TypedDict(
        "TargetInfo",
        {
            "targetId": TargetID,
            "type": str,
            "title": str,
            "url": str,
            "attached": bool,
            "openerId": Optional[TargetID],
            "canAccessOpener": bool,
            "openerFrameId": Optional[Page.FrameId],
            "browserContextId": Optional[Browser.BrowserContextID]
        }
    )

class Generic(object):

    TabInfo = TypedDict(
        "TabInfo",
        {
            "description": str,
            "devtoolsFrontendUrl": str,
            "id": str,
            "title": str,
            "url": str,
            "webSocketDebuggerUrl": str
        }
    )

    GlobalDebugableInfo = TypedDict(
        "GlobalDebugableInfo",
        {
            "Browser": str,
            "Protocol-Version": str,
            "User-Agent": str,
            "V8-Version": str,
            "Webkit-Version": str,
            "webSocketDebuggerUrl": str
        }
    )

    DebugCommand = TypedDict(
        "DebugCommand",
        {
            "id": Optional[int],
            "method": str,

            #This is used when using flatten mode. It specify the more accurate target method.
            "sessionId": Optional[Target.SessionID],
            "params": Optional[Dict[str, str]]
        }
    )

    DebugReply = TypedDict(
        "DebugReply",
        {
            # Message id `int` specified in DebugCommand, if you have.
            "id": int,
            
            # The <RETURN OBJECT> mentioned in Chrome Devtools Protocols
            "result": Dict[str, Any]
        }
    )
