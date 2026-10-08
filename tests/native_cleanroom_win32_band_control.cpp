// Disposable pure Win32 A/B capability control: no Qt, D3D, capture or input.
// Never requests foreground, retries positioning or changes another window.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <atomic>
#include <cstdio>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr UINT commandMessage=WM_APP+41;
constexpr DWORD baseStyle=WS_EX_NOREDIRECTIONBITMAP|WS_EX_TOOLWINDOW|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE;
struct State {
    bool valid=false,visible=false,topmost=false,nonactivating=false,inputTransparent=false;
    bool sameProcess=false,guiOwned=false,workerOwned=false,foreground=false,foregroundUnchanged=false;
    unsigned owner=0,parent=0,previous=0,next=0;
    bool previousTopmost=false,nextTopmost=false,previousForeground=false,nextForeground=false;
    unsigned long style=0,exstyle=0;
    RECT rectangle{},client{};
    unsigned dpi=0;
};
struct Row {
    std::string api,phase,insertion;
    long long begin=0,end=0,result=0;
    unsigned long immediateError=0,flags=0;
    bool guiCall=false,workerCall=false;
    State before,after;
};
struct Context {
    std::atomic<HWND> live{nullptr},host{nullptr};
    HWND initialForeground=nullptr;
    DWORD guiThread=GetCurrentThreadId();
    std::atomic<DWORD> workerThread{0};
    std::mutex rowsMutex;
    std::vector<Row> rows;
};
long long qpc() { LARGE_INTEGER value{}; QueryPerformanceCounter(&value); return value.QuadPart; }
unsigned relationship(HWND value,const Context& context) {
    if(!value) return 0;
    if(value==context.live) return 1;
    if(value==context.host) return 2;
    DWORD process=0;
    if(!GetWindowThreadProcessId(value,&process)) return 5;
    return process==GetCurrentProcessId() ? 3U : 4U;
}
State sample(HWND window,const Context& context) {
    State state;
    state.valid=IsWindow(window)!=FALSE;
    state.foregroundUnchanged=GetForegroundWindow()==context.initialForeground;
    if(!state.valid) return state;
    DWORD process=0; const DWORD thread=GetWindowThreadProcessId(window,&process);
    state.sameProcess=process==GetCurrentProcessId();
    state.guiOwned=thread==context.guiThread; state.workerOwned=thread==context.workerThread;
    state.visible=IsWindowVisible(window)!=FALSE;
    state.style=static_cast<DWORD>(GetWindowLongPtrW(window,GWL_STYLE));
    state.exstyle=static_cast<DWORD>(GetWindowLongPtrW(window,GWL_EXSTYLE));
    state.topmost=(state.exstyle&WS_EX_TOPMOST)!=0;
    state.nonactivating=(state.exstyle&WS_EX_NOACTIVATE)!=0;
    state.inputTransparent=(state.exstyle&WS_EX_TRANSPARENT)!=0;
    const HWND foreground=GetForegroundWindow(); state.foreground=window==foreground;
    state.owner=relationship(GetWindow(window,GW_OWNER),context);
    state.parent=relationship(GetParent(window),context);
    const HWND previous=GetWindow(window,GW_HWNDPREV),next=GetWindow(window,GW_HWNDNEXT);
    state.previous=relationship(previous,context); state.next=relationship(next,context);
    state.previousTopmost=previous && (GetWindowLongPtrW(previous,GWL_EXSTYLE)&WS_EX_TOPMOST)!=0;
    state.nextTopmost=next && (GetWindowLongPtrW(next,GWL_EXSTYLE)&WS_EX_TOPMOST)!=0;
    state.previousForeground=previous && previous==foreground; state.nextForeground=next && next==foreground;
    GetWindowRect(window,&state.rectangle); GetClientRect(window,&state.client);
    state.dpi=GetDpiForWindow(window);
    return state;
}
template<class F> long long record(Context& context,const char* api,const char* phase,
                                  HWND window,DWORD flags,const char* insertion,F operation) {
    Row row; row.api=api; row.phase=phase; row.flags=flags; row.insertion=insertion;
    row.guiCall=GetCurrentThreadId()==context.guiThread;
    row.workerCall=GetCurrentThreadId()==context.workerThread;
    row.before=sample(window,context);
    row.begin=qpc(); SetLastError(0);
    row.result=static_cast<long long>(operation());
    row.immediateError=GetLastError(); row.end=qpc(); // Preserve before any metadata query.
    row.after=sample(window,context);
    { std::lock_guard<std::mutex> lock(context.rowsMutex); context.rows.push_back(row); }
    return row.result;
}
struct Command { std::function<void()> action; std::promise<void> completion; };
LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM w,LPARAM l) {
    if(message==WM_NCHITTEST) return HTTRANSPARENT;
    if(message==WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    if(message==commandMessage) {
        auto* command=reinterpret_cast<Command*>(l);
        try { command->action(); command->completion.set_value(); }
        catch(...) { command->completion.set_exception(std::current_exception()); }
        return 0;
    }
    if(message==WM_DESTROY && GetWindowLongPtrW(window,GWLP_USERDATA)) PostQuitMessage(0);
    return DefWindowProcW(window,message,w,l);
}
struct Worker {
    std::shared_ptr<Context> storage;
    Context& context;
    std::thread thread;
    bool finished=false;
    Worker(std::shared_ptr<Context> state,DWORD style,int left,int top) : storage(std::move(state)),context(*storage) {
        auto ready=std::make_shared<std::promise<void>>(); auto future=ready->get_future();
        thread=std::thread([state=storage,style,left,top,ready] {
            auto& context=*state;
            context.workerThread=GetCurrentThreadId();
            try {
                record(context,"CreateWindowExW(host)","hidden-create",nullptr,style,"none",[&] {
                    context.host=CreateWindowExW(style,L"CSPMPureWin32BandControl",L"CSPM synthetic hidden band",
                        WS_POPUP,left,top,120,96,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
                    return context.host ? 1 : 0;
                });
                { std::lock_guard<std::mutex> lock(context.rowsMutex);
                  context.rows.back().after=sample(context.host,context); }
                if(!context.host) throw std::runtime_error("host-create");
                SetWindowLongPtrW(context.host,GWLP_USERDATA,1);
                ready->set_value();
            } catch(...) { ready->set_exception(std::current_exception()); return; }
            MSG message{};
            while(GetMessageW(&message,nullptr,0,0)>0) { TranslateMessage(&message); DispatchMessageW(&message); }
        });
        if(future.wait_for(std::chrono::seconds(2))!=std::future_status::ready) {
            thread.detach(); // Worker retains context ownership if initialization is still running.
            throw std::runtime_error("worker-create-deadline");
        }
        try { future.get(); }
        catch(...) { thread.join(); throw; }
    }
    void invoke(std::function<void()> action) {
        auto command=std::make_unique<Command>(); command->action=std::move(action);
        auto future=command->completion.get_future();
        if(!PostMessageW(context.host,commandMessage,0,reinterpret_cast<LPARAM>(command.get())))
            throw std::runtime_error("worker-command-post");
        if(future.wait_for(std::chrono::seconds(2))!=std::future_status::ready) {
            command.release(); // Preserve an allocation that the worker may still own.
            throw std::runtime_error("worker-command-deadline");
        }
        future.get();
    }
    bool destroy() {
        if(finished) return true;
        const HWND host=context.host;
        invoke([state=storage,host] { auto& context=*state;
            record(context,"DestroyWindow(host)","cleanup",host,0,"none",[&] {
            return DestroyWindow(host); }); });
        const auto wait=record(context,"WaitForSingleObject(worker)","cleanup",host,3000,"none",[&] {
            return WaitForSingleObject(thread.native_handle(),3000); });
        if(wait!=WAIT_OBJECT_0) return false;
        thread.join(); finished=true; return !IsWindow(host);
    }
    ~Worker() { if(thread.joinable()) thread.detach(); }
};
void writeState(const State& state) {
    printf("{\"valid\":%u,\"visible\":%u,\"topmost\":%u,\"nonactivating\":%u,\"inputTransparent\":%u,"
        "\"sameProcess\":%u,\"guiOwned\":%u,\"workerOwned\":%u,\"foreground\":%u,\"foregroundUnchanged\":%u,"
        "\"ownerRelation\":%u,\"parentRelation\":%u,\"precedingRelation\":%u,\"followingRelation\":%u,"
        "\"precedingTopmost\":%u,\"followingTopmost\":%u,\"precedingForeground\":%u,\"followingForeground\":%u,"
        "\"style\":%lu,\"exstyle\":%lu,\"windowLTRB\":[%ld,%ld,%ld,%ld],\"clientLTRB\":[%ld,%ld,%ld,%ld],\"dpi\":%u}",
        state.valid,state.visible,state.topmost,state.nonactivating,state.inputTransparent,state.sameProcess,
        state.guiOwned,state.workerOwned,state.foreground,state.foregroundUnchanged,state.owner,state.parent,
        state.previous,state.next,state.previousTopmost,state.nextTopmost,state.previousForeground,state.nextForeground,
        state.style,state.exstyle,state.rectangle.left,state.rectangle.top,state.rectangle.right,state.rectangle.bottom,
        state.client.left,state.client.top,state.client.right,state.client.bottom,state.dpi);
}
bool run(bool topmost,bool createdBand,HWND foreground) {
    auto storage=std::make_shared<Context>(); auto& context=*storage;
    context.initialForeground=foreground;
    bool accepted=false,hiddenGate=false,transferGate=false,cleanupGate=false;
    std::string failure;
    std::unique_ptr<Worker> worker;
    try {
        MONITORINFO monitor{sizeof(monitor)};
        if(!GetMonitorInfoW(MonitorFromPoint({0,0},MONITOR_DEFAULTTOPRIMARY),&monitor))
            throw std::runtime_error("monitor");
        const int left=monitor.rcWork.left+64,top=monitor.rcWork.top+64;
        const DWORD sourceStyle=baseStyle|(topmost ? WS_EX_TOPMOST : 0);
        record(context,"CreateWindowExW(source)","source-create",nullptr,sourceStyle,"none",[&] {
            context.live=CreateWindowExW(sourceStyle,L"CSPMPureWin32BandControl",L"CSPM synthetic source band",
                WS_POPUP,left+12,top+12,96,72,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
            return context.live ? 1 : 0;
        });
        { std::lock_guard<std::mutex> lock(context.rowsMutex);
          context.rows.back().after=sample(context.live,context); }
        if(!context.live) throw std::runtime_error("source-create");
        record(context,"ShowWindow(source)","source-visible",context.live,SW_SHOWNOACTIVATE,"none",[&] {
            return ShowWindow(context.live,SW_SHOWNOACTIVATE); });
        const auto source=sample(context.live,context);
        if(!source.visible || source.topmost!=topmost || !source.guiOwned || !source.sameProcess ||
           source.owner || source.parent || !source.foregroundUnchanged) throw std::runtime_error("source-setup-gate");
        worker=std::make_unique<Worker>(storage,baseStyle|(createdBand && source.topmost ? WS_EX_TOPMOST : 0),left,top);
        worker->invoke([state=storage,createdBand,topmost] {
            auto& context=*state;
            const DWORD flags=SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|(createdBand ? SWP_NOZORDER : 0);
            record(context,"SetWindowPos(host)","hidden-band",context.host,flags,topmost ? "TOPMOST" : "NOTOPMOST",[&] {
                return SetWindowPos(context.host,topmost ? HWND_TOPMOST : HWND_NOTOPMOST,0,0,0,0,flags); });
        });
        const auto hidden=sample(context.host,context);
        hiddenGate=hidden.valid && !hidden.visible && hidden.topmost==source.topmost && hidden.workerOwned &&
            hidden.sameProcess && hidden.nonactivating && hidden.inputTransparent && !hidden.owner && !hidden.parent &&
            hidden.foregroundUnchanged;
        if(!hiddenGate) throw std::runtime_error("hidden-band-gate-before-source-hide");
        HDWP batch=nullptr;
        record(context,"BeginDeferWindowPos","visibility-transfer",context.host,0,"none",[&] {
            batch=BeginDeferWindowPos(2); return batch ? 1 : 0; });
        if(!batch) throw std::runtime_error("visibility-begin");
        constexpr UINT hideFlags=SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_NOZORDER|SWP_HIDEWINDOW;
        record(context,"DeferWindowPos(source-hide)","visibility-transfer",context.live,hideFlags,"ignored",[&] {
            batch=DeferWindowPos(batch,context.live,nullptr,0,0,0,0,hideFlags); return batch ? 1 : 0; });
        if(!batch) throw std::runtime_error("visibility-hide-defer");
        constexpr UINT showFlags=SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_NOZORDER|SWP_SHOWWINDOW;
        record(context,"DeferWindowPos(host-show)","visibility-transfer",context.host,showFlags,"ignored",[&] {
            batch=DeferWindowPos(batch,context.host,nullptr,0,0,0,0,showFlags); return batch ? 1 : 0; });
        if(!batch) throw std::runtime_error("visibility-show-defer");
        const auto endResult=record(context,"EndDeferWindowPos","visibility-transfer",context.host,0,"none",[&] {
            return EndDeferWindowPos(batch); });
        const auto liveAfter=sample(context.live,context),hostAfter=sample(context.host,context);
        transferGate=endResult && !liveAfter.visible && hostAfter.visible && hostAfter.topmost==source.topmost &&
            liveAfter.topmost==source.topmost && hostAfter.foregroundUnchanged && liveAfter.foregroundUnchanged;
        if(!transferGate) throw std::runtime_error("visibility-transfer-gate");
        accepted=true;
    } catch(const std::exception& exception) { failure=exception.what(); }
    if(context.live) record(context,"ShowWindow(source-restore)","cleanup",context.live,SW_SHOWNOACTIVATE,"none",[&] {
        return ShowWindow(context.live,SW_SHOWNOACTIVATE); });
    bool sourceRestored=!context.live || IsWindowVisible(context.live)!=FALSE;
    bool hostDestroyed=!context.host || !IsWindow(context.host);
    if(worker) {
        try { hostDestroyed=worker->destroy(); } catch(const std::exception& exception) { failure=exception.what(); }
    }
    if(context.live) record(context,"DestroyWindow(source)","cleanup",context.live,0,"none",[&] {
        return DestroyWindow(context.live); });
    cleanupGate=sourceRestored && hostDestroyed && !IsWindow(context.live) && GetForegroundWindow()==foreground;
    printf("{\"requestedTopmost\":%s,\"createdBand\":%s,\"accepted\":%s,\"hiddenGate\":%s,"
        "\"transferGate\":%s,\"cleanupGate\":%s,\"failure\":\"%s\",\"calls\":[",
        topmost ? "true":"false",createdBand ? "true":"false",accepted ? "true":"false",
        hiddenGate ? "true":"false",transferGate ? "true":"false",cleanupGate ? "true":"false",failure.c_str());
    std::vector<Row> rows;
    { std::lock_guard<std::mutex> lock(context.rowsMutex); rows=context.rows; }
    for(size_t i=0;i<rows.size();++i) {
        const auto& row=rows[i]; if(i) printf(",");
        printf("{\"api\":\"%s\",\"phase\":\"%s\",\"insertion\":\"%s\",\"beginQpc\":%lld,"
            "\"returnQpc\":%lld,\"result\":%lld,\"immediateGetLastError\":%lu,\"flags\":%lu,"
            "\"guiCall\":%s,\"workerCall\":%s,\"before\":",row.api.c_str(),row.phase.c_str(),row.insertion.c_str(),
            row.begin,row.end,row.result,row.immediateError,row.flags,row.guiCall ? "true":"false",row.workerCall ? "true":"false");
        writeState(row.before); printf(",\"after\":"); writeState(row.after); printf("}");
    }
    printf("]}"); fflush(stdout);
    return accepted && cleanupGate;
}
}
int main() {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    WNDCLASSW windowClass{}; windowClass.lpfnWndProc=procedure; windowClass.hInstance=GetModuleHandleW(nullptr);
    windowClass.lpszClassName=L"CSPMPureWin32BandControl";
    if(!RegisterClassW(&windowClass)) return 2;
    const HWND foreground=GetForegroundWindow(); if(!foreground) return 3;
    LARGE_INTEGER frequency{}; QueryPerformanceFrequency(&frequency);
    printf("{\"schemaVersion\":1,\"scope\":\"Pure Win32 same-process GUI/worker HWND metadata; no Qt/D3D11/desktop pixel or WebEngine proof\","
        "\"privateContent\":false,\"relationEnum\":\"0 none;1 live;2 host;3 other same-process;4 foreign;5 unknown\","
        "\"gateDefinedBeforeRun\":\"visible owned source; stopped hidden matching band before hide; nonactivate transparent unowned worker host;"
        "one preserved-band visibility batch; source restore; both destroyed; foreground unchanged\",\"qpcFrequency\":%lld,\"cases\":[",frequency.QuadPart);
    bool all=true;
    for(unsigned i=0;i<4;++i) { if(i) printf(","); all=run(i>=2,(i&1)!=0,foreground) && all; }
    printf("],\"allCasesAccepted\":%s,\"foregroundUnchanged\":%s}\n",all ? "true":"false",
        GetForegroundWindow()==foreground ? "true":"false");
    return all ? 0 : 1;
}
