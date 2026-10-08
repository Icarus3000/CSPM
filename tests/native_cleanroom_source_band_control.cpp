// Real SDK-only foreground-false control. Run one bridge DLL per process.
// All uploads are deterministic synthetic markers; no Qt or private data.
#include "../src/native/cleanroom_composition/cleanroom_composition.cpp"
#include <vector>

template<class T> T entry(HMODULE library,const char* name) {
    const auto address=GetProcAddress(library,name);
    if(!address) throw std::runtime_error(std::string("Missing native export: ")+name);
    return reinterpret_cast<T>(address);
}
struct Api {
    decltype(&cspm_gpu_capture) capture;
    decltype(&cspm_gpu_release) release;
    decltype(&cspm_comp_create_from_frame) create;
    decltype(&cspm_comp_defer_source_visibility) defer;
    decltype(&cspm_comp_enable_probe_snapshot) snapshot;
    decltype(&cspm_comp_enable_source_transfer_trace) trace;
    decltype(&cspm_comp_set_source_frame) source;
    decltype(&cspm_comp_transfer_source_visibility) transfer;
    decltype(&cspm_comp_probe_pixels) probe;
    decltype(&cspm_comp_source_transfer_observation) observation;
    decltype(&cspm_comp_source_windowpos_trace) windowPositions;
    decltype(&cspm_comp_hwnd) hwnd;
    decltype(&cspm_comp_destroy) destroy;
    explicit Api(HMODULE library) :
        capture(entry<decltype(capture)>(library,"cspm_gpu_capture")),
        release(entry<decltype(release)>(library,"cspm_gpu_release")),
        create(entry<decltype(create)>(library,"cspm_comp_create_from_frame")),
        defer(entry<decltype(defer)>(library,"cspm_comp_defer_source_visibility")),
        snapshot(entry<decltype(snapshot)>(library,"cspm_comp_enable_probe_snapshot")),
        trace(entry<decltype(trace)>(library,"cspm_comp_enable_source_transfer_trace")),
        source(entry<decltype(source)>(library,"cspm_comp_set_source_frame")),
        transfer(entry<decltype(transfer)>(library,"cspm_comp_transfer_source_visibility")),
        probe(entry<decltype(probe)>(library,"cspm_comp_probe_pixels")),
        observation(entry<decltype(observation)>(library,"cspm_comp_source_transfer_observation")),
        windowPositions(entry<decltype(windowPositions)>(library,"cspm_comp_source_windowpos_trace")),
        hwnd(entry<decltype(hwnd)>(library,"cspm_comp_hwnd")),
        destroy(entry<decltype(destroy)>(library,"cspm_comp_destroy")) {}
};
LRESULT CALLBACK liveProcedure(HWND hwnd,UINT message,WPARAM w,LPARAM l) {
    if(message==WM_NCHITTEST) return HTTRANSPARENT;
    if(message==WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    if(message==WM_ERASEBKGND) return 1;
    if(message==WM_PAINT) { PAINTSTRUCT paint; BeginPaint(hwnd,&paint); EndPaint(hwnd,&paint); return 0; }
    return DefWindowProcW(hwnd,message,w,l);
}
struct Outcome {
    bool accepted=false,foregroundUnchanged=false,liveHidden=false,nativeVisible=false,bandMatches=false;
    bool foregroundFalse=false,cleanupForegroundUnchanged=false;
    unsigned mismatches=0;
    SourceTransferObservation observation;
    SourceWindowPosTrace positions;
};
Outcome runPolicy(Api& api,bool topmost,HWND initialForeground) {
    constexpr unsigned width=96,height=72;
    HWND live=nullptr; void* frame=nullptr; void* host=nullptr;
    auto cleanup=[&] {
        if(host) { api.destroy(host); host=nullptr; }
        if(frame) { api.release(frame); frame=nullptr; }
        if(live) { DestroyWindow(live); live=nullptr; }
    };
    try {
        MONITORINFO monitor{}; monitor.cbSize=sizeof(monitor);
        if(!GetMonitorInfoW(MonitorFromPoint(POINT{0,0},MONITOR_DEFAULTTOPRIMARY),&monitor))
            throw std::runtime_error("Synthetic monitor bounds unavailable");
        const int left=monitor.rcWork.left+64,top=monitor.rcWork.top+64;
        live=CreateWindowExW(WS_EX_NOREDIRECTIONBITMAP|WS_EX_TOOLWINDOW|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE,
            L"CSPMSyntheticSourceBandLive",L"CSPM synthetic band control",WS_POPUP,
            left+12,top+12,width,height,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
        if(!live) throw std::runtime_error("Create synthetic live HWND failed");
        ComPtr<ID3D11Device> gpu; ComPtr<ID3D11DeviceContext> context; D3D_FEATURE_LEVEL feature{};
        check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            nullptr,0,D3D11_SDK_VERSION,&gpu,&feature,&context),"Synthetic GPU");
        ComPtr<IDXGIDevice> dxgi; check(gpu.As(&dxgi),"Synthetic DXGI");
        ComPtr<IDXGIAdapter> adapter; check(dxgi->GetAdapter(&adapter),"Synthetic adapter");
        ComPtr<IDXGIFactory2> factory; check(adapter->GetParent(__uuidof(IDXGIFactory2),&factory),"Synthetic factory");
        DXGI_SWAP_CHAIN_DESC1 desc{}; desc.Width=width; desc.Height=height;
        desc.Format=DXGI_FORMAT_B8G8R8A8_UNORM; desc.SampleDesc.Count=1;
        desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT; desc.BufferCount=2;
        desc.Scaling=DXGI_SCALING_STRETCH; desc.SwapEffect=DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL;
        desc.AlphaMode=DXGI_ALPHA_MODE_PREMULTIPLIED;
        ComPtr<IDXGISwapChain1> swapchain;
        check(factory->CreateSwapChainForComposition(gpu.Get(),&desc,nullptr,&swapchain),"Synthetic live swapchain");
        ComPtr<IDCompositionDevice> compositor;
        check(DCompositionCreateDevice(dxgi.Get(),__uuidof(IDCompositionDevice),&compositor),"Synthetic compositor");
        ComPtr<IDCompositionTarget> target; ComPtr<IDCompositionVisual> visual;
        check(compositor->CreateTargetForHwnd(live,TRUE,&target),"Synthetic live target");
        check(compositor->CreateVisual(&visual),"Synthetic visual");
        check(target->SetRoot(visual.Get()),"Synthetic root");
        check(visual->SetContent(swapchain.Get()),"Synthetic marker content");
        std::vector<unsigned char> markers(width*height*4);
        for(unsigned y=0;y<height;++y) for(unsigned x=0;x<width;++x) {
            const auto index=(y*width+x)*4;
            markers[index]=static_cast<unsigned char>(x+31);
            markers[index+1]=static_cast<unsigned char>(y+47);
            markers[index+2]=static_cast<unsigned char>((x*3+y*5+59)%256);
            markers[index+3]=255;
        }
        ComPtr<ID3D11Texture2D> buffer;
        check(swapchain->GetBuffer(0,__uuidof(ID3D11Texture2D),&buffer),"Synthetic live buffer");
        context->UpdateSubresource(buffer.Get(),0,nullptr,markers.data(),width*4,0);
        ComPtr<ID3D11RenderTargetView> view;
        check(gpu->CreateRenderTargetView(buffer.Get(),nullptr,&view),"Synthetic live RTV");
        ID3D11RenderTargetView* renderTarget=view.Get(); context->OMSetRenderTargets(1,&renderTarget,nullptr);
        unsigned capturedWidth=0,capturedHeight=0;
        frame=api.capture(context.Get(),&capturedWidth,&capturedHeight);
        if(!frame || capturedWidth!=width || capturedHeight!=height)
            throw std::runtime_error("Synthetic immutable capture failed");
        context->OMSetRenderTargets(0,nullptr,nullptr);
        check(swapchain->Present(1,0),"Present synthetic live markers");
        check(compositor->Commit(),"Commit synthetic live markers");
        check(compositor->WaitForCommitCompletion(),"Process synthetic live commit");
        if(!SetWindowPos(live,topmost ? HWND_TOPMOST : HWND_NOTOPMOST,0,0,0,0,
                SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_SHOWWINDOW))
            throw std::runtime_error("Show nonactivating synthetic live source failed");
        if(!sourceVisibilityBandMatches(GetWindowLongPtrW(live,GWL_EXSTYLE),topmost) ||
                GetForegroundWindow()!=initialForeground || GetForegroundWindow()==live)
            throw std::runtime_error("Synthetic source setup changed foreground or selected band");
        host=api.create(frame,left,top,120,96);
        if(!host || !api.defer(host) || !api.snapshot(host) || !api.trace(host) ||
                !api.source(host,frame,12,12,width,height,0,0))
            throw std::runtime_error("Prepare synthetic native source failed");
        Outcome result;
        result.accepted=api.transfer(host,uintptr_t(live))!=0;
        const HWND native=reinterpret_cast<HWND>(api.hwnd(host));
        result.foregroundUnchanged=GetForegroundWindow()==initialForeground;
        result.foregroundFalse=GetForegroundWindow()!=live;
        result.liveHidden=!IsWindowVisible(live); result.nativeVisible=IsWindowVisible(native)!=FALSE;
        result.bandMatches=sourceVisibilityBandMatches(GetWindowLongPtrW(native,GWL_EXSTYLE),topmost);
        if(!api.observation(host,&result.observation,sizeof(result.observation)) ||
                !api.windowPositions(host,&result.positions,sizeof(result.positions)))
            throw std::runtime_error("Synthetic transfer metadata unavailable");
        if(result.accepted) {
            const int xy[]{0,0,95,0,0,71,95,71,48,0,48,71,0,36,95,36,48,36};
            unsigned char source[36]{},submitted[36]{};
            if(!api.probe(host,xy,9,source,submitted)) throw std::runtime_error("Synthetic stopped markers unavailable");
            for(unsigned i=0;i<9;++i) {
                const auto index=(unsigned(xy[2*i+1])*width+unsigned(xy[2*i]))*4;
                if(memcmp(source+i*4,markers.data()+index,4) || memcmp(submitted+i*4,markers.data()+index,4))
                    ++result.mismatches;
            }
        }
        cleanup();
        result.cleanupForegroundUnchanged=GetForegroundWindow()==initialForeground;
        return result;
    } catch(...) { cleanup(); throw; }
}
int wmain(int argc,wchar_t** argv) {
    HMODULE library=nullptr;
    try {
        if(argc!=2) throw std::runtime_error("Pass exactly one diagnostic bridge DLL path");
        SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
        const HWND initialForeground=GetForegroundWindow();
        if(!initialForeground) throw std::runtime_error("Interactive initial foreground is unavailable");
        check(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED),"Synthetic apartment");
        WNDCLASSW wc{}; wc.lpfnWndProc=liveProcedure; wc.hInstance=GetModuleHandleW(nullptr);
        wc.lpszClassName=L"CSPMSyntheticSourceBandLive";
        if(!RegisterClassW(&wc)) throw std::runtime_error("Register synthetic live class failed");
        library=LoadLibraryW(argv[1]);
        if(!library) throw std::runtime_error("Load diagnostic DLL failed");
        Api api(library); bool passed=true;
        printf("{\"scope\":\"real SDK-only synthetic GPU source and transfer; no desktop pixel observer/Qt/WebEngine\",\"noPrivateContent\":true,\"policies\":[");
        for(unsigned policy=0;policy<2;++policy) {
            const Outcome result=runPolicy(api,policy!=0,initialForeground);
            if(policy) printf(",");
            printf("{\"topmostPolicy\":%s,\"accepted\":%s,\"stage\":%u,\"foregroundFalse\":%s,\"foregroundUnchanged\":%s,\"cleanupForegroundUnchanged\":%s,\"liveHidden\":%s,\"nativeVisible\":%s,\"bandMatches\":%s,\"markerSamples\":%u,\"markerMismatchCount\":%u,\"liveStyleEntry\":%u,\"liveStyleExit\":%u,\"nativeStyleEntry\":%u,\"nativeStyleExit\":%u,\"liveForegroundEntry\":%u,\"liveForegroundExit\":%u,\"sameProcess\":%u,\"sameParent\":%u,\"liveThreadOwned\":%u,\"nativeThreadOwned\":%u,\"expectedTopmost\":%u,\"windowPositions\":[",
                policy ? "true" : "false",result.accepted ? "true" : "false",result.observation.stage,
                result.foregroundFalse ? "true" : "false",result.foregroundUnchanged ? "true" : "false",
                result.cleanupForegroundUnchanged ? "true" : "false",result.liveHidden ? "true" : "false",
                result.nativeVisible ? "true" : "false",result.bandMatches ? "true" : "false",
                result.accepted ? 9u : 0u,result.mismatches,result.observation.liveStyleEntry,result.observation.liveStyleExit,
                result.observation.nativeStyleEntry,result.observation.nativeStyleExit,
                result.observation.liveForegroundEntry,result.observation.liveForegroundExit,
                result.observation.sameProcess,result.observation.sameParent,result.observation.liveThreadOwned,
                result.observation.nativeThreadOwned,result.observation.expectedTopmost);
            for(unsigned i=0;i<result.positions.count;++i) {
                const auto& row=result.positions.rows[i]; if(i) printf(",");
                printf("{\"sequence\":%llu,\"phase\":%u,\"message\":%u,\"bandBefore\":%u,\"bandAfter\":%u,\"flagsBefore\":%u,\"flagsAfter\":%u,\"styleBefore\":%u,\"styleAfter\":%u,\"visibleAfter\":%u}",
                    static_cast<unsigned long long>(row.sequence),row.phase,row.message,row.insertAfterBandBefore,
                    row.insertAfterBandAfter,row.flagsBefore,row.flagsAfter,row.styleBefore,row.styleAfter,row.visibleAfter);
            }
            printf("]}");
            passed=passed && result.accepted && result.foregroundFalse && result.foregroundUnchanged &&
                result.cleanupForegroundUnchanged && result.liveHidden && result.nativeVisible && result.bandMatches && !result.mismatches;
        }
        printf("],\"allPoliciesPass\":%s}\n",passed ? "true" : "false");
        FreeLibrary(library); CoUninitialize(); return passed ? 0 : 2;
    } catch(const std::exception& ex) {
        fprintf(stderr,"Synthetic band control failed: %s\n",ex.what());
        if(library) FreeLibrary(library); return 1;
    }
}
