// Experimental GPU-only Qt-frame -> fixed DirectComposition HWND bridge.
// Uses public Windows SDK interfaces. The independent native UI thread submits
// GPU frames; unlike the first control spike, animation is not DComp-owned.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <dxgi1_2.h>
#include <dxgi1_3.h>
#include <dxgi1_4.h>
#include <dcomp.h>
#include <wrl/client.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <deque>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>

using Microsoft::WRL::ComPtr;
#define EXPORT extern "C" __declspec(dllexport)
namespace {
thread_local std::string lastError;
void check(HRESULT hr,const char* operation) {
    if(FAILED(hr)) { char message[256]; sprintf_s(message,"%s: HRESULT 0x%08X",operation,unsigned(hr));
        throw std::runtime_error(message); }
}
double nowSeconds() {
    LARGE_INTEGER count,frequency; QueryPerformanceCounter(&count); QueryPerformanceFrequency(&frequency);
    return double(count.QuadPart)/double(frequency.QuadPart);
}
double flow(double p) {
    p=std::clamp(p,0.,1.); return p*p*p*p*(35.+p*(-84.+p*(70.-20.*p)));
}
std::atomic<uint64_t> nextFrameIdentity{0},nextResourceIdentity{0},nextHostGeneration{0};
struct Frame {
    ComPtr<ID3D11Texture2D> texture;
    ComPtr<IDXGIKeyedMutex> mutex;
    D3D11_TEXTURE2D_DESC desc{};
    HANDLE sharedHandle=nullptr;
    uint64_t revision=++nextFrameIdentity;
};
struct Pixels {
    ComPtr<ID3D11Texture2D> texture;
    ComPtr<ID3D11ShaderResourceView> view;
    UINT width=0,height=0;
    uint64_t frameRevision=0,resourceIdentity=0;
};
bool probeCoordinatesValid(const int* xy,unsigned count,unsigned width,unsigned height,
                           int offsetX,int offsetY,unsigned hostWidth,unsigned hostHeight) {
    if(!xy || !count || count>64 || offsetX<0 || offsetY<0) return false;
    for(unsigned i=0;i<count;++i) {
        const int x=xy[2*i],y=xy[2*i+1];
        if(x<0 || y<0 || unsigned(x)>=width || unsigned(y)>=height ||
           uint64_t(x)+unsigned(offsetX)>=hostWidth || uint64_t(y)+unsigned(offsetY)>=hostHeight)
            return false;
    }
    return true;
}
bool probeEndpointStateValid(unsigned flags,bool endpointSubmitted,bool targetAvailable,
                             bool submittedAvailable,double motion,double content) {
    // The running flag remains set after completion. Endpoint submission and
    // the exact final submitted sample establish that this is a stopped clock.
    return (flags&(1|2|4|8))==(1|2|4|8) && !(flags&16) && endpointSubmitted &&
        targetAvailable && submittedAvailable && motion==1. && content==1.;
}
HWND sourceVisibilityBand(bool sourceTopmost) {
    return sourceTopmost ? HWND_TOPMOST : HWND_NOTOPMOST;
}
bool sourceVisibilityBandMatches(LONG_PTR extendedStyle,bool sourceTopmost) {
    return ((extendedStyle&WS_EX_TOPMOST)!=0)==sourceTopmost;
}
bool sourceBandOperationAllowed(unsigned flags,bool policyKnown,bool visible,bool expectedVisible,bool nativeOwnerThread) {
    return (flags&1) && !(flags&(2|16)) && policyKnown && visible==expectedVisible && nativeOwnerThread;
}
struct ProbePixels {
    int xy[128]{};
    unsigned char source[256]{},submitted[256]{};
};
// Additive diagnostic identities contain monotonic opaque IDs, never pointers.
// Orientation 1 is top-left; sampled subresource is always mip/array slice 0.
struct FrameIdentity {
    uint32_t version=1,byteSize=48;
    uint64_t revision=0;
    uint32_t width=0,height=0,format=0,mipLevels=0,arraySize=0,sampleCount=0;
    uint32_t subresource=0,orientation=1;
};
static_assert(sizeof(FrameIdentity)==48,"Diagnostic frame identity ABI layout");
struct ProbeIdentity {
    uint32_t version=1,byteSize=200;
    uint64_t hostGeneration=0,snapshotRevision=0,sourceFrameRevision=0,targetFrameRevision=0;
    uint32_t submittedPresentId=0,phase=0,witnessRevision=0,subresource=0;
    double snapshotQueuedSeconds=0,presentBeginSeconds=0,presentReturnSeconds=0,motion=0,content=0;
    int32_t hostLeft=0,hostTop=0,hostWidth=0,hostHeight=0;
    int32_t sourceLeft=0,sourceTop=0,sourceWidth=0,sourceHeight=0;
    int32_t targetLeft=0,targetTop=0,targetWidth=0,targetHeight=0;
    uint32_t sourceFormat=0,targetFormat=0,snapshotFormat=0,snapshotWidth=0,snapshotHeight=0;
    uint32_t snapshotEnabled=0,orientation=1,premultiplied=1;
    uint64_t sourceResourceIdentity=0,targetResourceIdentity=0,snapshotResourceIdentity=0;
};
static_assert(sizeof(ProbeIdentity)==200,"Diagnostic submitted identity ABI layout");
struct SourceTransferObservation {
    uint32_t version=1,byteSize=192;
    uint64_t hostGeneration=0,sequence=0;
    uint32_t stage=0,accepted=0,win32Error=0,expectedTopmost=0;
    uint32_t currentThreadId=0,currentProcessId=0,liveThreadId=0,liveProcessId=0,nativeThreadId=0,nativeProcessId=0;
    uint32_t sameParent=0,sameProcess=0,liveThreadOwned=0,nativeThreadOwned=0;
    uint32_t liveForegroundEntry=0,liveForegroundExit=0,liveOwnerRelation=0,nativeOwnerRelation=0;
    uint32_t liveStyleEntry=0,nativeStyleEntry=0,liveStyleExit=0,nativeStyleExit=0;
    uint32_t liveVisibleEntry=0,nativeVisibleEntry=0,liveVisibleExit=0,nativeVisibleExit=0;
    uint32_t beginAccepted=0,liveDeferAccepted=0,nativeDeferAccepted=0,endAccepted=0;
    double entrySeconds=0,beginBatchSeconds=0,endBatchBeginSeconds=0,endBatchReturnSeconds=0,exitSeconds=0;
    uint32_t traceEnabled=0,policySampled=0;
};
static_assert(sizeof(SourceTransferObservation)==192,"Diagnostic source transfer ABI layout");
struct SourceWindowPosRow {
    uint64_t sequence=0;
    double timeSeconds=0;
    uint32_t message=0,phase=0,insertAfterBandBefore=0,insertAfterBandAfter=0;
    uint32_t flagsBefore=0,flagsAfter=0,styleBefore=0,styleAfter=0;
    uint32_t currentThreadId=0,expectedTopmost=0,visibleAfter=0,reserved=0;
};
static_assert(sizeof(SourceWindowPosRow)==64,"Diagnostic source WINDOWPOS row ABI layout");
struct SourceWindowPosTrace {
    uint32_t version=1,byteSize=1048,rowByteSize=64,count=0;
    uint64_t totalRows=0;
    SourceWindowPosRow rows[16]{};
};
static_assert(sizeof(SourceWindowPosTrace)==1048,"Diagnostic source WINDOWPOS trace ABI layout");
// Opt-in local evidence. Window handles/thread IDs are never public identities;
// callers must sanitize them before publishing aggregates. No wait-state probe
// is performed: probing a DXGI availability event could consume its signal.
enum NativeCall : uint32_t {
    NativeFrameSlotWait=1,NativeSourceBandPosition=2,NativeBeginVisibilityBatch=3,
    NativeDeferLiveHide=4,NativeDeferNativeShow=5,NativeEndVisibilityBatch=6,
    NativeCompositionCommit=7,NativeCommitCompletion=8,NativeSourceShow=9,
    NativeWitnessPosition=10,NativeAcquireSharedMutex=11,NativeReleaseSharedMutex=12,
    NativePresent=13,NativeLastPresentCount=14,NativeFrameStatistics=15,
    NativeGetBuffer=16,NativeOpenSharedResource=17,NativeCreateOwnedTexture=18,
    NativeCreateOwnedView=19,NativeCreateRenderTarget=20,NativeCommandPost=21,
    NativeCommandCompletion=22,NativeDestroyPost=23,NativeDestroyWait=24,
    NativeHideHost=25,NativeSetTimer=26,NativeValidateSourceBand=27,
    NativeCreateWindow=28,NativeValidateCreatedHost=29,NativeInitializationCompletion=30,
    NativeDestroyWindow=31,NativeCloseFrameHandle=32,NativeValidateCreationSource=33
};
struct NativeWindowState {
    uint64_t window=0,foreground=0,focus=0,active=0,owner=0;
    uint32_t thread=0,process=0,foregroundThread=0,foregroundProcess=0;
    uint32_t guiFlags=0,valid=0,visible=0,iconic=0,zoomed=0,cloaked=0;
    uint32_t cloakHRESULT=uint32_t(E_NOTIMPL),style=0,exstyle=0,queryErrors=0;
    int32_t windowRect[4]{},clientRect[4]{},workRect[4]{};
    uint32_t dpi=0,reserved=0;
};
static_assert(sizeof(NativeWindowState)==152,"Diagnostic native window state ABI layout");
struct NativeCallRow {
    uint32_t version=1,byteSize=896,call=0,phase=0;
    uint64_t sequence=0,startQpc=0,returnQpc=0,qpcFrequency=0;
    double beginSeconds=0,returnSeconds=0;
    uint32_t result=0,win32Error=0,lastErrorApplicable=0,timeoutMs=0;
    uint32_t waitStateBefore=0,waitStateAfter=0,alertable=0,flagsBefore=0;
    uint32_t flagsAfter=0,currentThread=0,guiThread=0,workerThread=0;
    uint32_t expectedPresentId=0,submittedBefore=0,submittedAfter=0,displayedBefore=0;
    uint32_t displayedAfter=0,statisticsHRESULT=0,bufferIndex=UINT32_MAX,bufferCount=2;
    uint64_t expectedHostGeneration=0,hostGeneration=0,expectedSourceGeneration=0,sourceGeneration=0;
    uint64_t expectedTargetGeneration=0,targetGeneration=0,commitBefore=0,commitAfter=0;
    uint64_t adapterIdentity=0,deviceIdentity=0,swapchainIdentity=0,waitIdentity=0;
    uint64_t sourceResourceIdentity=0,targetResourceIdentity=0,keyedMutexKey=0;
    uint32_t keyedMutexState=0,fenceState=0,beforeMotion=0,diagnosticOverheadUs=0;
    NativeWindowState nativeBefore,nativeAfter,liveBefore,liveAfter;
    int64_t adapterLuid=0;
};
static_assert(sizeof(NativeCallRow)==896,"Diagnostic native call row ABI layout");
struct NativeCallTrace {
    uint32_t version=1,byteSize=230312,rowByteSize=896,count=0;
    uint64_t totalRows=0,droppedRows=0;
    uint32_t enabled=0,hasFirstFailure=0;
    NativeCallRow firstFailure;
    NativeCallRow rows[256]{};
};
static_assert(sizeof(NativeCallTrace)==230312,"Diagnostic native call trace ABI layout");
// Additive creation/lifecycle evidence leaves all preceding ABI layouts intact.
// Raw relationships are local diagnostic data, never public window identities.
struct NativeCreationRow {
    uint32_t phase=0,flags=0;
    uint64_t qpc=0;
    double seconds=0;
    NativeWindowState native,live;
    uint64_t nativeParent=0,nativePrevious=0,nativeNext=0,nativeMonitor=0;
    uint64_t liveParent=0,livePrevious=0,liveNext=0,liveMonitor=0;
};
static_assert(sizeof(NativeCreationRow)==392,"Diagnostic creation row ABI layout");
struct NativeCreationObservation {
    uint32_t version=1,byteSize=4816,rowByteSize=392,count=0;
    uint64_t hostGeneration=0,frameRevision=0,qpcFrequency=0;
    uint32_t enabled=0,strategy=0,expectedTopmost=0,requestedStyle=0,requestedExStyle=0;
    uint32_t sourceValidated=0,creationAccepted=0,initializationAccepted=0;
    uint32_t cleanupCompleted=0,hostRetained=0,failureStage=0,reserved=0;
    uint64_t createBeginQpc=0,createReturnQpc=0;
    uint32_t createResult=0,createWin32Error=0;
    NativeCreationRow rows[12]{};
};
static_assert(sizeof(NativeCreationObservation)==4816,"Diagnostic creation observation ABI layout");
struct Constants {
    float currentRect[4],sourceRect[4],targetRect[4],sizes[4],motion[4];
    float witnessRect[4],witnessColor[4];
};
static_assert(sizeof(Constants)==112,"HLSL constant-buffer layout");
// Additive diagnostic ABI. QPC seconds describe API boundaries, not scanout.
// A caller initializes version/byteSize before requesting a consistent snapshot.
struct Observation {
    uint32_t version=1,byteSize=208;
    uint64_t sequence=0;
    uint32_t submittedPresentId=0,lastPresentHRESULT=0;
    double lastPresentBeginSeconds=0,lastPresentReturnSeconds=0;
    double sourceCommitBeginSeconds=0,sourceCommitReturnSeconds=0;
    double sourceWaitBeginSeconds=0,sourceWaitReturnSeconds=0;
    double sourceShowBeginSeconds=0,sourceShowReturnSeconds=0;
    double targetImportBeginSeconds=0,targetReadySeconds=0;
    double endpointPresentReturnSeconds=0;
    double hostHideBeginSeconds=0,hostHideReturnSeconds=0;
    double lastFrameElapsedSeconds=0,lastFrameMotion=0,lastFrameContent=0;
    float currentRect[4]{};
    uint32_t sourceWidth=0,sourceHeight=0,targetWidth=0,targetHeight=0;
    uint32_t sourceFormat=0,targetFormat=0;
    int32_t hostLeft=0,hostTop=0,hostWidth=0,hostHeight=0;
};
static_assert(sizeof(Observation)==208,"Diagnostic observation ABI layout");
struct PresentObservation {
    uint32_t version=1,byteSize=80;
    uint64_t sequence=0;
    uint32_t submittedPresentId=0,presentHRESULT=0;
    double presentBeginSeconds=0,presentReturnSeconds=0,elapsedSeconds=0,motion=0,content=0;
    float currentRect[4]{};
};
static_assert(sizeof(PresentObservation)==80,"Diagnostic Present row ABI layout");
struct PresentTrace {
    uint32_t version=1,byteSize=10264,rowByteSize=80,count=0;
    uint64_t totalFrames=0;
    PresentObservation rows[128]{};
};
static_assert(sizeof(PresentTrace)==10264,"Diagnostic Present trace ABI layout");
bool probeIdentityMatches(const ProbeIdentity& identity,unsigned phase,const Observation& observation) {
    return identity.snapshotEnabled && identity.hostGeneration && identity.snapshotRevision &&
        identity.snapshotResourceIdentity && identity.phase==phase && identity.subresource==0 &&
        identity.orientation==1 && identity.submittedPresentId==observation.submittedPresentId &&
        identity.presentReturnSeconds==observation.lastPresentReturnSeconds &&
        identity.motion==observation.lastFrameMotion && identity.content==observation.lastFrameContent;
}
struct Host;
template<class F> auto nativeInvoke(Host& h,NativeCall operation,unsigned timeout,uint64_t expectedFrame,
                                   uint64_t mutexKey,bool usesLastError,F function)->decltype(function());
struct Host {
    HWND hwnd=nullptr;
    std::thread worker;
    std::mutex queueMutex,errorMutex,observationMutex,sourceTransferMutex;
    Observation observation;
    ProbeIdentity probeIdentity;
    SourceTransferObservation sourceTransferObservation;
    SourceWindowPosTrace sourceWindowPosTrace;
    bool sourceTransferTraceEnabled=false;
    std::atomic<bool> sourceTransferTraceActive{false};
    std::atomic<HWND> sourceTransferLive{nullptr};
    std::atomic<bool> nativeCallTraceEnabled{false};
    std::mutex nativeCallTraceMutex;
    std::unique_ptr<NativeCallTrace> nativeCallTrace;
    uint64_t nativeQpcFrequency=0;
    std::atomic<uint64_t> adapterIdentity{0},deviceIdentity{0},swapchainIdentity{0},waitIdentity{0};
    std::atomic<int64_t> adapterLuid{0};
    std::atomic<uint64_t> compositionCommitRevision{0};
    std::atomic<uint32_t> workerThreadId{0},liveGuiThreadId{0};
    std::atomic<HWND> diagnosticLive{nullptr};
    std::atomic<HWND> diagnosticNative{nullptr}; // Retained identity through shutdown.
    ComPtr<IDXGISwapChain3> diagnosticSwapchain;
    HMODULE diagnosticDwm=nullptr;
    using DwmAttribute=HRESULT(WINAPI*)(HWND,DWORD,PVOID,DWORD);
    DwmAttribute diagnosticDwmAttribute=nullptr;
    PresentObservation presentRows[128]{};
    uint64_t totalPresentRows=0;
    std::deque<std::function<void()>> queue;
    std::string error;
    std::atomic<unsigned> flags{0};
    ComPtr<ID3D11Device> gpu;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<IDCompositionDevice> compositor;
    ComPtr<IDCompositionTarget> target;
    ComPtr<IDCompositionVisual> root;
    ComPtr<IDXGISwapChain1> swapchain;
    // D3D11 rotates flip-chain storage behind retained GetBuffer(0) interfaces.
    // An opt-in owned GPU copy before Present preserves only stopped source
    // and complete endpoint submissions. Intermediate motion has no copy.
    ComPtr<ID3D11Texture2D> lastSubmittedTexture;
    bool probeSnapshotEnabled=false;
    uint64_t generation=++nextHostGeneration,snapshotRevision=0,snapshotResourceIdentity=0;
    HANDLE frameReady=nullptr;
    std::atomic<unsigned> submittedCount{0},displayedCount{0},statisticsResult{0};
    UINT endpointCount=0;
    bool endpointSubmitted=false;
    ComPtr<ID3D11VertexShader> vertexShader;
    ComPtr<ID3D11PixelShader> pixelShader;
    ComPtr<ID3D11Buffer> constants;
    ComPtr<ID3D11SamplerState> sampler;
    Pixels source,destination;
    int hostWidth=0,hostHeight=0;
    float sourceX=0,sourceY=0,sourceW=0,sourceH=0;
    float targetX=0,targetY=0,targetW=0,targetH=0,header=0,rightWidth=0;
    std::atomic<double> startSeconds{0},duration{0};
    double blendStart=0;
    // Optional qualification witness, wholly outside both client rectangles.
    // It shares the actual swapchain Present with the sampled representation.
    float witnessX=0,witnessY=0;
    uint32_t witnessRevision=0;
    bool apartment=false;
    bool deferredSourceVisibility=false;
    // Explicit opt-in: establish the verified owned source band at HWND
    // creation, rather than requiring a later nonforeground band promotion.
    bool sourceCreationBandKnown=false,sourceCreationTopmost=false;
    std::mutex creationMutex;
    std::unique_ptr<NativeCreationObservation> creationObservation;
    // Published by the authorized live GUI owner before native visibility
    // transfer; the stopped worker raise consumes that same source policy.
    std::atomic<bool> sourceTopmost{false},sourceBandKnown{false};
    ~Host() { if(diagnosticDwm) FreeLibrary(diagnosticDwm); }
    template<class F> void observe(F writer) {
        std::lock_guard<std::mutex> lock(observationMutex);
        writer(observation); ++observation.sequence;
    }
    void fail(const std::string& message) {
        std::lock_guard<std::mutex> lock(errorMutex);
        // Rejected follow-up commands must retain the failure that ended the
        // transaction, rather than replace it with a generic failed-state error.
        if(!(flags.load()&16)) error=message;
        flags.fetch_or(16);
    }
    template<class F> int call(F function) {
        auto promise=std::make_shared<std::promise<int>>(); auto future=promise->get_future();
        auto cancelled=std::make_shared<std::atomic<bool>>(false);
        { std::lock_guard<std::mutex> lock(queueMutex);
          queue.push_back([this,promise,function,cancelled] {
              if(cancelled->load()) { promise->set_value(0); return; }
              try { function(); promise->set_value(1); }
              catch(const std::exception& ex) { fail(ex.what()); promise->set_value(0); }
          }); }
        if(!nativeInvoke(*this,NativeCommandPost,0,0,0,true,[&] { return PostMessageW(hwnd,WM_APP+1,0,0); })) {
            cancelled->store(true); fail("Native command PostMessageW failed"); return 0;
        }
        if(nativeInvoke(*this,NativeCommandCompletion,2000,0,0,false,[&] {
                return future.wait_for(std::chrono::seconds(2)); })!=std::future_status::ready) {
            cancelled->store(true); fail("Native command exceeded bounded 2000 ms completion"); return 0;
        }
        return future.get();
    }
};
void nativeWindowState(Host& h,HWND window,NativeWindowState& row) {
    row.window=uint64_t(uintptr_t(window));
    row.foreground=uint64_t(uintptr_t(GetForegroundWindow()));
    DWORD foregroundProcess=0,process=0;
    row.foregroundThread=GetWindowThreadProcessId(reinterpret_cast<HWND>(uintptr_t(row.foreground)),&foregroundProcess);
    row.foregroundProcess=foregroundProcess;
    if(!window || !IsWindow(window)) { row.queryErrors|=1; return; }
    row.valid=1; row.thread=GetWindowThreadProcessId(window,&process); row.process=process;
    row.visible=IsWindowVisible(window)!=FALSE; row.iconic=IsIconic(window)!=FALSE;
    row.zoomed=IsZoomed(window)!=FALSE; row.owner=uint64_t(uintptr_t(GetWindow(window,GW_OWNER)));
    row.style=uint32_t(GetWindowLongPtrW(window,GWL_STYLE));
    row.exstyle=uint32_t(GetWindowLongPtrW(window,GWL_EXSTYLE));
    GUITHREADINFO gui{}; gui.cbSize=sizeof(gui);
    if(GetGUIThreadInfo(row.thread,&gui)) {
        row.guiFlags=gui.flags; row.focus=uint64_t(uintptr_t(gui.hwndFocus));
        row.active=uint64_t(uintptr_t(gui.hwndActive));
    } else row.queryErrors|=2;
    RECT rect{};
    if(GetWindowRect(window,&rect)) memcpy(row.windowRect,&rect,sizeof(rect));
    else row.queryErrors|=4;
    if(GetClientRect(window,&rect)) {
        POINT origin{rect.left,rect.top};
        if(ClientToScreen(window,&origin)) {
            row.clientRect[0]=origin.x; row.clientRect[1]=origin.y;
            row.clientRect[2]=origin.x+rect.right-rect.left;
            row.clientRect[3]=origin.y+rect.bottom-rect.top;
        } else row.queryErrors|=8;
    } else row.queryErrors|=8;
    MONITORINFO monitor{}; monitor.cbSize=sizeof(monitor);
    if(GetMonitorInfoW(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST),&monitor))
        memcpy(row.workRect,&monitor.rcWork,sizeof(monitor.rcWork));
    else row.queryErrors|=16;
    row.dpi=GetDpiForWindow(window);
    if(h.diagnosticDwmAttribute)
        row.cloakHRESULT=uint32_t(h.diagnosticDwmAttribute(window,14,&row.cloaked,sizeof(row.cloaked)));
    if(FAILED(HRESULT(row.cloakHRESULT))) row.queryErrors|=32;
}
uint32_t nativeWaitState(DWORD result) {
    if(result==WAIT_OBJECT_0) return 1;
    if(result==WAIT_TIMEOUT) return 2;
    if(result==WAIT_FAILED) return 3;
    if(result==WAIT_ABANDONED_0) return 4;
    return 5;
}
bool nativeCallFailed(uint32_t call,uint32_t result) {
    switch(call) {
    case NativeFrameSlotWait: case NativeDestroyWait: return result!=WAIT_OBJECT_0;
    case NativeCommandCompletion: case NativeInitializationCompletion:
        return result!=uint32_t(std::future_status::ready);
    case NativeAcquireSharedMutex: return result!=uint32_t(S_OK);
    case NativeReleaseSharedMutex: case NativeCompositionCommit: case NativeCommitCompletion:
    case NativePresent: case NativeLastPresentCount: case NativeFrameStatistics: case NativeGetBuffer:
    case NativeOpenSharedResource: case NativeCreateOwnedTexture: case NativeCreateOwnedView:
    case NativeCreateRenderTarget: return FAILED(HRESULT(result));
    case NativeHideHost: return false; // ShowWindow returns prior visibility, not success.
    default: return result==0;
    }
}
void nativeStoreCall(Host& h,NativeCallRow row) {
    std::lock_guard<std::mutex> lock(h.nativeCallTraceMutex);
    auto& trace=*h.nativeCallTrace;
    row.sequence=++trace.totalRows;
    trace.rows[(row.sequence-1)%256]=row;
    trace.count=unsigned(std::min(trace.totalRows,uint64_t(256)));
    trace.droppedRows=trace.totalRows-trace.count;
    // These optional statistics failures are retained rows, not failures of
    // the transaction (DISJOINT is expected before stable statistics exist).
    if(!trace.hasFirstFailure && row.call!=NativeFrameStatistics && row.call!=NativeLastPresentCount &&
       nativeCallFailed(row.call,row.result)) {
        trace.firstFailure=row; trace.hasFirstFailure=1;
    }
}
template<class F> auto nativeInvoke(Host& h,NativeCall operation,unsigned timeout,uint64_t expectedFrame,
                                   uint64_t mutexKey,bool usesLastError,F function)->decltype(function()) {
    if(!h.nativeCallTraceEnabled.load()) return function();
    LARGE_INTEGER diagnosticBegin{}; QueryPerformanceCounter(&diagnosticBegin);
    NativeCallRow row;
    row.call=operation; row.timeoutMs=timeout; row.lastErrorApplicable=usesLastError;
    row.flagsBefore=h.flags.load(); row.beforeMotion=!(row.flagsBefore&2);
    row.phase=(operation>=NativeDestroyPost && operation<=NativeHideHost) ||
        operation==NativeDestroyWindow || operation==NativeCloseFrameHandle ? 5u :
        (operation>=NativeSourceBandPosition && operation<=NativeEndVisibilityBatch) || operation==NativeValidateSourceBand ? 2u :
        (row.flagsBefore&2) && ((operation>=NativeAcquireSharedMutex && operation<=NativeReleaseSharedMutex) ||
            (operation>=NativeOpenSharedResource && operation<=NativeCreateOwnedView)) ? 4u :
        (row.flagsBefore&2) ? 3u : 1u;
    row.currentThread=GetCurrentThreadId(); row.guiThread=h.liveGuiThreadId.load();
    row.workerThread=h.workerThreadId.load(); row.expectedHostGeneration=row.hostGeneration=h.generation;
    // Resources are only inspected on their owning worker. GUI dispatch rows
    // never read source/destination COM resources while imports can mutate them.
    if(row.currentThread==row.workerThread) {
        row.sourceGeneration=h.source.frameRevision; row.targetGeneration=h.destination.frameRevision;
        row.sourceResourceIdentity=h.source.resourceIdentity; row.targetResourceIdentity=h.destination.resourceIdentity;
        if(h.diagnosticSwapchain) row.bufferIndex=h.diagnosticSwapchain->GetCurrentBackBufferIndex();
    }
    row.expectedSourceGeneration=row.sourceGeneration;
    row.expectedTargetGeneration=row.targetGeneration;
    if(expectedFrame) {
        if(row.flagsBefore&1) row.expectedTargetGeneration=expectedFrame;
        else row.expectedSourceGeneration=expectedFrame;
    }
    row.commitBefore=h.compositionCommitRevision.load(); row.keyedMutexKey=mutexKey;
    row.adapterIdentity=h.adapterIdentity; row.deviceIdentity=h.deviceIdentity;
    row.swapchainIdentity=h.swapchainIdentity; row.waitIdentity=h.waitIdentity; row.adapterLuid=h.adapterLuid;
    row.submittedBefore=h.submittedCount.load();
    row.expectedPresentId=row.submittedBefore+
        ((operation==NativeFrameSlotWait || operation==NativeGetBuffer || operation==NativeCreateRenderTarget ||
          operation==NativePresent || operation==NativeLastPresentCount) ? 1u : 0u);
    row.displayedBefore=h.displayedCount.load();
    const HWND live=h.diagnosticLive.load();
    nativeWindowState(h,h.diagnosticNative.load(),row.nativeBefore); nativeWindowState(h,live,row.liveBefore);
    LARGE_INTEGER counter{}; QueryPerformanceCounter(&counter);
    row.startQpc=uint64_t(counter.QuadPart); row.qpcFrequency=h.nativeQpcFrequency;
    row.beginSeconds=double(row.startQpc)/double(row.qpcFrequency);
    const auto result=function();
    // This is the first operation after the native return. QPC, window queries,
    // locks, formatting and throwing cannot replace the captured Win32 error.
    const DWORD immediateError=GetLastError();
    if constexpr(std::is_pointer_v<decltype(result)>) {
        if(operation==NativeCreateWindow) h.diagnosticNative.store(reinterpret_cast<HWND>(result));
    }
    QueryPerformanceCounter(&counter); row.returnQpc=uint64_t(counter.QuadPart);
    row.returnSeconds=double(row.returnQpc)/double(row.qpcFrequency);
    if constexpr(std::is_pointer_v<decltype(result)>) row.result=result ? 1u : 0u;
    else row.result=uint32_t(result);
    row.win32Error=immediateError;
    row.flagsAfter=h.flags.load(); row.submittedAfter=h.submittedCount.load();
    row.displayedAfter=h.displayedCount.load(); row.statisticsHRESULT=h.statisticsResult.load();
    if(operation==NativeCompositionCommit && SUCCEEDED(HRESULT(row.result))) ++h.compositionCommitRevision;
    row.commitAfter=h.compositionCommitRevision.load();
    if(operation==NativeFrameSlotWait || operation==NativeDestroyWait) row.waitStateAfter=nativeWaitState(row.result);
    if(operation==NativeAcquireSharedMutex) row.keyedMutexState=row.result==S_OK ? 1u : 2u;
    if(operation==NativeReleaseSharedMutex) row.keyedMutexState=SUCCEEDED(HRESULT(row.result)) ? 3u : 4u;
    nativeWindowState(h,h.diagnosticNative.load(),row.nativeAfter); nativeWindowState(h,live,row.liveAfter);
    LARGE_INTEGER diagnosticEnd{}; QueryPerformanceCounter(&diagnosticEnd);
    const uint64_t metadataTicks=(row.startQpc-uint64_t(diagnosticBegin.QuadPart))+
        (uint64_t(diagnosticEnd.QuadPart)-row.returnQpc);
    row.diagnosticOverheadUs=uint32_t(std::min(uint64_t(UINT32_MAX),metadataTicks*1000000/row.qpcFrequency));
    nativeStoreCall(h,row);
    if(operation==NativeCreateWindow && h.creationObservation) {
        std::lock_guard<std::mutex> lock(h.creationMutex);
        auto& creation=*h.creationObservation;
        creation.createBeginQpc=row.startQpc; creation.createReturnQpc=row.returnQpc;
        creation.createResult=row.result; creation.createWin32Error=immediateError;
        creation.creationAccepted=row.result!=0;
    }
    SetLastError(immediateError); // Preserve existing caller failure checks too.
    return result;
}
void creationSnapshot(Host& h,uint32_t phase) {
    if(!h.creationObservation) return;
    NativeCreationRow row; row.phase=phase; row.flags=h.flags.load();
    LARGE_INTEGER counter{}; QueryPerformanceCounter(&counter);
    row.qpc=uint64_t(counter.QuadPart); row.seconds=double(row.qpc)/double(h.nativeQpcFrequency);
    const HWND native=h.diagnosticNative.load(),live=h.diagnosticLive.load();
    nativeWindowState(h,native,row.native); nativeWindowState(h,live,row.live);
    const auto relation=[](HWND window,int which)->uint64_t {
        return window && IsWindow(window) ? uint64_t(uintptr_t(GetWindow(window,UINT(which)))) : 0;
    };
    const auto parent=[](HWND window)->uint64_t {
        return window && IsWindow(window) ? uint64_t(uintptr_t(GetParent(window))) : 0;
    };
    const auto monitor=[](HWND window)->uint64_t {
        return window && IsWindow(window) ? uint64_t(uintptr_t(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST))) : 0;
    };
    row.nativeParent=parent(native); row.nativePrevious=relation(native,GW_HWNDPREV);
    row.nativeNext=relation(native,GW_HWNDNEXT); row.nativeMonitor=monitor(native);
    row.liveParent=parent(live); row.livePrevious=relation(live,GW_HWNDPREV);
    row.liveNext=relation(live,GW_HWNDNEXT); row.liveMonitor=monitor(live);
    std::lock_guard<std::mutex> lock(h.creationMutex);
    auto& observation=*h.creationObservation;
    if(observation.count<12) observation.rows[observation.count++]=row;
}
void validateHiddenCreationBand(Host& h) {
    if(!h.sourceCreationBandKnown) return;
    if(!nativeInvoke(h,NativeValidateCreatedHost,0,0,0,false,[&] {
            DWORD process=0; const DWORD thread=GetWindowThreadProcessId(h.hwnd,&process);
            const LONG_PTR style=GetWindowLongPtrW(h.hwnd,GWL_STYLE);
            const LONG_PTR exstyle=GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE);
            return IsWindow(h.hwnd) && !IsWindowVisible(h.hwnd) && !GetParent(h.hwnd) &&
                !GetWindow(h.hwnd,GW_OWNER) && process==GetCurrentProcessId() &&
                thread==GetCurrentThreadId() && !(style&(WS_CHILD|WS_VISIBLE)) &&
                (exstyle&(WS_EX_NOACTIVATE|WS_EX_TRANSPARENT))==(WS_EX_NOACTIVATE|WS_EX_TRANSPARENT) &&
                sourceVisibilityBandMatches(exstyle,h.sourceCreationTopmost); }))
        throw std::runtime_error("Hidden preparation did not preserve the created source band/visibility/authority");
}
void prepareNativeTrace(Host& h) {
    h.nativeCallTrace=std::make_unique<NativeCallTrace>(); h.nativeCallTrace->enabled=1;
    LARGE_INTEGER frequency{}; QueryPerformanceFrequency(&frequency);
    h.nativeQpcFrequency=uint64_t(frequency.QuadPart);
    h.diagnosticDwm=LoadLibraryW(L"dwmapi.dll");
    if(h.diagnosticDwm)
        h.diagnosticDwmAttribute=reinterpret_cast<Host::DwmAttribute>(GetProcAddress(h.diagnosticDwm,"DwmGetWindowAttribute"));
    h.nativeCallTraceEnabled.store(true);
}
void populateNativeTraceResources(Host& h) {
    h.diagnosticNative.store(h.hwnd);
    h.adapterIdentity=++nextResourceIdentity; h.deviceIdentity=++nextResourceIdentity;
    h.swapchainIdentity=++nextResourceIdentity; h.waitIdentity=++nextResourceIdentity;
    ComPtr<IDXGIDevice> dxgi; check(h.gpu.As(&dxgi),"Diagnostic device adapter query");
    ComPtr<IDXGIAdapter> adapter; check(dxgi->GetAdapter(&adapter),"Diagnostic adapter identity");
    DXGI_ADAPTER_DESC desc{}; check(adapter->GetDesc(&desc),"Diagnostic adapter LUID");
    int64_t luid=0; memcpy(&luid,&desc.AdapterLuid,sizeof(desc.AdapterLuid)); h.adapterLuid.store(luid);
    h.swapchain.As(&h.diagnosticSwapchain);
}
uint32_t windowOwnerRelation(HWND window,HWND live,HWND native) {
    const HWND owner=GetWindow(window,GW_OWNER);
    if(!owner) return 0;
    if(owner==live) return 1;
    if(owner==native) return 2;
    DWORD process=0;
    if(!GetWindowThreadProcessId(owner,&process)) return 5;
    return process==GetCurrentProcessId() ? 3u : 4u;
}
uint32_t windowInsertBand(HWND after,HWND live) {
    if(after==HWND_TOP) return 0;
    if(after==HWND_TOPMOST) return 1;
    if(after==HWND_NOTOPMOST) return 2;
    if(after==HWND_BOTTOM) return 3;
    if(after==live && live) return 4;
    DWORD process=0;
    if(!GetWindowThreadProcessId(after,&process)) return 7;
    return process==GetCurrentProcessId() ? 5u : 6u;
}
void sourceTransferEntry(Host& h,HWND live) {
    if(h.nativeCallTraceEnabled.load()) {
        h.diagnosticLive.store(live);
        h.liveGuiThreadId.store(GetWindowThreadProcessId(live,nullptr));
    }
    if(!h.sourceTransferTraceEnabled) return;
    SourceTransferObservation row;
    row.hostGeneration=h.generation; row.stage=1; row.traceEnabled=1;
    row.entrySeconds=nowSeconds();
    row.currentThreadId=GetCurrentThreadId(); row.currentProcessId=GetCurrentProcessId();
    DWORD liveProcess=0,nativeProcess=0;
    row.liveThreadId=GetWindowThreadProcessId(live,&liveProcess);
    row.nativeThreadId=GetWindowThreadProcessId(h.hwnd,&nativeProcess);
    row.liveProcessId=liveProcess; row.nativeProcessId=nativeProcess;
    row.sameParent=GetParent(live)==GetParent(h.hwnd);
    row.sameProcess=row.liveProcessId==row.currentProcessId && row.nativeProcessId==row.currentProcessId;
    row.liveThreadOwned=row.liveThreadId==row.currentThreadId;
    row.nativeThreadOwned=row.nativeThreadId==row.currentThreadId;
    row.liveForegroundEntry=GetForegroundWindow()==live;
    row.liveOwnerRelation=windowOwnerRelation(live,live,h.hwnd);
    row.nativeOwnerRelation=windowOwnerRelation(h.hwnd,live,h.hwnd);
    row.liveStyleEntry=uint32_t(GetWindowLongPtrW(live,GWL_EXSTYLE));
    row.nativeStyleEntry=uint32_t(GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE));
    row.liveVisibleEntry=IsWindowVisible(live)!=FALSE;
    row.nativeVisibleEntry=IsWindowVisible(h.hwnd)!=FALSE;
    {
        std::lock_guard<std::mutex> lock(h.sourceTransferMutex);
        row.sequence=h.sourceTransferObservation.sequence+1;
        h.sourceTransferObservation=row; h.sourceWindowPosTrace=SourceWindowPosTrace{};
    }
    h.sourceTransferLive.store(live); h.sourceTransferTraceActive.store(true);
}
template<class F> void sourceTransferObserve(Host& h,F writer) {
    if(!h.sourceTransferTraceEnabled) return;
    std::lock_guard<std::mutex> lock(h.sourceTransferMutex);
    writer(h.sourceTransferObservation); ++h.sourceTransferObservation.sequence;
}
void applyOwnedSourceBand(Host& h,bool expectedVisible) {
    DWORD process=0;
    const DWORD thread=GetWindowThreadProcessId(h.hwnd,&process);
    const bool owned=thread==GetCurrentThreadId() && process==GetCurrentProcessId();
    if(!sourceBandOperationAllowed(h.flags.load(),h.sourceBandKnown.load(),
            IsWindowVisible(h.hwnd)!=FALSE,expectedVisible,owned))
        throw std::runtime_error("Source band operation requires its native owner thread and stopped prepared visibility state");
    const bool sourceTopmost=h.sourceTopmost.load();
    if(h.sourceCreationBandKnown && (sourceTopmost!=h.sourceCreationTopmost ||
            !sourceVisibilityBandMatches(GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE),sourceTopmost)))
        throw std::runtime_error("Created source band differs from the currently owned live source");
    if(!nativeInvoke(h,NativeSourceBandPosition,0,0,0,true,[&] {
            const UINT flags=SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|
                (h.sourceCreationBandKnown && !expectedVisible ? SWP_NOZORDER : 0);
            // Once visible, raise within the already verified group. HWND_TOP
            // retains a created topmost window's group; it is not promotion.
            const HWND insertion=h.sourceCreationBandKnown && expectedVisible ?
                HWND_TOP : sourceVisibilityBand(sourceTopmost);
            return SetWindowPos(h.hwnd,insertion,0,0,0,0,flags); }))
        throw std::runtime_error("Stopped source host z-order unavailable");
    if(!nativeInvoke(h,NativeValidateSourceBand,0,0,0,false,[&] {
            return sourceVisibilityBandMatches(GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE),sourceTopmost) &&
                (IsWindowVisible(h.hwnd)!=FALSE)==expectedVisible; }))
        throw std::runtime_error("Stopped source band operation did not preserve the owned live window band and visibility");
    if(expectedVisible) creationSnapshot(h,10);
}
void sourceTransferExit(Host& h,HWND live,uint32_t stage,DWORD error=0) {
    if(!h.sourceTransferTraceEnabled) return;
    const double ended=nowSeconds();
    const auto liveStyle=uint32_t(GetWindowLongPtrW(live,GWL_EXSTYLE));
    const auto nativeStyle=uint32_t(GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE));
    const bool liveVisible=IsWindowVisible(live)!=FALSE,nativeVisible=IsWindowVisible(h.hwnd)!=FALSE;
    const bool foreground=GetForegroundWindow()==live;
    sourceTransferObserve(h,[&](SourceTransferObservation& row) {
        row.stage=stage; row.accepted=stage==9; row.win32Error=error;
        row.liveStyleExit=liveStyle; row.nativeStyleExit=nativeStyle;
        row.liveVisibleExit=liveVisible; row.nativeVisibleExit=nativeVisible;
        row.liveForegroundExit=foreground; row.exitSeconds=ended;
    });
}
void sourceWindowPosObserve(Host& h,UINT message,const WINDOWPOS& before,const WINDOWPOS& after,
                            uint32_t styleBefore) {
    SourceWindowPosRow row;
    row.timeSeconds=nowSeconds(); row.message=message;
    const HWND live=h.sourceTransferLive.load();
    row.insertAfterBandBefore=windowInsertBand(before.hwndInsertAfter,live);
    row.insertAfterBandAfter=windowInsertBand(after.hwndInsertAfter,live);
    row.flagsBefore=before.flags; row.flagsAfter=after.flags; row.styleBefore=styleBefore;
    row.styleAfter=uint32_t(GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE));
    row.currentThreadId=GetCurrentThreadId(); row.visibleAfter=IsWindowVisible(h.hwnd)!=FALSE;
    std::lock_guard<std::mutex> lock(h.sourceTransferMutex);
    row.phase=h.sourceTransferObservation.stage;
    row.expectedTopmost=h.sourceTransferObservation.expectedTopmost;
    auto& trace=h.sourceWindowPosTrace; row.sequence=++trace.totalRows;
    // Retain the first causally relevant rows; cleanup never overwrites them.
    if(trace.count<16) trace.rows[trace.count++]=row;
}
const char* shader=R"HLSL(
Texture2D oldFrame : register(t0);
Texture2D newFrame : register(t1);
SamplerState linearClamp : register(s0);
cbuffer Motion : register(b0) {
    float4 currentRect,sourceRect,targetRect,sizes,motion,witnessRect,witnessColor;
};
float4 vertex(uint id:SV_VertexID):SV_Position {
    float2 xy=float2((id<<1)&2,id&2);
    return float4(xy*float2(2,-2)+float2(-1,1),0,1);
}
float2 mapped(float2 local,float2 imageSize) {
    float2 geometrySize=currentRect.zw;
    float header=min(motion.x,min(imageSize.y,geometrySize.y)-1);
    float2 pixel;
    if(local.y<header) {
        float fixedRight=min(motion.y,min(imageSize.x,geometrySize.x));
        pixel=local;
        // Extend only the empty left-header edge through a growing gap.
        // The source's right-anchored controls must not appear a second time
        // at their old x coordinate before the anchored control branch.
        pixel.x=min(pixel.x,max(0.5,imageSize.x-fixedRight-0.5));
        if(local.x>=geometrySize.x-fixedRight)
            pixel.x=imageSize.x-(geometrySize.x-local.x);
    } else {
        pixel.x=local.x*imageSize.x/geometrySize.x;
        pixel.y=header+(local.y-header)*(imageSize.y-header)/(geometrySize.y-header);
    }
    return pixel/imageSize;
}
float4 pixel(float4 pos:SV_Position):SV_Target {
    if(witnessRect.z>0&&all(pos.xy>=witnessRect.xy)&&all(pos.xy<witnessRect.xy+witnessRect.zw))
        return witnessColor;
    float2 local=pos.xy-currentRect.xy;
    if(any(local<0)||any(local>=currentRect.zw)) return 0;
    // Endpoints use integer physical texels: no filtering, opacity stacking,
    // or transparent source corners left underneath the target.
    if(motion.z<=0) return oldFrame.Load(int3(int2(pos.xy-sourceRect.xy),0));
    if(motion.z>=1&&motion.w>=1)
        return newFrame.Load(int3(int2(pos.xy-targetRect.xy),0));
    float4 oldPixel=oldFrame.SampleLevel(linearClamp,mapped(local,sizes.xy),0);
    float4 newPixel=newFrame.SampleLevel(linearClamp,mapped(local,sizes.zw),0);
    return lerp(oldPixel,newPixel,motion.w);
}
)HLSL";
void statistics(Host& h) {
    DXGI_FRAME_STATISTICS stats{};
    const HRESULT hr=nativeInvoke(h,NativeFrameStatistics,0,0,0,false,[&] { return h.swapchain->GetFrameStatistics(&stats); });
    h.statisticsResult=unsigned(hr);
    if(SUCCEEDED(hr)) {
        h.displayedCount=stats.PresentCount;
        if(h.endpointSubmitted && h.endpointCount && stats.PresentCount>=h.endpointCount)
            h.flags.fetch_or(32); // DXGI statistics, still independently checked on desktop.
    }
}
void render(Host& h,bool initial=false) {
    if(h.endpointSubmitted) {
        statistics(h);
        if((h.flags.load()&32)||nowSeconds()-h.startSeconds.load()>h.duration.load()+0.25)
            KillTimer(h.hwnd,1);
        return;
    }
    const DWORD slotResult=nativeInvoke(h,NativeFrameSlotWait,100,0,0,true,[&] {
        return WaitForSingleObjectEx(h.frameReady,100,FALSE); });
    if(slotResult!=WAIT_OBJECT_0)
        throw std::runtime_error("Native DXGI presentation slot missed bounded 100 ms readiness");
    // Query time only after the previous frame's presentation slot is ready.
    // A delayed slot skips stale samples rather than changing the trajectory.
    const double elapsed=initial ? 0 : nowSeconds()-h.startSeconds.load();
    const double duration=h.duration.load();
    const double p=initial ? 0 : flow(elapsed/duration);
    double content=initial ? 0 : flow((elapsed-h.blendStart)/(duration-h.blendStart));
    if(!h.destination.view) {
        content=0;
        if(!initial && elapsed>=h.blendStart && !(h.flags.load()&16))
            h.fail("Target readiness missed fixed content-transfer deadline; trajectory continues unchanged");
    }
    Constants c{};
    c.currentRect[0]=float(h.sourceX+(h.targetX-h.sourceX)*p);
    c.currentRect[1]=float(h.sourceY+(h.targetY-h.sourceY)*p);
    c.currentRect[2]=float(h.sourceW+(h.targetW-h.sourceW)*p);
    c.currentRect[3]=float(h.sourceH+(h.targetH-h.sourceH)*p);
    const float sourceRect[]={h.sourceX,h.sourceY,h.sourceW,h.sourceH};
    const float targetRect[]={h.targetX,h.targetY,h.targetW,h.targetH};
    memcpy(c.sourceRect,sourceRect,sizeof(sourceRect)); memcpy(c.targetRect,targetRect,sizeof(targetRect));
    c.sizes[0]=float(h.source.width); c.sizes[1]=float(h.source.height);
    c.sizes[2]=float(h.destination.view ? h.destination.width : h.source.width);
    c.sizes[3]=float(h.destination.view ? h.destination.height : h.source.height);
    c.motion[0]=h.header; c.motion[1]=h.rightWidth; c.motion[2]=float(p); c.motion[3]=float(content);
    if(h.witnessRevision) {
        c.witnessRect[0]=h.witnessX; c.witnessRect[1]=h.witnessY;
        c.witnessRect[2]=8; c.witnessRect[3]=8;
        c.witnessColor[0]=float(h.witnessRevision&255)/255;
        c.witnessColor[1]=float((h.witnessRevision>>8)&255)/255;
        c.witnessColor[2]=float(initial ? 1 : (p>=1&&content>=1 ? 3 : 2))/255;
        c.witnessColor[3]=1;
    }
    h.context->UpdateSubresource(h.constants.Get(),0,nullptr,&c,0,0);
    ComPtr<ID3D11Texture2D> buffer;
    check(nativeInvoke(h,NativeGetBuffer,0,0,0,false,[&] {
        return h.swapchain->GetBuffer(0,__uuidof(ID3D11Texture2D),&buffer); }),"Swapchain.GetBuffer");
    ComPtr<ID3D11RenderTargetView> view;
    check(nativeInvoke(h,NativeCreateRenderTarget,0,0,0,false,[&] {
        return h.gpu->CreateRenderTargetView(buffer.Get(),nullptr,&view); }),"Create presentation RTV");
    const float clear[]={0,0,0,0}; h.context->ClearRenderTargetView(view.Get(),clear);
    ID3D11RenderTargetView* renderTarget=view.Get(); h.context->OMSetRenderTargets(1,&renderTarget,nullptr);
    D3D11_VIEWPORT viewport{0,0,float(h.hostWidth),float(h.hostHeight),0,1};
    h.context->RSSetViewports(1,&viewport);
    h.context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    h.context->VSSetShader(h.vertexShader.Get(),nullptr,0); h.context->PSSetShader(h.pixelShader.Get(),nullptr,0);
    ID3D11Buffer* constants=h.constants.Get(); h.context->PSSetConstantBuffers(0,1,&constants);
    ID3D11SamplerState* sampler=h.sampler.Get(); h.context->PSSetSamplers(0,1,&sampler);
    ID3D11ShaderResourceView* inputs[]={h.source.view.Get(),h.destination.view ? h.destination.view.Get() : h.source.view.Get()};
    h.context->PSSetShaderResources(0,2,inputs); h.context->Draw(3,0);
    ID3D11ShaderResourceView* empty[]={nullptr,nullptr}; h.context->PSSetShaderResources(0,2,empty);
    h.context->OMSetRenderTargets(0,nullptr,nullptr);
    const bool copyStoppedProbe=h.probeSnapshotEnabled &&
        (initial || (elapsed>=duration && p==1. && content==1. && h.destination.view));
    const double snapshotQueued=copyStoppedProbe ? nowSeconds() : 0;
    if(copyStoppedProbe) h.context->CopyResource(h.lastSubmittedTexture.Get(),buffer.Get());
    const double presentBegin=nowSeconds();
    const HRESULT presentResult=nativeInvoke(h,NativePresent,0,0,0,false,[&] { return h.swapchain->Present(1,0); });
    const double presentReturn=nowSeconds();
    UINT submitted=0;
    if(SUCCEEDED(nativeInvoke(h,NativeLastPresentCount,0,0,0,false,[&] {
            return h.swapchain->GetLastPresentCount(&submitted); }))) h.submittedCount=submitted;
    h.observe([&](Observation& observation) {
        observation.lastPresentBeginSeconds=presentBegin;
        observation.lastPresentReturnSeconds=presentReturn;
        observation.lastPresentHRESULT=uint32_t(presentResult);
        observation.submittedPresentId=submitted;
        observation.lastFrameElapsedSeconds=elapsed;
        observation.lastFrameMotion=p; observation.lastFrameContent=content;
        memcpy(observation.currentRect,c.currentRect,sizeof(c.currentRect));
        auto& row=h.presentRows[h.totalPresentRows%128];
        row.sequence=++h.totalPresentRows; row.submittedPresentId=submitted;
        row.presentHRESULT=uint32_t(presentResult);
        row.presentBeginSeconds=presentBegin; row.presentReturnSeconds=presentReturn;
        row.elapsedSeconds=elapsed; row.motion=p; row.content=content;
        memcpy(row.currentRect,c.currentRect,sizeof(c.currentRect));
        if(copyStoppedProbe && SUCCEEDED(presentResult)) {
            auto& identity=h.probeIdentity;
            identity.hostGeneration=h.generation; identity.snapshotRevision=++h.snapshotRevision;
            identity.sourceFrameRevision=h.source.frameRevision;
            identity.targetFrameRevision=h.destination.frameRevision;
            identity.submittedPresentId=submitted; identity.phase=initial ? 1u : 3u;
            identity.witnessRevision=h.witnessRevision;
            identity.snapshotQueuedSeconds=snapshotQueued;
            identity.presentBeginSeconds=presentBegin; identity.presentReturnSeconds=presentReturn;
            identity.motion=p; identity.content=content;
            identity.hostLeft=observation.hostLeft; identity.hostTop=observation.hostTop;
            identity.hostWidth=h.hostWidth; identity.hostHeight=h.hostHeight;
            identity.sourceLeft=int(h.sourceX); identity.sourceTop=int(h.sourceY);
            identity.sourceWidth=int(h.source.width); identity.sourceHeight=int(h.source.height);
            identity.targetLeft=int(h.targetX); identity.targetTop=int(h.targetY);
            identity.targetWidth=int(h.destination.width); identity.targetHeight=int(h.destination.height);
            identity.sourceFormat=observation.sourceFormat; identity.targetFormat=observation.targetFormat;
            identity.snapshotFormat=DXGI_FORMAT_B8G8R8A8_UNORM;
            identity.snapshotWidth=unsigned(h.hostWidth); identity.snapshotHeight=unsigned(h.hostHeight);
            identity.snapshotEnabled=1;
            identity.sourceResourceIdentity=h.source.resourceIdentity;
            identity.targetResourceIdentity=h.destination.resourceIdentity;
            identity.snapshotResourceIdentity=h.snapshotResourceIdentity;
        }
    });
    check(presentResult,"Present GPU-only premultiplied frame");
    if(!initial && elapsed>=duration) {
        h.endpointSubmitted=true; h.endpointCount=submitted;
        h.observe([&](Observation& observation) {
            observation.endpointPresentReturnSeconds=presentReturn;
        });
        if(h.destination.view && !(h.flags.load()&16)) h.flags.fetch_or(4);
    }
    statistics(h);
}
LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM w,LPARAM l) {
    auto host=reinterpret_cast<Host*>(GetWindowLongPtrW(hwnd,GWLP_USERDATA));
    if(message==WM_NCCREATE) {
        host=static_cast<Host*>(reinterpret_cast<CREATESTRUCTW*>(l)->lpCreateParams);
        SetWindowLongPtrW(hwnd,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(host));
    }
    if(message==WM_NCHITTEST) return HTTRANSPARENT;
    if(message==WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    if(message==WM_ERASEBKGND) return 1;
    if(message==WM_PAINT) { PAINTSTRUCT paint; BeginPaint(hwnd,&paint); EndPaint(hwnd,&paint); return 0; }
    if(message==WM_APP+1 && host) {
        std::deque<std::function<void()>> tasks;
        { std::lock_guard<std::mutex> lock(host->queueMutex); tasks.swap(host->queue); }
        for(auto& task:tasks) task(); return 0;
    }
    if(message==WM_TIMER && w==1 && host) {
        try { render(*host); }
        catch(const std::exception& ex) { host->fail(ex.what()); KillTimer(hwnd,1); }
        return 0;
    }
    if(message==WM_APP+2) {
        KillTimer(hwnd,1);
        if(host) nativeInvoke(*host,NativeDestroyWindow,0,0,0,true,[&] { return DestroyWindow(hwnd); });
        else DestroyWindow(hwnd);
        PostQuitMessage(0); return 0;
    }
    if(host && host->sourceTransferTraceEnabled && host->sourceTransferTraceActive.load() &&
       !(host->flags.load()&2) && l && (message==WM_WINDOWPOSCHANGING || message==WM_WINDOWPOSCHANGED)) {
        const auto position=reinterpret_cast<WINDOWPOS*>(l);
        const WINDOWPOS before=*position;
        const auto styleBefore=uint32_t(GetWindowLongPtrW(hwnd,GWL_EXSTYLE));
        const LRESULT result=DefWindowProcW(hwnd,message,w,l);
        sourceWindowPosObserve(*host,message,before,*position,styleBefore);
        return result;
    }
    return DefWindowProcW(hwnd,message,w,l);
}
void initialize(Host& h,IDXGIAdapter* adapter,int left,int top,int width,int height) {
    h.workerThreadId.store(GetCurrentThreadId());
    check(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED),"CoInitializeEx"); h.apartment=true;
    WNDCLASSW wc{}; wc.lpfnWndProc=procedure; wc.hInstance=GetModuleHandleW(nullptr);
    wc.lpszClassName=L"CSPMExperimentalDirectCompositionShader";
    if(!RegisterClassW(&wc) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)
        throw std::runtime_error("RegisterClassW failed");
    const DWORD hostStyle=WS_EX_NOREDIRECTIONBITMAP|WS_EX_TOOLWINDOW|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE|
        (h.sourceCreationBandKnown && h.sourceCreationTopmost ? WS_EX_TOPMOST : 0);
    if(h.creationObservation) {
        std::lock_guard<std::mutex> lock(h.creationMutex);
        h.creationObservation->requestedStyle=WS_POPUP;
        h.creationObservation->requestedExStyle=hostStyle;
    }
    h.hwnd=nativeInvoke(h,NativeCreateWindow,0,0,0,true,[&] {
        return CreateWindowExW(hostStyle,wc.lpszClassName,L"CSPM experimental native composition",WS_POPUP,
            left,top,width,height,nullptr,nullptr,wc.hInstance,&h); });
    const DWORD creationError=GetLastError();
    creationSnapshot(h,2);
    if(!h.hwnd) throw std::runtime_error("CreateWindowExW failed");
    if((h.creationObservation || h.sourceCreationBandKnown) && !nativeInvoke(h,NativeValidateCreatedHost,0,0,0,false,[&] {
            DWORD process=0; const DWORD thread=GetWindowThreadProcessId(h.hwnd,&process);
            const LONG_PTR style=GetWindowLongPtrW(h.hwnd,GWL_STYLE);
            const LONG_PTR exstyle=GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE);
            return !IsWindowVisible(h.hwnd) && !GetParent(h.hwnd) && !GetWindow(h.hwnd,GW_OWNER) &&
                process==GetCurrentProcessId() && thread==GetCurrentThreadId() &&
                !(style&(WS_CHILD|WS_VISIBLE)) && (style&WS_POPUP) &&
                (exstyle&(WS_EX_NOREDIRECTIONBITMAP|WS_EX_TOOLWINDOW|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE))==
                    (WS_EX_NOREDIRECTIONBITMAP|WS_EX_TOOLWINDOW|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE) &&
                sourceVisibilityBandMatches(exstyle,h.sourceCreationBandKnown && h.sourceCreationTopmost); }))
        throw std::runtime_error("Created hidden host did not preserve the requested band/styles/owner-thread contract");
    SetLastError(creationError);
    h.hostWidth=width; h.hostHeight=height;
    h.observe([&](Observation& observation) {
        observation.hostLeft=left; observation.hostTop=top;
        observation.hostWidth=width; observation.hostHeight=height;
    });
    D3D_FEATURE_LEVEL feature;
    check(D3D11CreateDevice(adapter,D3D_DRIVER_TYPE_UNKNOWN,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        nullptr,0,D3D11_SDK_VERSION,&h.gpu,&feature,&h.context),"D3D11CreateDevice(same adapter)");
    ComPtr<IDXGIDevice> dxgi; check(h.gpu.As(&dxgi),"IDXGIDevice");
    check(DCompositionCreateDevice(dxgi.Get(),__uuidof(IDCompositionDevice),&h.compositor),"DCompositionCreateDevice");
    check(h.compositor->CreateTargetForHwnd(h.hwnd,TRUE,&h.target),"CreateTargetForHwnd");
    check(h.compositor->CreateVisual(&h.root),"CreateVisual(root)");
    check(h.target->SetRoot(h.root.Get()),"SetRoot");
    ComPtr<IDXGIFactory2> factory; check(adapter->GetParent(__uuidof(IDXGIFactory2),&factory),"GPU factory");
    DXGI_SWAP_CHAIN_DESC1 desc{}; desc.Width=UINT(width); desc.Height=UINT(height);
    desc.Format=DXGI_FORMAT_B8G8R8A8_UNORM; desc.SampleDesc.Count=1;
    desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT; desc.BufferCount=2;
    desc.Scaling=DXGI_SCALING_STRETCH; desc.SwapEffect=DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL;
    desc.AlphaMode=DXGI_ALPHA_MODE_PREMULTIPLIED;
    desc.Flags=DXGI_SWAP_CHAIN_FLAG_FRAME_LATENCY_WAITABLE_OBJECT;
    check(factory->CreateSwapChainForComposition(h.gpu.Get(),&desc,nullptr,&h.swapchain),"CreateSwapChainForComposition");
    ComPtr<IDXGISwapChain2> pacing; check(h.swapchain.As(&pacing),"IDXGISwapChain2 pacing capability");
    check(pacing->SetMaximumFrameLatency(1),"SetMaximumFrameLatency(1)");
    h.frameReady=pacing->GetFrameLatencyWaitableObject();
    if(!h.frameReady) throw std::runtime_error("DXGI frame-latency wait handle unavailable");
    check(h.root->SetContent(h.swapchain.Get()),"SetContent(GPU swapchain)");
    auto compile=[](const char* entry,const char* profile) {
        ComPtr<ID3DBlob> code,errors;
        HRESULT hr=D3DCompile(shader,strlen(shader),"CSPM clean-room GPU presentation",nullptr,nullptr,
            entry,profile,D3DCOMPILE_ENABLE_STRICTNESS,0,&code,&errors);
        if(FAILED(hr) && errors) throw std::runtime_error(std::string("HLSL compile: ")+static_cast<char*>(errors->GetBufferPointer()));
        check(hr,"D3DCompile"); return code;
    };
    auto vs=compile("vertex","vs_5_0"),ps=compile("pixel","ps_5_0");
    check(h.gpu->CreateVertexShader(vs->GetBufferPointer(),vs->GetBufferSize(),nullptr,&h.vertexShader),"CreateVertexShader");
    check(h.gpu->CreatePixelShader(ps->GetBufferPointer(),ps->GetBufferSize(),nullptr,&h.pixelShader),"CreatePixelShader");
    D3D11_BUFFER_DESC constants{}; constants.ByteWidth=sizeof(Constants);
    constants.Usage=D3D11_USAGE_DEFAULT; constants.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
    check(h.gpu->CreateBuffer(&constants,nullptr,&h.constants),"Create motion constant buffer");
    D3D11_SAMPLER_DESC sampler{}; sampler.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sampler.AddressU=sampler.AddressV=sampler.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;
    sampler.MaxLOD=D3D11_FLOAT32_MAX;
    check(h.gpu->CreateSamplerState(&sampler,&h.sampler),"Create linear sampler");
    if(h.nativeCallTraceEnabled.load()) populateNativeTraceResources(h);
}
void releaseResources(Host& h) {
    if(h.context) { h.context->ClearState(); h.context->Flush(); }
    h.root.Reset(); h.target.Reset(); h.source=Pixels{}; h.destination=Pixels{};
    h.lastSubmittedTexture.Reset();
    h.vertexShader.Reset(); h.pixelShader.Reset(); h.constants.Reset(); h.sampler.Reset();
    if(h.frameReady) {
        nativeInvoke(h,NativeCloseFrameHandle,0,0,0,true,[&] { return CloseHandle(h.frameReady); });
        h.frameReady=nullptr;
    }
    h.swapchain.Reset(); h.compositor.Reset(); h.context.Reset(); h.gpu.Reset();
    h.diagnosticSwapchain.Reset();
    if(h.hwnd && IsWindow(h.hwnd))
        nativeInvoke(h,NativeDestroyWindow,0,0,0,true,[&] { return DestroyWindow(h.hwnd); });
    h.hwnd=nullptr;
    if(h.apartment) { CoUninitialize(); h.apartment=false; }
    if(h.creationObservation) {
        creationSnapshot(h,9);
        std::lock_guard<std::mutex> lock(h.creationMutex);
        h.creationObservation->cleanupCompleted=1;
    }
}
Pixels copyPixels(Host& h,Frame& frame) {
    ComPtr<ID3D11Texture2D> opened;
    check(nativeInvoke(h,NativeOpenSharedResource,0,frame.revision,0,false,[&] {
        return h.gpu->OpenSharedResource(frame.sharedHandle,__uuidof(ID3D11Texture2D),&opened); }),"OpenSharedResource");
    D3D11_TEXTURE2D_DESC openedDesc{}; opened->GetDesc(&openedDesc);
    if(openedDesc.Width!=frame.desc.Width || openedDesc.Height!=frame.desc.Height ||
       openedDesc.Format!=frame.desc.Format || openedDesc.MipLevels!=1 || openedDesc.ArraySize!=1 ||
       openedDesc.SampleDesc.Count!=1)
        throw std::runtime_error("Shared GPU frame dimensions/format mismatch");
    ComPtr<IDXGIKeyedMutex> mutex; check(opened.As(&mutex),"Shared texture keyed mutex");
    if(nativeInvoke(h,NativeAcquireSharedMutex,40,frame.revision,1,false,[&] { return mutex->AcquireSync(1,40); })!=S_OK)
        throw std::runtime_error("GPU synchronization: shared texture AcquireSync missed 40 ms bound");
    Pixels pixels;
    try {
        auto desc=frame.desc; desc.Usage=D3D11_USAGE_DEFAULT; desc.CPUAccessFlags=0;
        desc.BindFlags=D3D11_BIND_SHADER_RESOURCE; desc.MiscFlags=0;
        pixels.width=desc.Width; pixels.height=desc.Height;
        pixels.frameRevision=frame.revision; pixels.resourceIdentity=++nextResourceIdentity;
        check(nativeInvoke(h,NativeCreateOwnedTexture,0,frame.revision,1,false,[&] {
            return h.gpu->CreateTexture2D(&desc,nullptr,&pixels.texture); }),"Create native owned GPU frame");
        // CopyResource copies identical extents; no atlas offset/destination
        // subrectangle remains to exceed the resource bounds.
        h.context->CopyResource(pixels.texture.Get(),opened.Get()); h.context->Flush();
        check(nativeInvoke(h,NativeCreateOwnedView,0,frame.revision,1,false,[&] {
            return h.gpu->CreateShaderResourceView(pixels.texture.Get(),nullptr,&pixels.view); }),"Create GPU frame SRV");
        check(nativeInvoke(h,NativeReleaseSharedMutex,0,frame.revision,1,false,[&] {
            return mutex->ReleaseSync(1); }),"Shared texture ReleaseSync(immutable)");
    } catch(...) { nativeInvoke(h,NativeReleaseSharedMutex,0,frame.revision,1,false,[&] {
        return mutex->ReleaseSync(1); }); throw; }
    return pixels;
}
void validateRect(const Host& h,float x,float y,float width,float height) {
    if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(width)||!std::isfinite(height)||
       x<0||y<0||width<=0||height<=0||double(x)+width>h.hostWidth||double(y)+height>h.hostHeight)
        throw std::runtime_error("Physical frame rectangle exceeds fixed composition host bounds");
    if(x!=std::floor(x)||y!=std::floor(y)||width!=std::floor(width)||height!=std::floor(height))
        throw std::runtime_error("Endpoint frame rectangles must use integral physical pixels");
}
void enableProbeSnapshot(Host& h) {
    if(h.flags.load() || h.source.texture || h.probeSnapshotEnabled)
        throw std::runtime_error("Submitted probe snapshot must be enabled once before source preparation");
    D3D11_TEXTURE2D_DESC desc{};
    desc.Width=UINT(h.hostWidth); desc.Height=UINT(h.hostHeight);
    desc.MipLevels=desc.ArraySize=1; desc.Format=DXGI_FORMAT_B8G8R8A8_UNORM;
    desc.SampleDesc.Count=1; desc.Usage=D3D11_USAGE_DEFAULT;
    check(h.gpu->CreateTexture2D(&desc,nullptr,&h.lastSubmittedTexture),"Create stopped submitted GPU snapshot");
    h.snapshotResourceIdentity=++nextResourceIdentity; h.probeSnapshotEnabled=true;
    h.observe([&](Observation&) {
        h.probeIdentity.hostGeneration=h.generation;
        h.probeIdentity.snapshotEnabled=1;
    });
}
void probeTexels(Host& h,ID3D11Texture2D* texture,const int* xy,unsigned count,
                 int offsetX,int offsetY,unsigned char* bgra) {
    D3D11_TEXTURE2D_DESC desc{}; texture->GetDesc(&desc);
    if(desc.Format!=DXGI_FORMAT_B8G8R8A8_UNORM && desc.Format!=DXGI_FORMAT_R8G8B8A8_UNORM)
        throw std::runtime_error("Diagnostic texel format unsupported");
    desc.Width=desc.Height=desc.MipLevels=desc.ArraySize=1;
    desc.SampleDesc.Count=1; desc.SampleDesc.Quality=0;
    desc.Usage=D3D11_USAGE_STAGING; desc.BindFlags=desc.MiscFlags=0;
    desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    ComPtr<ID3D11Texture2D> staging;
    check(h.gpu->CreateTexture2D(&desc,nullptr,&staging),"Create one-texel diagnostic staging");
    for(unsigned i=0;i<count;++i) {
        const UINT x=UINT(xy[2*i]+offsetX),y=UINT(xy[2*i+1]+offsetY);
        D3D11_BOX box{x,y,0,x+1,y+1,1};
        h.context->CopySubresourceRegion(staging.Get(),0,0,0,0,texture,0,&box);
        D3D11_MAPPED_SUBRESOURCE mapped{};
        check(h.context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped),"Map diagnostic texel only");
        const auto bytes=static_cast<const unsigned char*>(mapped.pData);
        bgra[4*i]=bytes[desc.Format==DXGI_FORMAT_R8G8B8A8_UNORM ? 2 : 0];
        bgra[4*i+1]=bytes[1];
        bgra[4*i+2]=bytes[desc.Format==DXGI_FORMAT_R8G8B8A8_UNORM ? 0 : 2];
        bgra[4*i+3]=bytes[3];
        h.context->Unmap(staging.Get(),0);
    }
}
}

EXPORT unsigned cspm_comp_abi_version() { return 1; }
EXPORT int cspm_comp_enable_native_call_trace(void* pointer) {
    if(!pointer) return 0;
    auto& h=*static_cast<Host*>(pointer);
    return h.call([&h] {
        if(h.flags.load() || h.source.texture || h.nativeCallTraceEnabled.load())
            throw std::runtime_error("Native call trace must be enabled once before source preparation");
        prepareNativeTrace(h); populateNativeTraceResources(h);
    });
}
EXPORT int cspm_comp_set_native_trace_live(void* pointer,uintptr_t livePointer) {
    if(!pointer || !livePointer) return 0;
    auto& h=*static_cast<Host*>(pointer);
    if(!h.nativeCallTraceEnabled.load() || (h.flags.load()&(2|16))) return 0;
    const HWND live=reinterpret_cast<HWND>(livePointer);
    DWORD process=0; const DWORD thread=GetWindowThreadProcessId(live,&process);
    if(!IsWindow(live) || process!=GetCurrentProcessId() || thread!=GetCurrentThreadId()) return 0;
    h.diagnosticLive.store(live); h.liveGuiThreadId.store(thread);
    return 1;
}
EXPORT int cspm_comp_native_call_trace(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(NativeCallTrace)) return 0;
    auto* result=static_cast<NativeCallTrace*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(NativeCallTrace) ||
       result->rowByteSize!=sizeof(NativeCallRow)) return 0;
    auto& h=*static_cast<Host*>(pointer);
    std::lock_guard<std::mutex> lock(h.nativeCallTraceMutex);
    if(!h.nativeCallTraceEnabled.load() || !h.nativeCallTrace) return 0;
    const auto& trace=*h.nativeCallTrace;
    result->count=trace.count; result->totalRows=trace.totalRows; result->droppedRows=trace.droppedRows;
    result->enabled=trace.enabled; result->hasFirstFailure=trace.hasFirstFailure; result->firstFailure=trace.firstFailure;
    const auto first=trace.totalRows>256 ? trace.totalRows%256 : 0;
    for(unsigned i=0;i<trace.count;++i) result->rows[i]=trace.rows[(first+i)%256];
    for(unsigned i=trace.count;i<256;++i) result->rows[i]=NativeCallRow{};
    return 1;
}
EXPORT int cspm_comp_source_creation_observation(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(NativeCreationObservation)) return 0;
    auto* result=static_cast<NativeCreationObservation*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(*result) || result->rowByteSize!=sizeof(NativeCreationRow)) return 0;
    auto& h=*static_cast<Host*>(pointer);
    std::lock_guard<std::mutex> lock(h.creationMutex);
    if(!h.creationObservation) return 0;
    *result=*h.creationObservation; return 1;
}
EXPORT int cspm_comp_enable_probe_snapshot(void* pointer) {
    if(!pointer) return 0;
    auto& h=*static_cast<Host*>(pointer);
    return h.call([&h] { enableProbeSnapshot(h); });
}
EXPORT int cspm_comp_enable_source_transfer_trace(void* pointer) {
    if(!pointer) return 0;
    auto& h=*static_cast<Host*>(pointer);
    return h.call([&h] {
        if(h.flags.load() || h.source.texture || h.sourceTransferTraceEnabled)
            throw std::runtime_error("Source transfer trace must be enabled once before source preparation");
        h.sourceTransferTraceEnabled=true;
        sourceTransferObserve(h,[&](SourceTransferObservation& row) {
            row.hostGeneration=h.generation; row.traceEnabled=1;
        });
    });
}
EXPORT int cspm_comp_source_transfer_observation(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(SourceTransferObservation)) return 0;
    auto* result=static_cast<SourceTransferObservation*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(SourceTransferObservation)) return 0;
    auto& h=*static_cast<Host*>(pointer);
    std::lock_guard<std::mutex> lock(h.sourceTransferMutex);
    memcpy(result,&h.sourceTransferObservation,sizeof(SourceTransferObservation)); return 1;
}
EXPORT int cspm_comp_source_windowpos_trace(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(SourceWindowPosTrace)) return 0;
    auto* result=static_cast<SourceWindowPosTrace*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(SourceWindowPosTrace) ||
       result->rowByteSize!=sizeof(SourceWindowPosRow)) return 0;
    auto& h=*static_cast<Host*>(pointer);
    std::lock_guard<std::mutex> lock(h.sourceTransferMutex);
    memcpy(result,&h.sourceWindowPosTrace,sizeof(SourceWindowPosTrace)); return 1;
}
EXPORT int cspm_comp_probe_identity(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(ProbeIdentity)) return 0;
    auto* result=static_cast<ProbeIdentity*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(ProbeIdentity)) return 0;
    auto& h=*static_cast<Host*>(pointer);
    std::lock_guard<std::mutex> lock(h.observationMutex);
    memcpy(result,&h.probeIdentity,sizeof(ProbeIdentity)); return 1;
}
EXPORT int cspm_gpu_frame_identity(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(FrameIdentity)) return 0;
    auto* result=static_cast<FrameIdentity*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(FrameIdentity)) return 0;
    const auto& frame=*static_cast<Frame*>(pointer);
    result->revision=frame.revision;
    result->width=frame.desc.Width; result->height=frame.desc.Height;
    result->format=uint32_t(frame.desc.Format); result->mipLevels=frame.desc.MipLevels;
    result->arraySize=frame.desc.ArraySize; result->sampleCount=frame.desc.SampleDesc.Count;
    result->subresource=0; result->orientation=1;
    return 1;
}
// Measurement-only small readback; never supplies any presentation pixels and
// never runs on a motion clock. Caller storage is not captured by queued work.
EXPORT int cspm_comp_probe_pixels(void* pointer,const int* xy,unsigned count,
                                  unsigned char* sourceBGRA,unsigned char* submittedBGRA) {
    if(!pointer || !xy || !sourceBGRA || !submittedBGRA || !count || count>64) return 0;
    auto& h=*static_cast<Host*>(pointer);
    auto samples=std::make_shared<ProbePixels>();
    memcpy(samples->xy,xy,count*2*sizeof(int));
    const int result=h.call([&h,samples,count] {
        if((h.flags.load()&(2|16)) || !h.source.texture || !h.lastSubmittedTexture ||
           !probeIdentityMatches(h.probeIdentity,1,h.observation))
            throw std::runtime_error("Diagnostic samples require a stopped source presentation");
        if(!probeCoordinatesValid(samples->xy,count,h.source.width,h.source.height,
                int(h.sourceX),int(h.sourceY),unsigned(h.hostWidth),unsigned(h.hostHeight)))
            throw std::runtime_error("Diagnostic texel coordinates exceed source or submitted extent");
        probeTexels(h,h.source.texture.Get(),samples->xy,count,0,0,samples->source);
        probeTexels(h,h.lastSubmittedTexture.Get(),samples->xy,count,
            int(h.sourceX),int(h.sourceY),samples->submitted);
    });
    if(result) {
        memcpy(sourceBGRA,samples->source,count*4);
        memcpy(submittedBGRA,samples->submitted,count*4);
    }
    return result;
}
// Additive endpoint diagnostics. The immutable target and last submitted
// allocation are sampled only after complete endpoint submission; no Present,
// visibility change, shader input or destination replacement occurs here.
EXPORT int cspm_comp_probe_endpoint_pixels(void* pointer,const int* xy,unsigned count,
                                           unsigned char* targetBGRA,unsigned char* submittedBGRA) {
    if(!pointer || !xy || !targetBGRA || !submittedBGRA || !count || count>64) return 0;
    auto& h=*static_cast<Host*>(pointer);
    auto samples=std::make_shared<ProbePixels>();
    memcpy(samples->xy,xy,count*2*sizeof(int));
    const int result=h.call([&h,samples,count] {
        if(!probeEndpointStateValid(h.flags.load(),h.endpointSubmitted,bool(h.destination.texture),
                bool(h.lastSubmittedTexture),h.observation.lastFrameMotion,h.observation.lastFrameContent) ||
           !probeIdentityMatches(h.probeIdentity,3,h.observation))
            throw std::runtime_error("Diagnostic target samples require a stopped complete endpoint");
        if(!probeCoordinatesValid(samples->xy,count,h.destination.width,h.destination.height,
                int(h.targetX),int(h.targetY),unsigned(h.hostWidth),unsigned(h.hostHeight)))
            throw std::runtime_error("Diagnostic endpoint texels exceed target or submitted extent");
        probeTexels(h,h.destination.texture.Get(),samples->xy,count,0,0,samples->source);
        probeTexels(h,h.lastSubmittedTexture.Get(),samples->xy,count,
            int(h.targetX),int(h.targetY),samples->submitted);
    });
    if(result) {
        memcpy(targetBGRA,samples->source,count*4);
        memcpy(submittedBGRA,samples->submitted,count*4);
    }
    return result;
}
// A separately exported original-source or later-live Qt frame is retained
// and copied to a diagnostic allocation on this host's GPU worker. Samples
// use that immutable frame's own extent, independently of the target extent.
// The caller verifies live-target extent equality; this never presents input.
EXPORT int cspm_comp_probe_frame_pixels(void* pointer,void* frame,const int* xy,unsigned count,
                                        unsigned char* frameBGRA) {
    if(!pointer || !frame || !xy || !frameBGRA || !count || count>64) return 0;
    auto& h=*static_cast<Host*>(pointer);
    auto retained=std::make_shared<Frame>(*static_cast<Frame*>(frame));
    auto samples=std::make_shared<ProbePixels>();
    memcpy(samples->xy,xy,count*2*sizeof(int));
    const int result=h.call([&h,retained,samples,count] {
        if(!probeEndpointStateValid(h.flags.load(),h.endpointSubmitted,bool(h.destination.texture),
                bool(h.lastSubmittedTexture),h.observation.lastFrameMotion,h.observation.lastFrameContent) ||
           !probeIdentityMatches(h.probeIdentity,3,h.observation))
            throw std::runtime_error("Diagnostic exported-frame samples require a stopped complete endpoint");
        if(!probeCoordinatesValid(samples->xy,count,retained->desc.Width,retained->desc.Height,
                0,0,retained->desc.Width,retained->desc.Height))
            throw std::runtime_error("Diagnostic exported-frame texels exceed their own immutable extent");
        const Pixels copied=copyPixels(h,*retained);
        probeTexels(h,copied.texture.Get(),samples->xy,count,0,0,samples->source);
    });
    if(result) memcpy(frameBGRA,samples->source,count*4);
    return result;
}
EXPORT void* cspm_gpu_capture(void* nativeContext,unsigned* width,unsigned* height) {
    try {
        if(!nativeContext || !width || !height) throw std::runtime_error("GPU capture arguments are null");
        auto context=static_cast<ID3D11DeviceContext*>(nativeContext);
        if(context->GetType()!=D3D11_DEVICE_CONTEXT_IMMEDIATE)
            throw std::runtime_error("Qt GPU capture requires the public immediate D3D11 context");
        ComPtr<ID3D11RenderTargetView> view; context->OMGetRenderTargets(1,&view,nullptr);
        if(!view) throw std::runtime_error("Qt main render target unavailable: OMGetRenderTargets returned null");
        ComPtr<ID3D11Resource> resource; view->GetResource(&resource);
        ComPtr<ID3D11Texture2D> texture; check(resource.As(&texture),"Qt main target Texture2D");
        auto frame=std::make_unique<Frame>(); texture->GetDesc(&frame->desc);
        if(frame->desc.SampleDesc.Count!=1 || frame->desc.MipLevels!=1 || frame->desc.ArraySize!=1)
            throw std::runtime_error("Qt target is not a single-sample, single-level 2D texture");
        if(frame->desc.Format!=DXGI_FORMAT_B8G8R8A8_UNORM && frame->desc.Format!=DXGI_FORMAT_R8G8B8A8_UNORM)
            throw std::runtime_error("Qt target format unsupported by bounded native spike");
        ComPtr<ID3D11Device> gpu; context->GetDevice(&gpu);
        auto desc=frame->desc; desc.Usage=D3D11_USAGE_DEFAULT; desc.CPUAccessFlags=0;
        desc.BindFlags=D3D11_BIND_SHADER_RESOURCE|D3D11_BIND_RENDER_TARGET;
        desc.MiscFlags=D3D11_RESOURCE_MISC_SHARED_KEYEDMUTEX;
        check(gpu->CreateTexture2D(&desc,nullptr,&frame->texture),"Create immutable shared GPU frame");
        check(frame->texture.As(&frame->mutex),"Capture keyed mutex");
        if(frame->mutex->AcquireSync(0,0)!=S_OK) throw std::runtime_error("Initial GPU frame mutex unavailable");
        context->CopyResource(frame->texture.Get(),texture.Get()); context->Flush();
        check(frame->mutex->ReleaseSync(1),"Publish immutable GPU frame");
        ComPtr<IDXGIResource> dxgi; check(frame->texture.As(&dxgi),"Capture IDXGIResource");
        check(dxgi->GetSharedHandle(&frame->sharedHandle),"GetSharedHandle");
        *width=desc.Width; *height=desc.Height; return frame.release();
    } catch(const std::exception& ex) { lastError=ex.what(); return nullptr; }
}
EXPORT void cspm_gpu_release(void* frame) { delete static_cast<Frame*>(frame); }
static void* createCompositionHost(void* frame,int left,int top,int width,int height,
                                   bool sourceBandKnown,bool sourceTopmost,HWND observedLive=nullptr,
                                   NativeCreationObservation* creationOutput=nullptr,NativeCallTrace* traceOutput=nullptr) {
    std::unique_ptr<Host> h;
    const auto copyOutputs=[&] {
        if(creationOutput && h) cspm_comp_source_creation_observation(h.get(),creationOutput,sizeof(*creationOutput));
        if(traceOutput && h) cspm_comp_native_call_trace(h.get(),traceOutput,sizeof(*traceOutput));
    };
    try {
        h=std::make_unique<Host>(); auto* host=h.get();
        h->sourceCreationBandKnown=sourceBandKnown; h->sourceCreationTopmost=sourceTopmost;
        if(creationOutput) {
            prepareNativeTrace(*h);
            h->creationObservation=std::make_unique<NativeCreationObservation>();
            h->diagnosticLive.store(observedLive);
            h->liveGuiThreadId.store(GetWindowThreadProcessId(observedLive,nullptr));
            auto& observation=*h->creationObservation;
            observation.enabled=1; observation.hostGeneration=h->generation;
            observation.strategy=sourceBandKnown ? 1u : 0u;
            observation.qpcFrequency=h->nativeQpcFrequency;
            observation.failureStage=1;
            creationSnapshot(*h,1);
        }
        if(!frame || width<=0 || height<=0) throw std::runtime_error("Invalid composition host bounds/frame");
        if(creationOutput) {
            if(!nativeInvoke(*h,NativeValidateCreationSource,0,0,0,false,[&] {
                    DWORD process=0; const DWORD thread=GetWindowThreadProcessId(observedLive,&process);
                    RECT client{};
                    return IsWindow(observedLive) && IsWindowVisible(observedLive) &&
                        process==GetCurrentProcessId() && thread==GetCurrentThreadId() &&
                        !GetParent(observedLive) && !GetWindow(observedLive,GW_OWNER) &&
                        !((GetWindowLongPtrW(observedLive,GWL_STYLE))&WS_CHILD) &&
                        GetClientRect(observedLive,&client) &&
                        uint32_t(client.right-client.left)==static_cast<Frame*>(frame)->desc.Width &&
                        uint32_t(client.bottom-client.top)==static_cast<Frame*>(frame)->desc.Height; }))
                throw std::runtime_error("Observed creation requires visible unowned GUI source with immutable frame extent");
            const bool sampled=(GetWindowLongPtrW(observedLive,GWL_EXSTYLE)&WS_EX_TOPMOST)!=0;
            h->sourceCreationTopmost=sampled;
            std::lock_guard<std::mutex> lock(h->creationMutex);
            h->creationObservation->sourceValidated=1;
            h->creationObservation->expectedTopmost=sampled;
            h->creationObservation->frameRevision=static_cast<Frame*>(frame)->revision;
            h->creationObservation->failureStage=2;
        }
        ComPtr<ID3D11Device> sourceGpu; static_cast<Frame*>(frame)->texture->GetDevice(&sourceGpu);
        ComPtr<IDXGIDevice> dxgi; check(sourceGpu.As(&dxgi),"Source IDXGIDevice");
        ComPtr<IDXGIAdapter> adapter; check(dxgi->GetAdapter(&adapter),"Source GPU adapter");
        auto initialized=std::make_shared<std::promise<void>>(); auto ready=initialized->get_future();
        h->worker=std::thread([host,adapter,left,top,width,height,initialized] {
            try {
                initialize(*host,adapter.Get(),left,top,width,height);
                if(host->creationObservation) {
                    creationSnapshot(*host,3);
                    std::lock_guard<std::mutex> lock(host->creationMutex);
                    host->creationObservation->initializationAccepted=1;
                    host->creationObservation->failureStage=0;
                }
                initialized->set_value();
            } catch(...) { releaseResources(*host); initialized->set_exception(std::current_exception()); return; }
            MSG message; while(GetMessageW(&message,nullptr,0,0)>0) { TranslateMessage(&message); DispatchMessageW(&message); }
            releaseResources(*host);
        });
        if(nativeInvoke(*h,NativeInitializationCompletion,3000,0,0,false,[&] {
                return ready.wait_for(std::chrono::seconds(3)); })!=std::future_status::ready) {
            // Initialization can be in a driver call. Retain storage/thread
            // rather than delete a live host or terminate the driver thread.
            host->fail("Native initialization exceeded 3000 ms; host retained for lifetime safety");
            if(h->creationObservation) {
                std::lock_guard<std::mutex> lock(h->creationMutex);
                h->creationObservation->hostRetained=1; h->creationObservation->failureStage=3;
            }
            copyOutputs();
            h.release(); throw std::runtime_error("Native initialization exceeded 3000 ms; host retained for lifetime safety");
        }
        try { ready.get(); } catch(...) { h->worker.join(); throw; }
        copyOutputs(); return h.release();
    } catch(const std::exception& ex) {
        lastError=ex.what();
        if(h) { h->fail(lastError); copyOutputs(); }
        return nullptr;
    }
}
EXPORT void* cspm_comp_create_from_frame(void* frame,int left,int top,int width,int height) {
    return createCompositionHost(frame,left,top,width,height,false,false);
}
EXPORT void* cspm_comp_create_from_frame_observed(void* frame,uintptr_t livePointer,
        int left,int top,int width,int height,unsigned createSourceBand,
        void* creationOutput,unsigned creationCapacity,void* traceOutput,unsigned traceCapacity) {
    if(!creationOutput || !traceOutput || createSourceBand>1 ||
       creationCapacity<sizeof(NativeCreationObservation) || traceCapacity<sizeof(NativeCallTrace)) {
        lastError="Observed creation output/strategy rejected before native mutation"; return nullptr;
    }
    auto* creation=static_cast<NativeCreationObservation*>(creationOutput);
    auto* trace=static_cast<NativeCallTrace*>(traceOutput);
    if(creation->version!=1 || creation->byteSize!=sizeof(*creation) || creation->rowByteSize!=sizeof(NativeCreationRow) ||
       trace->version!=1 || trace->byteSize!=sizeof(*trace) || trace->rowByteSize!=sizeof(NativeCallRow)) {
        lastError="Observed creation output ABI rejected before native mutation"; return nullptr;
    }
    return createCompositionHost(frame,left,top,width,height,createSourceBand!=0,false,
        reinterpret_cast<HWND>(livePointer),creation,trace);
}
EXPORT void* cspm_comp_create_from_frame_with_source_band(void* frame,uintptr_t livePointer,
                                                        int left,int top,int width,int height) {
    if(!frame || !livePointer) { lastError="Owned source band requires a frame and live HWND"; return nullptr; }
    const HWND live=reinterpret_cast<HWND>(livePointer);
    DWORD process=0; const DWORD thread=GetWindowThreadProcessId(live,&process);
    RECT client{};
    if(!IsWindow(live) || !IsWindowVisible(live) || process!=GetCurrentProcessId() ||
       thread!=GetCurrentThreadId() || GetParent(live) || !GetClientRect(live,&client) ||
       uint32_t(client.right-client.left)!=static_cast<Frame*>(frame)->desc.Width ||
       uint32_t(client.bottom-client.top)!=static_cast<Frame*>(frame)->desc.Height) {
        lastError="Source band creation requires visible owned GUI source with the immutable frame extent";
        return nullptr;
    }
    const bool topmost=(GetWindowLongPtrW(live,GWL_EXSTYLE)&WS_EX_TOPMOST)!=0;
    return createCompositionHost(frame,left,top,width,height,true,topmost);
}
// Diagnostic opt-in: prepare the complete GPU source while its HWND is hidden.
// The GUI owner then transfers native visibility in one window-position batch.
EXPORT int cspm_comp_defer_source_visibility(void* pointer) {
    if(!pointer) return 0; auto& h=*static_cast<Host*>(pointer);
    return h.call([&h] {
        if(h.flags.load()) throw std::runtime_error("Source visibility policy must precede source preparation");
        h.deferredSourceVisibility=true;
    });
}
EXPORT int cspm_comp_transfer_source_visibility(void* pointer,uintptr_t livePointer) {
    if(!pointer || !livePointer) return 0; auto& h=*static_cast<Host*>(pointer);
    const HWND live=reinterpret_cast<HWND>(livePointer);
    sourceTransferEntry(h,live);
    const auto rejected=[&h,live](const char* reason,uint32_t stage,DWORD apiError=0) {
        char detail[256];
        if(stage>=3 && stage<=6) sprintf_s(detail,"%s: Win32 error %lu",reason,apiError);
        else sprintf_s(detail,"%s",reason);
        sourceTransferExit(h,live,stage,apiError);
        h.fail(detail); return 0;
    };
    DWORD process=0;
    const DWORD guiThread=GetWindowThreadProcessId(live,&process);
    if(!h.deferredSourceVisibility || !(h.flags.load()&1) || (h.flags.load()&(2|16)) ||
       process!=GetCurrentProcessId() || guiThread!=GetCurrentThreadId() ||
       !IsWindowVisible(live) || IsWindowVisible(h.hwnd) || GetParent(live)!=GetParent(h.hwnd))
        return rejected("Source visibility transfer requires owned GUI thread, same parent and stopped prepared state",2);
    const bool sourceTopmost=(GetWindowLongPtrW(live,GWL_EXSTYLE)&WS_EX_TOPMOST)!=0;
    h.sourceTopmost.store(sourceTopmost); h.sourceBandKnown.store(true);
    sourceTransferObserve(h,[&](SourceTransferObservation& row) {
        row.expectedTopmost=sourceTopmost; row.policySampled=1;
    });
    // Establish the actual source band on this HWND's owner while still hidden.
    // The GUI thread reveals it without requesting another cross-thread reorder.
    sourceTransferObserve(h,[](SourceTransferObservation& row) { row.stage=10; });
    if(!h.call([&h] { applyOwnedSourceBand(h,false); })) {
        sourceTransferExit(h,live,10); return 0; // Preserve the worker's original failure.
    }
    sourceTransferObserve(h,[](SourceTransferObservation& row) { row.stage=1; });
    if(!sourceVisibilityBandMatches(GetWindowLongPtrW(live,GWL_EXSTYLE),sourceTopmost))
        return rejected("Source visibility band changed before the prepared GUI batch",11);
    const double began=nowSeconds();
    sourceTransferObserve(h,[&](SourceTransferObservation& row) { row.beginBatchSeconds=began; });
    HDWP batch=nativeInvoke(h,NativeBeginVisibilityBatch,0,0,0,true,[&] { return BeginDeferWindowPos(2); });
    if(!batch) return rejected("Begin source visibility batch failed",3,GetLastError());
    sourceTransferObserve(h,[](SourceTransferObservation& row) { row.beginAccepted=1; });
    batch=nativeInvoke(h,NativeDeferLiveHide,0,0,0,true,[&] {
        return DeferWindowPos(batch,live,nullptr,0,0,0,0,
            SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_HIDEWINDOW); });
    if(!batch) return rejected("Defer live source hide failed",4,GetLastError());
    sourceTransferObserve(h,[](SourceTransferObservation& row) { row.liveDeferAccepted=1; });
    batch=nativeInvoke(h,NativeDeferNativeShow,0,0,0,true,[&] {
        return DeferWindowPos(batch,h.hwnd,sourceVisibilityBand(sourceTopmost),0,0,0,0,
            SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE|SWP_SHOWWINDOW); });
    if(!batch) return rejected("Defer native source reveal failed",5,GetLastError());
    sourceTransferObserve(h,[](SourceTransferObservation& row) { row.nativeDeferAccepted=1; });
    const double endBegin=h.sourceTransferTraceEnabled ? nowSeconds() : 0;
    sourceTransferObserve(h,[&](SourceTransferObservation& row) { row.endBatchBeginSeconds=endBegin; });
    const BOOL endResult=nativeInvoke(h,NativeEndVisibilityBatch,0,0,0,true,[&] { return EndDeferWindowPos(batch); });
    const DWORD endError=endResult ? 0 : GetLastError();
    const double ended=nowSeconds();
    sourceTransferObserve(h,[&](SourceTransferObservation& row) {
        row.endAccepted=endResult!=FALSE; row.endBatchReturnSeconds=ended;
    });
    if(!endResult) return rejected("End source visibility batch failed",6,endError);
    h.observe([&](Observation& observation) {
        observation.sourceShowBeginSeconds=began; observation.sourceShowReturnSeconds=ended;
    });
    if(IsWindowVisible(live) || !IsWindowVisible(h.hwnd))
        return rejected("Source visibility batch returned without the requested ownership state",7);
    if(!sourceVisibilityBandMatches(GetWindowLongPtrW(h.hwnd,GWL_EXSTYLE),sourceTopmost))
        return rejected("Source visibility batch did not preserve the owned live window band",8);
    sourceTransferExit(h,live,9);
    creationSnapshot(h,7);
    return 1;
}
EXPORT int cspm_comp_raise_source_visibility(void* pointer) {
    if(!pointer) return 0; auto& h=*static_cast<Host*>(pointer);
    return h.call([&h] {
        applyOwnedSourceBand(h,true);
    });
}
static void validateWitnessOutside(const Host& h,float x,float y,float width,float height) {
    if(h.witnessRevision && h.witnessX<x+width && h.witnessX+8>x &&
       h.witnessY<y+height && h.witnessY+8>y)
        throw std::runtime_error("Qualification witness must remain outside client pixels");
}
EXPORT int cspm_comp_set_observer_witness(void* pointer,int x,int y,unsigned revision) {
    if(!pointer) return 0; auto& h=*static_cast<Host*>(pointer);
    return h.call([&h,x,y,revision] {
        if(!revision || revision>65535 || x<0 || y<0 || x+8>h.hostWidth || y+8>h.hostHeight ||
           (h.flags.load()&(2|16)))
            throw std::runtime_error("Invalid diagnostic witness or already running clock");
        h.witnessX=float(x); h.witnessY=float(y); h.witnessRevision=revision;
        if(h.source.view) {
            validateWitnessOutside(h,h.sourceX,h.sourceY,h.sourceW,h.sourceH);
            render(h,true);
        }
    });
}
EXPORT int cspm_comp_set_source_frame(void* pointer,void* frame,float x,float y,float width,float height,
                                     float header,float rightFixedWidth) {
    if(!pointer || !frame) return 0; auto& h=*static_cast<Host*>(pointer);
    auto retained=std::make_shared<Frame>(*static_cast<Frame*>(frame));
    return h.call([&h,retained,x,y,width,height,header,rightFixedWidth] {
        if(h.flags.load()&(1|16)) throw std::runtime_error("Source cannot be uploaded twice or after failure");
        validateRect(h,x,y,width,height);
        validateWitnessOutside(h,x,y,width,height);
        if(width!=retained->desc.Width || height!=retained->desc.Height)
            throw std::runtime_error("Source physical endpoint dimensions differ from GPU frame");
        if(!std::isfinite(header)||!std::isfinite(rightFixedWidth)||header<0||header>=height||
           rightFixedWidth<0||rightFixedWidth>width)
            throw std::runtime_error("Invalid fixed-pixel header/control geometry");
        h.sourceX=h.targetX=x; h.sourceY=h.targetY=y; h.sourceW=h.targetW=width; h.sourceH=h.targetH=height;
        h.header=header; h.rightWidth=rightFixedWidth; h.source=copyPixels(h,*retained);
        creationSnapshot(h,4);
        validateHiddenCreationBand(h);
        h.observe([&](Observation& observation) {
            observation.sourceWidth=retained->desc.Width; observation.sourceHeight=retained->desc.Height;
            observation.sourceFormat=uint32_t(retained->desc.Format);
        });
        render(h,true);
        const double commitBegin=nowSeconds();
        const HRESULT commitResult=nativeInvoke(h,NativeCompositionCommit,0,0,0,false,[&] { return h.compositor->Commit(); });
        const double commitReturn=nowSeconds();
        h.observe([&](Observation& observation) {
            observation.sourceCommitBeginSeconds=commitBegin; observation.sourceCommitReturnSeconds=commitReturn;
        });
        check(commitResult,"Commit source GPU swapchain");
        creationSnapshot(h,5);
        validateHiddenCreationBand(h);
        const double waitBegin=nowSeconds();
        const HRESULT waitResult=nativeInvoke(h,NativeCommitCompletion,UINT32_MAX,0,0,false,[&] {
            return h.compositor->WaitForCommitCompletion(); });
        const double waitReturn=nowSeconds();
        h.observe([&](Observation& observation) {
            observation.sourceWaitBeginSeconds=waitBegin; observation.sourceWaitReturnSeconds=waitReturn;
        });
        check(waitResult,"Source commit processed");
        creationSnapshot(h,6);
        validateHiddenCreationBand(h);
        if(h.flags.load()&16) throw std::runtime_error("Source preparation already failed");
        if(h.deferredSourceVisibility) {
            // Hidden preparation has no source band contract. The owned GUI
            // transfer derives and explicitly applies its live window's band
            // while revealing the native host, then verifies that metadata.
            h.flags.fetch_or(1); // Prepared while hidden; separate batch owns visibility.
            return;
        }
        const double showBegin=nowSeconds();
        const BOOL showed=nativeInvoke(h,NativeSourceShow,0,0,0,true,[&] {
            return SetWindowPos(h.hwnd,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_SHOWWINDOW); });
        const double showReturn=nowSeconds();
        h.observe([&](Observation& observation) {
            observation.sourceShowBeginSeconds=showBegin; observation.sourceShowReturnSeconds=showReturn;
        });
        if(!showed)
            throw std::runtime_error("Show source composition host failed");
        if(h.witnessRevision && !nativeInvoke(h,NativeWitnessPosition,0,0,0,true,[&] {
                return SetWindowPos(h.hwnd,HWND_TOP,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE); }))
            throw std::runtime_error("Diagnostic witness host z-order unavailable");
        h.flags.fetch_or(1); // Native submission/commit processing; scanout requires physical probe.
    });
}
EXPORT int cspm_comp_start(void* pointer,float x,float y,float width,float height,
                           unsigned durationMs,unsigned blendStartMs) {
    if(!pointer) return 0; auto& h=*static_cast<Host*>(pointer);
    return h.call([&h,x,y,width,height,durationMs,blendStartMs] {
        const auto flags=h.flags.load();
        if(!(flags&1)||(flags&(2|16))||durationMs<100||durationMs>1000||blendStartMs>=durationMs)
            throw std::runtime_error("Invalid independent motion clock request");
        validateRect(h,x,y,width,height);
        validateWitnessOutside(h,x,y,width,height);
        if(h.destination.view && (width!=h.destination.width || height!=h.destination.height))
            throw std::runtime_error("Prepared target GPU frame differs from physical endpoint dimensions");
        h.targetX=x; h.targetY=y; h.targetW=width; h.targetH=height;
        h.duration=durationMs/1000.; h.blendStart=blendStartMs/1000.; h.startSeconds=nowSeconds();
        h.flags.fetch_or(2); render(h);
        if(!nativeInvoke(h,NativeSetTimer,0,0,0,true,[&] { return SetTimer(h.hwnd,1,1,nullptr); }))
            throw std::runtime_error("Native presentation timer failed");
    });
}
EXPORT int cspm_comp_set_target_frame(void* pointer,void* frame) {
    if(!pointer || !frame) return 0; auto& h=*static_cast<Host*>(pointer);
    auto retained=std::make_shared<Frame>(*static_cast<Frame*>(frame));
    return h.call([&h,retained] {
        const double importBegin=nowSeconds();
        h.observe([&](Observation& observation) {
            observation.targetImportBeginSeconds=importBegin;
            observation.targetWidth=retained->desc.Width; observation.targetHeight=retained->desc.Height;
            observation.targetFormat=uint32_t(retained->desc.Format);
        });
        const auto flags=h.flags.load();
        if(!(flags&1)||(flags&16)||h.destination.view)
            throw std::runtime_error("Target requires source, accepts one GPU frame, and rejects failed transactions");
        const bool running=bool(flags&2);
        if(running && nowSeconds()-h.startSeconds.load()>=h.blendStart)
            throw std::runtime_error("Target readiness missed fixed content-transfer deadline; motion was not paused/restarted");
        if(running && (h.targetW!=retained->desc.Width || h.targetH!=retained->desc.Height))
            throw std::runtime_error("Target physical endpoint dimensions differ from GPU frame");
        auto destination=copyPixels(h,*retained);
        if(running && nowSeconds()-h.startSeconds.load()>=h.blendStart)
            throw std::runtime_error("GPU target transfer exceeded fixed content-transfer deadline");
        h.destination=std::move(destination); h.flags.fetch_or(8);
        const double ready=nowSeconds();
        h.observe([&](Observation& observation) { observation.targetReadySeconds=ready; });
    });
}
EXPORT unsigned cspm_comp_status(void* pointer) { return pointer ? static_cast<Host*>(pointer)->flags.load() : 16; }
EXPORT int cspm_comp_presentation(void* pointer,unsigned* submitted,unsigned* displayed,unsigned* statisticsHRESULT) {
    if(!pointer||!submitted||!displayed||!statisticsHRESULT) return 0;
    auto& h=*static_cast<Host*>(pointer);
    *submitted=h.submittedCount.load(); *displayed=h.displayedCount.load();
    *statisticsHRESULT=h.statisticsResult.load(); return 1;
}
EXPORT int cspm_comp_observation(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(Observation)) return 0;
    auto* result=static_cast<Observation*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(Observation)) return 0;
    auto& h=*static_cast<Host*>(pointer);
    std::lock_guard<std::mutex> lock(h.observationMutex);
    memcpy(result,&h.observation,sizeof(Observation)); return 1;
}
EXPORT int cspm_comp_present_trace(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(PresentTrace)) return 0;
    auto* result=static_cast<PresentTrace*>(output);
    if(result->version!=1 || result->byteSize!=sizeof(PresentTrace) ||
       result->rowByteSize!=sizeof(PresentObservation)) return 0;
    auto& h=*static_cast<Host*>(pointer);
    std::lock_guard<std::mutex> lock(h.observationMutex);
    result->count=unsigned(std::min(h.totalPresentRows,uint64_t(128)));
    result->totalFrames=h.totalPresentRows;
    const auto first=h.totalPresentRows>128 ? h.totalPresentRows%128 : 0;
    for(unsigned i=0;i<result->count;++i) result->rows[i]=h.presentRows[(first+i)%128];
    for(unsigned i=result->count;i<128;++i) result->rows[i]=PresentObservation{};
    return 1;
}
EXPORT double cspm_comp_elapsed_ms(void* pointer) {
    if(!pointer) return 0; const double begin=static_cast<Host*>(pointer)->startSeconds.load();
    return begin ? (nowSeconds()-begin)*1000 : 0;
}
EXPORT uintptr_t cspm_comp_hwnd(void* pointer) { return pointer ? uintptr_t(static_cast<Host*>(pointer)->hwnd) : 0; }
EXPORT int cspm_comp_finish(void* pointer) {
    if(!pointer) return 0; auto& h=*static_cast<Host*>(pointer);
    return h.call([&h] {
        KillTimer(h.hwnd,1);
        const double hideBegin=nowSeconds();
        nativeInvoke(h,NativeHideHost,0,0,0,false,[&] { return ShowWindow(h.hwnd,SW_HIDE); });
        const double hideReturn=nowSeconds();
        h.observe([&](Observation& observation) {
            observation.hostHideBeginSeconds=hideBegin; observation.hostHideReturnSeconds=hideReturn;
        });
        creationSnapshot(h,8);
    });
}
static int destroyHostWithTrace(Host* h,NativeCallTrace* finalTrace) {
    h->call([h] {
        KillTimer(h->hwnd,1);
        const double hideBegin=nowSeconds();
        nativeInvoke(*h,NativeHideHost,0,0,0,false,[&] { return ShowWindow(h->hwnd,SW_HIDE); });
        const double hideReturn=nowSeconds();
        h->observe([&](Observation& observation) {
            if(!observation.hostHideBeginSeconds) {
                observation.hostHideBeginSeconds=hideBegin; observation.hostHideReturnSeconds=hideReturn;
            }
        });
    });
    if(!nativeInvoke(*h,NativeDestroyPost,0,0,0,true,[&] { return PostMessageW(h->hwnd,WM_APP+2,0,0); }))
        h->fail("Native destruction PostMessageW failed");
    if(h->worker.joinable()) {
        if(nativeInvoke(*h,NativeDestroyWait,3000,0,0,true,[&] {
                return WaitForSingleObject(h->worker.native_handle(),3000); })!=WAIT_OBJECT_0) {
            h->fail("Native destruction exceeded 3000 ms; retained host prevents use-after-free");
            lastError="Native destruction exceeded 3000 ms; retained host prevents use-after-free";
            if(finalTrace) cspm_comp_native_call_trace(h,finalTrace,sizeof(*finalTrace));
            return 2; // Existing retained-host policy; callers must not retry destruction.
        }
        h->worker.join();
    }
    if(finalTrace) cspm_comp_native_call_trace(h,finalTrace,sizeof(*finalTrace));
    delete h; return 1;
}
EXPORT int cspm_comp_destroy_with_native_call_trace(void* pointer,void* output,unsigned capacity) {
    if(!pointer || !output || capacity<sizeof(NativeCallTrace)) return 0;
    auto* trace=static_cast<NativeCallTrace*>(output);
    if(trace->version!=1 || trace->byteSize!=sizeof(NativeCallTrace) || trace->rowByteSize!=sizeof(NativeCallRow)) return 0;
    auto* h=static_cast<Host*>(pointer);
    if(!h->nativeCallTraceEnabled.load() || !h->nativeCallTrace) return 0;
    // 0: rejected before any mutation. 1: final trace copied and host deleted.
    // 2: final trace copied after bounded teardown timeout, host retained safely.
    return destroyHostWithTrace(h,trace);
}
EXPORT void cspm_comp_destroy(void* pointer) {
    if(pointer) destroyHostWithTrace(static_cast<Host*>(pointer),nullptr);
}
EXPORT unsigned cspm_comp_error(void* pointer,char* buffer,unsigned capacity) {
    std::string value;
    if(pointer) { auto& h=*static_cast<Host*>(pointer); std::lock_guard<std::mutex> lock(h.errorMutex); value=h.error; }
    else value=lastError;
    if(buffer && capacity) { const size_t count=std::min(size_t(capacity-1),value.size());
        memcpy(buffer,value.data(),count); buffer[count]=0; }
    return unsigned(value.size());
}
