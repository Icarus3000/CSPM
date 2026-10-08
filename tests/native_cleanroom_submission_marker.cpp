// Real D3D11/DirectComposition marker control; no Qt, workbook or private content.
// This is a GPU test, separate from the safe no-window contract executable.
#include "../src/native/cleanroom_composition/cleanroom_composition.cpp"
#include <vector>
#include <array>

namespace {
std::array<unsigned char,4> markerValue(unsigned x,unsigned y,unsigned revision) {
    const unsigned alpha=(x>=1111&&x<=1122&&y>=646&&y<=655) ? (x+y)%3*85 : 255;
    return {static_cast<unsigned char>((x+revision*31)%(alpha+1)),
        static_cast<unsigned char>((y+revision*47)%(alpha+1)),
        static_cast<unsigned char>((x*3+y*5+revision*59)%(alpha+1)),static_cast<unsigned char>(alpha)};
}
Pixels markers(Host& h,UINT width,UINT height,unsigned revision,DXGI_FORMAT format=DXGI_FORMAT_B8G8R8A8_UNORM) {
    std::vector<unsigned char> bytes(size_t(width)*height*4);
    for(UINT y=0;y<height;++y) for(UINT x=0;x<width;++x) {
        auto* pixel=&bytes[(size_t(y)*width+x)*4];
        const auto value=markerValue(x,y,revision);
        pixel[0]=value[format==DXGI_FORMAT_R8G8B8A8_UNORM ? 2 : 0];
        pixel[1]=value[1]; pixel[2]=value[format==DXGI_FORMAT_R8G8B8A8_UNORM ? 0 : 2];
        pixel[3]=value[3];
    }
    D3D11_TEXTURE2D_DESC desc{};
    desc.Width=width; desc.Height=height; desc.MipLevels=desc.ArraySize=1;
    desc.Format=format; desc.SampleDesc.Count=1;
    desc.Usage=D3D11_USAGE_DEFAULT; desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
    D3D11_SUBRESOURCE_DATA initial{bytes.data(),width*4,0};
    Pixels pixels; pixels.width=width; pixels.height=height;
    pixels.frameRevision=revision; pixels.resourceIdentity=++nextResourceIdentity;
    check(h.gpu->CreateTexture2D(&desc,&initial,&pixels.texture),"Create synthetic markers");
    check(h.gpu->CreateShaderResourceView(pixels.texture.Get(),nullptr,&pixels.view),"Create marker SRV");
    return pixels;
}
std::vector<int> locations(UINT width,UINT height) {
    std::vector<int> xy{0,0,int(width-1),0,0,int(height-1),int(width-1),int(height-1),
        int(width/2),0,int(width/2),int(height-1),0,int(height/2),int(width-1),int(height/2),
        int(width/2),int(height/2)};
    for(int y : {646,650,655}) for(int x=1111;x<=1122;++x) { xy.push_back(x); xy.push_back(y); }
    return xy;
}
unsigned mismatches(Host& h,const Pixels& expected,const std::vector<int>& xy,int offsetX,int offsetY) {
    unsigned char reference[256]{},actual[256]{};
    const unsigned count=unsigned(xy.size()/2);
    if(!probeCoordinatesValid(xy.data(),count,expected.width,expected.height,
            offsetX,offsetY,unsigned(h.hostWidth),unsigned(h.hostHeight)))
        throw std::runtime_error("Synthetic marker coordinates invalid");
    probeTexels(h,expected.texture.Get(),xy.data(),count,0,0,reference);
    probeTexels(h,h.lastSubmittedTexture.Get(),xy.data(),count,offsetX,offsetY,actual);
    unsigned failures=0;
    for(unsigned i=0;i<count;++i) {
        const auto authored=markerValue(unsigned(xy[2*i]),unsigned(xy[2*i+1]),unsigned(expected.frameRevision));
        if(memcmp(reference+4*i,authored.data(),4)!=0)
            throw std::runtime_error("Probe reference differs from independently CPU-authored coordinate marker");
        if(memcmp(authored.data(),actual+4*i,4)!=0) ++failures;
    }
    return failures;
}
UINT diagnosticPitch(Host& h,ID3D11Texture2D* input) {
    D3D11_TEXTURE2D_DESC desc{}; input->GetDesc(&desc);
    desc.Width=desc.Height=desc.MipLevels=desc.ArraySize=1;
    desc.Usage=D3D11_USAGE_STAGING; desc.BindFlags=desc.MiscFlags=0;
    desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    ComPtr<ID3D11Texture2D> staging;
    check(h.gpu->CreateTexture2D(&desc,nullptr,&staging),"Create marker pitch staging");
    const D3D11_BOX firstTexel{0,0,0,1,1,1};
    h.context->CopySubresourceRegion(staging.Get(),0,0,0,0,input,0,&firstTexel);
    D3D11_MAPPED_SUBRESOURCE mapped{};
    check(h.context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped),"Map marker pitch staging");
    const UINT pitch=mapped.RowPitch;
    h.context->Unmap(staging.Get(),0);
    if(pitch<4) throw std::runtime_error("One-texel staging pitch is smaller than one BGRA pixel");
    return pitch;
}
}
int main() {
    Host h;
    try {
        ComPtr<ID3D11Device> seed; ComPtr<ID3D11DeviceContext> seedContext;
        D3D_FEATURE_LEVEL feature{};
        check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            nullptr,0,D3D11_SDK_VERSION,&seed,&feature,&seedContext),"Create marker seed GPU");
        ComPtr<IDXGIDevice> dxgi; check(seed.As(&dxgi),"Marker seed DXGI");
        ComPtr<IDXGIAdapter> adapter; check(dxgi->GetAdapter(&adapter),"Marker adapter");
        initialize(h,adapter.Get(),100,100,1200,760);
        enableProbeSnapshot(h);
        h.sourceX=h.targetX=12; h.sourceY=h.targetY=14;
        h.sourceW=h.targetW=1144; h.sourceH=h.targetH=720;
        h.duration=.350; h.blendStart=.240;
        h.witnessRevision=0x5137;
        unsigned sourceFailures=0,endpointFailures=0;
        const auto sourceXY=locations(1144,720),targetXY=locations(1128,680);
        UINT pitches[2]{};
        for(unsigned formatIndex=0;formatIndex<2;++formatIndex) {
          const auto format=formatIndex ? DXGI_FORMAT_R8G8B8A8_UNORM : DXGI_FORMAT_B8G8R8A8_UNORM;
          const uint64_t firstSnapshot=h.snapshotRevision;
          h.endpointSubmitted=false; h.endpointCount=0; h.flags=0;
          h.source=Pixels{}; h.destination=Pixels{};
          h.sourceX=h.targetX=12; h.sourceY=h.targetY=14;
          h.sourceW=h.targetW=1144; h.sourceH=h.targetH=720;
          h.observation.targetWidth=h.observation.targetHeight=h.observation.targetFormat=0;
          for(unsigned revision=1;revision<=3;++revision) {
            const unsigned markerRevision=revision+formatIndex*32;
            h.source=markers(h,1144,720,markerRevision,format);
            pitches[formatIndex]=diagnosticPitch(h,h.source.texture.Get());
            h.observation.sourceWidth=1144; h.observation.sourceHeight=720;
            h.observation.sourceFormat=format;
            render(h,true);
            if(!probeIdentityMatches(h.probeIdentity,1,h.observation) ||
                    h.probeIdentity.sourceFrameRevision!=markerRevision || h.probeIdentity.snapshotRevision!=firstSnapshot+revision)
                throw std::runtime_error("Stopped source identity did not follow marker revision");
            sourceFailures+=mismatches(h,h.source,sourceXY,12,14);
          }
        const unsigned targetRevision=19+formatIndex*32;
        h.destination=markers(h,1128,680,targetRevision,format);
        h.observation.targetWidth=1128; h.observation.targetHeight=680;
        h.observation.targetFormat=format;
        h.targetX=40; h.targetY=50; h.targetW=1128; h.targetH=680;
        // Intermediate motion must not rewrite the stopped diagnostic copy.
        h.flags.store(1|2|8); h.startSeconds=nowSeconds()-.120; render(h);
        if(h.snapshotRevision!=firstSnapshot+3 || probeIdentityMatches(h.probeIdentity,1,h.observation) ||
                mismatches(h,h.source,sourceXY,12,14))
            throw std::runtime_error("Intermediate motion rewrote or accepted a stopped probe");
        h.flags.store(1|2|8); h.startSeconds=nowSeconds()-.400; render(h);
        if(!probeIdentityMatches(h.probeIdentity,3,h.observation) ||
                h.probeIdentity.targetFrameRevision!=targetRevision || h.probeIdentity.snapshotRevision!=firstSnapshot+4)
            throw std::runtime_error("Complete endpoint identity did not follow target marker revision");
        endpointFailures+=mismatches(h,h.destination,targetXY,40,50);
        // Hiding the host must retain the same revision and immutable samples.
        ShowWindow(h.hwnd,SW_HIDE);
        if(mismatches(h,h.destination,targetXY,40,50))
            throw std::runtime_error("Host hide changed retained endpoint samples");
        }
        ProbeIdentity identity;
        if(!cspm_comp_probe_identity(&h,&identity,sizeof(identity)))
            throw std::runtime_error("Exported stopped identity unavailable");
        printf("{\"sourceSamples\":270,\"sourceMismatchCount\":%u,\"endpointSamples\":90,\"endpointMismatchCount\":%u,\"cpuAuthoredCoordinateCheck\":true,\"formats\":[\"BGRA8_UNORM\",\"RGBA8_UNORM\"],\"oneTexelRowPitchBytes\":[%u,%u],\"hostGeneration\":%llu,\"snapshotRevision\":%llu,\"sourceFrameRevision\":%llu,\"targetFrameRevision\":%llu,\"submittedPresentId\":%u,\"witnessRevision\":%u,\"snapshotResourceIdentity\":%llu,\"intermediateMotionCopyCount\":0,\"retainedAfterHide\":true,\"noPrivateContent\":true,\"scope\":\"real D3D11 shader and flip-model Present; no desktop scanout claim\"}\n",sourceFailures,endpointFailures,pitches[0],pitches[1],
            static_cast<unsigned long long>(identity.hostGeneration),static_cast<unsigned long long>(identity.snapshotRevision),
            static_cast<unsigned long long>(identity.sourceFrameRevision),static_cast<unsigned long long>(identity.targetFrameRevision),
            identity.submittedPresentId,identity.witnessRevision,static_cast<unsigned long long>(identity.snapshotResourceIdentity));
        releaseResources(h);
        return sourceFailures||endpointFailures ? 2 : 0;
    } catch(const std::exception& ex) {
        fprintf(stderr,"Synthetic marker control failed: %s\n",ex.what());
        releaseResources(h); return 1;
    }
}
