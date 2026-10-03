#version 440
layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 qt_TexCoord0;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix; float qt_Opacity; float clock; float transferStart;
    vec4 sourceRect; vec4 targetRect; vec4 headerMetrics;
    vec4 sourceCaptureUv; vec4 targetCaptureUv;
};
// Independently derived polynomial: value 0/1 and derivatives 1..3 zero at
// both endpoints. Its clock is independent of target readiness.
float flow(float t) { t=clamp(t,0.0,1.0); return t*t*t*t*(35.0+t*(-84.0+t*(70.0-20.0*t))); }
void main() {
    qt_TexCoord0 = qt_MultiTexCoord0;
    float p=flow(clock);
    vec4 bounds=mix(sourceRect,targetRect,p);
    vec4 uv=mix(sourceCaptureUv,targetCaptureUv,p);
    gl_Position=qt_Matrix*vec4(bounds.xy+(qt_MultiTexCoord0-uv.xy)*bounds.zw/uv.zw,0.0,1.0);
}
