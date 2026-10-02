#version 440
layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 qt_TexCoord0;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float progress;
    float preparationProgress;
    float settlementProgress;
    float earlyMotion;
    vec4 sourceRect;
    vec4 targetRect;
    vec4 headerMetrics;
    vec4 sourceCaptureUv;
    vec4 targetCaptureUv;
};
void main() {
    qt_TexCoord0 = qt_MultiTexCoord0;
    // The finish factor starts at zero, preserving position and velocity when
    // the final texture becomes ready. At one it owns the exact endpoint.
    float p = earlyMotion > 0.5
        ? mix(preparationProgress, 1.0, settlementProgress) : progress;
    vec4 bounds = mix(sourceRect, targetRect, clamp(p, 0.0, 1.0));
    vec4 captureUv = mix(sourceCaptureUv, targetCaptureUv, clamp(p, 0.0, 1.0));
    vec2 frameSize = bounds.zw / captureUv.zw;
    gl_Position = qt_Matrix * vec4(bounds.xy
        + (qt_MultiTexCoord0 - captureUv.xy) * frameSize, 0.0, 1.0);
}
