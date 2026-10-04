// Static native probe contract: no HWND, device, Qt or WebEngine is created.
#include "../src/native/cleanroom_composition/cleanroom_composition.cpp"
#include <cassert>
#include <climits>
int main() {
    assert(sourceVisibilityBand(true)==HWND_TOPMOST);
    assert(sourceVisibilityBand(false)==HWND_NOTOPMOST);
    assert(sourceVisibilityBandMatches(WS_EX_TOPMOST|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,true));
    assert(sourceVisibilityBandMatches(WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,false));
    assert(!sourceVisibilityBandMatches(WS_EX_TOPMOST,false));
    assert(!sourceVisibilityBandMatches(0,true));
    const int points[]{0,0,99,79};
    assert(probeCoordinatesValid(points,2,100,80,4,6,104,86));
    assert(!probeCoordinatesValid(nullptr,2,100,80,4,6,104,86));
    assert(!probeCoordinatesValid(points,0,100,80,4,6,104,86));
    assert(!probeCoordinatesValid(points,65,100,80,4,6,104,86));
    assert(!probeCoordinatesValid(points,2,99,80,4,6,104,86));
    assert(!probeCoordinatesValid(points,2,100,79,4,6,104,86));
    assert(!probeCoordinatesValid(points,2,100,80,4,6,103,86));
    assert(!probeCoordinatesValid(points,2,100,80,4,6,104,85));
    assert(!probeCoordinatesValid(points,2,100,80,-1,6,104,86));
    const int negative[]{-1,0};
    assert(!probeCoordinatesValid(negative,1,100,80,0,0,100,80));
    const int huge[]{INT_MAX,INT_MAX};
    assert(!probeCoordinatesValid(huge,1,UINT_MAX,UINT_MAX,INT_MAX,INT_MAX,100,100));
    assert(probeEndpointStateValid(1|2|4|8,true,true,true,1.,1.));
    assert(probeEndpointStateValid(1|2|4|8|32,true,true,true,1.,1.));
    for(unsigned required : {1u,2u,4u,8u})
        assert(!probeEndpointStateValid((1|2|4|8)&~required,true,true,true,1.,1.));
    assert(!probeEndpointStateValid(1|2|4|8|16,true,true,true,1.,1.));
    assert(!probeEndpointStateValid(1|2|4|8,false,true,true,1.,1.));
    assert(!probeEndpointStateValid(1|2|4|8,true,false,true,1.,1.));
    assert(!probeEndpointStateValid(1|2|4|8,true,true,false,1.,1.));
    assert(!probeEndpointStateValid(1|2|4|8,true,true,true,.99,1.));
    assert(!probeEndpointStateValid(1|2|4|8,true,true,true,1.,.99));
    unsigned char source[256]{},submitted[256]{};
    assert(cspm_comp_probe_pixels(nullptr,points,2,source,submitted)==0);
    assert(cspm_comp_probe_pixels(nullptr,points,2,nullptr,submitted)==0);
    assert(cspm_comp_probe_pixels(nullptr,points,2,source,nullptr)==0);
    assert(cspm_comp_probe_endpoint_pixels(nullptr,points,2,source,submitted)==0);
    assert(cspm_comp_probe_endpoint_pixels(nullptr,points,2,nullptr,submitted)==0);
    assert(cspm_comp_probe_endpoint_pixels(nullptr,points,2,source,nullptr)==0);
    assert(cspm_comp_probe_frame_pixels(nullptr,nullptr,points,2,source)==0);
    assert(cspm_comp_probe_frame_pixels(nullptr,nullptr,points,2,nullptr)==0);
    assert(cspm_comp_observation(nullptr,nullptr,0)==0);
    assert(cspm_comp_present_trace(nullptr,nullptr,0)==0);
    assert(cspm_comp_defer_source_visibility(nullptr)==0);
    assert(cspm_comp_transfer_source_visibility(nullptr,0)==0);
    assert(cspm_comp_raise_source_visibility(nullptr)==0);
    return 0;
}
