#version 440
layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 qt_TexCoord0;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float progress;
    vec4 sourceRect;
    vec4 targetRect;
    vec4 headerMetrics;
};
void main() {
    qt_TexCoord0 = qt_MultiTexCoord0;
    vec4 bounds = mix(sourceRect, targetRect, clamp(progress, 0.0, 1.0));
    gl_Position = qt_Matrix * vec4(bounds.xy + qt_MultiTexCoord0 * bounds.zw, 0.0, 1.0);
}
