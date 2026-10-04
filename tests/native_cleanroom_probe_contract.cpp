// Static native probe contract: no HWND, device, Qt or WebEngine is created.
#include "../src/native/cleanroom_composition/cleanroom_composition.cpp"
#include <cassert>
#include <climits>
int main() {
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
    unsigned char source[256]{},submitted[256]{};
    assert(cspm_comp_probe_pixels(nullptr,points,2,source,submitted)==0);
    assert(cspm_comp_probe_pixels(nullptr,points,2,nullptr,submitted)==0);
    assert(cspm_comp_probe_pixels(nullptr,points,2,source,nullptr)==0);
    assert(cspm_comp_observation(nullptr,nullptr,0)==0);
    assert(cspm_comp_present_trace(nullptr,nullptr,0)==0);
    assert(cspm_comp_defer_source_visibility(nullptr)==0);
    assert(cspm_comp_transfer_source_visibility(nullptr,0)==0);
    assert(cspm_comp_raise_source_visibility(nullptr)==0);
    return 0;
}
