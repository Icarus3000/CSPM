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
#include <dcomp.h>
#include <wrl/client.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <deque>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>

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
struct Frame {
    ComPtr<ID3D11Texture2D> texture;
    ComPtr<IDXGIKeyedMutex> mutex;
    D3D11_TEXTURE2D_DESC desc{};
    HANDLE sharedHandle=nullptr;
};
struct Pixels {
    ComPtr<ID3D11Texture2D> texture;
    ComPtr<ID3D11ShaderResourceView> view;
    UINT width=0,height=0;
};
struct Constants {
    float currentRect[4],sourceRect[4],targetRect[4],sizes[4],motion[4];
};
static_assert(sizeof(Constants)==80,"HLSL constant-buffer layout");
struct Host {
    HWND hwnd=nullptr;
    std::thread worker;
    std::mutex queueMutex,errorMutex;
    std::deque<std::function<void()>> queue;
    std::string error;
    std::atomic<unsigned> flags{0};
    ComPtr<ID3D11Device> gpu;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<IDCompositionDevice> compositor;
    ComPtr<IDCompositionTarget> target;
    ComPtr<IDCompositionVisual> root;
    ComPtr<IDXGISwapChain1> swapchain;
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
    bool apartment=false;
    void fail(const std::string& message) {
        std::lock_guard<std::mutex> lock(errorMutex); error=message; flags.fetch_or(16);
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
        if(!PostMessageW(hwnd,WM_APP+1,0,0)) {
            cancelled->store(true); fail("Native command PostMessageW failed"); return 0;
        }
        if(future.wait_for(std::chrono::seconds(2))!=std::future_status::ready) {
            cancelled->store(true); fail("Native command exceeded bounded 2000 ms completion"); return 0;
        }
        return future.get();
    }
};
const char* shader=R"HLSL(
Texture2D oldFrame : register(t0);
Texture2D newFrame : register(t1);
SamplerState linearClamp : register(s0);
cbuffer Motion : register(b0) {
    float4 currentRect,sourceRect,targetRect,sizes,motion;
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
    const HRESULT hr=h.swapchain->GetFrameStatistics(&stats);
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
    if(WaitForSingleObjectEx(h.frameReady,100,FALSE)!=WAIT_OBJECT_0)
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
    h.context->UpdateSubresource(h.constants.Get(),0,nullptr,&c,0,0);
    ComPtr<ID3D11Texture2D> buffer;
    check(h.swapchain->GetBuffer(0,__uuidof(ID3D11Texture2D),&buffer),"Swapchain.GetBuffer");
    ComPtr<ID3D11RenderTargetView> view;
    check(h.gpu->CreateRenderTargetView(buffer.Get(),nullptr,&view),"Create presentation RTV");
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
    check(h.swapchain->Present(1,0),"Present GPU-only premultiplied frame");
    UINT submitted=0;
    if(SUCCEEDED(h.swapchain->GetLastPresentCount(&submitted))) h.submittedCount=submitted;
    if(!initial && elapsed>=duration) {
        h.endpointSubmitted=true; h.endpointCount=submitted;
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
    if(message==WM_APP+2) { KillTimer(hwnd,1); DestroyWindow(hwnd); PostQuitMessage(0); return 0; }
    return DefWindowProcW(hwnd,message,w,l);
}
void initialize(Host& h,IDXGIAdapter* adapter,int left,int top,int width,int height) {
    check(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED),"CoInitializeEx"); h.apartment=true;
    WNDCLASSW wc{}; wc.lpfnWndProc=procedure; wc.hInstance=GetModuleHandleW(nullptr);
    wc.lpszClassName=L"CSPMExperimentalDirectCompositionShader";
    if(!RegisterClassW(&wc) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)
        throw std::runtime_error("RegisterClassW failed");
    h.hwnd=CreateWindowExW(WS_EX_NOREDIRECTIONBITMAP|WS_EX_TOOLWINDOW|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE,
        wc.lpszClassName,L"CSPM experimental native composition",WS_POPUP,
        left,top,width,height,nullptr,nullptr,wc.hInstance,&h);
    if(!h.hwnd) throw std::runtime_error("CreateWindowExW failed");
    h.hostWidth=width; h.hostHeight=height;
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
}
void releaseResources(Host& h) {
    if(h.context) { h.context->ClearState(); h.context->Flush(); }
    h.root.Reset(); h.target.Reset(); h.source=Pixels{}; h.destination=Pixels{};
    h.vertexShader.Reset(); h.pixelShader.Reset(); h.constants.Reset(); h.sampler.Reset();
    if(h.frameReady) { CloseHandle(h.frameReady); h.frameReady=nullptr; }
    h.swapchain.Reset(); h.compositor.Reset(); h.context.Reset(); h.gpu.Reset();
    if(h.hwnd && IsWindow(h.hwnd)) DestroyWindow(h.hwnd);
    h.hwnd=nullptr;
    if(h.apartment) { CoUninitialize(); h.apartment=false; }
}
Pixels copyPixels(Host& h,Frame& frame) {
    ComPtr<ID3D11Texture2D> opened;
    check(h.gpu->OpenSharedResource(frame.sharedHandle,__uuidof(ID3D11Texture2D),&opened),"OpenSharedResource");
    D3D11_TEXTURE2D_DESC openedDesc{}; opened->GetDesc(&openedDesc);
    if(openedDesc.Width!=frame.desc.Width || openedDesc.Height!=frame.desc.Height ||
       openedDesc.Format!=frame.desc.Format || openedDesc.MipLevels!=1 || openedDesc.ArraySize!=1 ||
       openedDesc.SampleDesc.Count!=1)
        throw std::runtime_error("Shared GPU frame dimensions/format mismatch");
    ComPtr<IDXGIKeyedMutex> mutex; check(opened.As(&mutex),"Shared texture keyed mutex");
    if(mutex->AcquireSync(1,40)!=S_OK)
        throw std::runtime_error("GPU synchronization: shared texture AcquireSync missed 40 ms bound");
    Pixels pixels;
    try {
        auto desc=frame.desc; desc.Usage=D3D11_USAGE_DEFAULT; desc.CPUAccessFlags=0;
        desc.BindFlags=D3D11_BIND_SHADER_RESOURCE; desc.MiscFlags=0;
        pixels.width=desc.Width; pixels.height=desc.Height;
        check(h.gpu->CreateTexture2D(&desc,nullptr,&pixels.texture),"Create native owned GPU frame");
        // CopyResource copies identical extents; no atlas offset/destination
        // subrectangle remains to exceed the resource bounds.
        h.context->CopyResource(pixels.texture.Get(),opened.Get()); h.context->Flush();
        check(h.gpu->CreateShaderResourceView(pixels.texture.Get(),nullptr,&pixels.view),"Create GPU frame SRV");
        check(mutex->ReleaseSync(1),"Shared texture ReleaseSync(immutable)");
    } catch(...) { mutex->ReleaseSync(1); throw; }
    return pixels;
}
void validateRect(const Host& h,float x,float y,float width,float height) {
    if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(width)||!std::isfinite(height)||
       x<0||y<0||width<=0||height<=0||double(x)+width>h.hostWidth||double(y)+height>h.hostHeight)
        throw std::runtime_error("Physical frame rectangle exceeds fixed composition host bounds");
    if(x!=std::floor(x)||y!=std::floor(y)||width!=std::floor(width)||height!=std::floor(height))
        throw std::runtime_error("Endpoint frame rectangles must use integral physical pixels");
}
}

EXPORT unsigned cspm_comp_abi_version() { return 1; }
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
EXPORT void* cspm_comp_create_from_frame(void* frame,int left,int top,int width,int height) {
    try {
        if(!frame || width<=0 || height<=0) throw std::runtime_error("Invalid composition host bounds/frame");
        auto h=std::make_unique<Host>(); auto* host=h.get();
        ComPtr<ID3D11Device> sourceGpu; static_cast<Frame*>(frame)->texture->GetDevice(&sourceGpu);
        ComPtr<IDXGIDevice> dxgi; check(sourceGpu.As(&dxgi),"Source IDXGIDevice");
        ComPtr<IDXGIAdapter> adapter; check(dxgi->GetAdapter(&adapter),"Source GPU adapter");
        auto initialized=std::make_shared<std::promise<void>>(); auto ready=initialized->get_future();
        h->worker=std::thread([host,adapter,left,top,width,height,initialized] {
            try { initialize(*host,adapter.Get(),left,top,width,height); initialized->set_value(); }
            catch(...) { releaseResources(*host); initialized->set_exception(std::current_exception()); return; }
            MSG message; while(GetMessageW(&message,nullptr,0,0)>0) { TranslateMessage(&message); DispatchMessageW(&message); }
            releaseResources(*host);
        });
        if(ready.wait_for(std::chrono::seconds(3))!=std::future_status::ready) {
            // Initialization can be in a driver call. Retain storage/thread
            // rather than delete a live host or terminate the driver thread.
            host->fail("Native initialization exceeded 3000 ms; host retained for lifetime safety");
            h.release(); throw std::runtime_error("Native initialization exceeded 3000 ms; host retained for lifetime safety");
        }
        try { ready.get(); } catch(...) { h->worker.join(); throw; }
        return h.release();
    } catch(const std::exception& ex) { lastError=ex.what(); return nullptr; }
}
EXPORT int cspm_comp_set_source_frame(void* pointer,void* frame,float x,float y,float width,float height,
                                     float header,float rightFixedWidth) {
    if(!pointer || !frame) return 0; auto& h=*static_cast<Host*>(pointer);
    auto retained=std::make_shared<Frame>(*static_cast<Frame*>(frame));
    return h.call([&h,retained,x,y,width,height,header,rightFixedWidth] {
        if(h.flags.load()&(1|16)) throw std::runtime_error("Source cannot be uploaded twice or after failure");
        validateRect(h,x,y,width,height);
        if(width!=retained->desc.Width || height!=retained->desc.Height)
            throw std::runtime_error("Source physical endpoint dimensions differ from GPU frame");
        if(!std::isfinite(header)||!std::isfinite(rightFixedWidth)||header<0||header>=height||
           rightFixedWidth<0||rightFixedWidth>width)
            throw std::runtime_error("Invalid fixed-pixel header/control geometry");
        h.sourceX=h.targetX=x; h.sourceY=h.targetY=y; h.sourceW=h.targetW=width; h.sourceH=h.targetH=height;
        h.header=header; h.rightWidth=rightFixedWidth; h.source=copyPixels(h,*retained);
        render(h,true);
        check(h.compositor->Commit(),"Commit source GPU swapchain");
        check(h.compositor->WaitForCommitCompletion(),"Source commit processed");
        if(h.flags.load()&16) throw std::runtime_error("Source preparation already failed");
        if(!SetWindowPos(h.hwnd,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_SHOWWINDOW))
            throw std::runtime_error("Show source composition host failed");
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
        if(h.destination.view && (width!=h.destination.width || height!=h.destination.height))
            throw std::runtime_error("Prepared target GPU frame differs from physical endpoint dimensions");
        h.targetX=x; h.targetY=y; h.targetW=width; h.targetH=height;
        h.duration=durationMs/1000.; h.blendStart=blendStartMs/1000.; h.startSeconds=nowSeconds();
        h.flags.fetch_or(2); render(h);
        if(!SetTimer(h.hwnd,1,1,nullptr)) throw std::runtime_error("Native presentation timer failed");
    });
}
EXPORT int cspm_comp_set_target_frame(void* pointer,void* frame) {
    if(!pointer || !frame) return 0; auto& h=*static_cast<Host*>(pointer);
    auto retained=std::make_shared<Frame>(*static_cast<Frame*>(frame));
    return h.call([&h,retained] {
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
    });
}
EXPORT unsigned cspm_comp_status(void* pointer) { return pointer ? static_cast<Host*>(pointer)->flags.load() : 16; }
EXPORT int cspm_comp_presentation(void* pointer,unsigned* submitted,unsigned* displayed,unsigned* statisticsHRESULT) {
    if(!pointer||!submitted||!displayed||!statisticsHRESULT) return 0;
    auto& h=*static_cast<Host*>(pointer);
    *submitted=h.submittedCount.load(); *displayed=h.displayedCount.load();
    *statisticsHRESULT=h.statisticsResult.load(); return 1;
}
EXPORT double cspm_comp_elapsed_ms(void* pointer) {
    if(!pointer) return 0; const double begin=static_cast<Host*>(pointer)->startSeconds.load();
    return begin ? (nowSeconds()-begin)*1000 : 0;
}
EXPORT uintptr_t cspm_comp_hwnd(void* pointer) { return pointer ? uintptr_t(static_cast<Host*>(pointer)->hwnd) : 0; }
EXPORT int cspm_comp_finish(void* pointer) {
    if(!pointer) return 0; auto& h=*static_cast<Host*>(pointer);
    return h.call([&h] { KillTimer(h.hwnd,1); ShowWindow(h.hwnd,SW_HIDE); });
}
EXPORT void cspm_comp_destroy(void* pointer) {
    if(!pointer) return; auto* h=static_cast<Host*>(pointer);
    h->call([h] { KillTimer(h->hwnd,1); ShowWindow(h->hwnd,SW_HIDE); });
    if(!PostMessageW(h->hwnd,WM_APP+2,0,0)) h->fail("Native destruction PostMessageW failed");
    if(h->worker.joinable()) {
        if(WaitForSingleObject(h->worker.native_handle(),3000)!=WAIT_OBJECT_0) {
            h->fail("Native destruction exceeded 3000 ms; retained host prevents use-after-free");
            lastError="Native destruction exceeded 3000 ms; retained host prevents use-after-free"; return;
        }
        h->worker.join();
    }
    delete h;
}
EXPORT unsigned cspm_comp_error(void* pointer,char* buffer,unsigned capacity) {
    std::string value;
    if(pointer) { auto& h=*static_cast<Host*>(pointer); std::lock_guard<std::mutex> lock(h.errorMutex); value=h.error; }
    else value=lastError;
    if(buffer && capacity) { const size_t count=std::min(size_t(capacity-1),value.size());
        memcpy(buffer,value.data(),count); buffer[count]=0; }
    return unsigned(value.size());
}
