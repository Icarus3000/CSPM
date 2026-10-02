#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
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
layout(binding = 1) uniform sampler2D source;
layout(binding = 2) uniform sampler2D targetSource;

vec2 endpointUv(vec2 point, vec2 currentSize, vec2 endpointSize, float rightWidth) {
    float headerHeight = min(headerMetrics.x, min(currentSize.y, endpointSize.y));
    if (headerHeight > 0.0 && point.y >= 0.0 && point.y < headerHeight
            && point.x >= 0.0 && point.x < currentSize.x) {
        // Lettering stays at one logical pixel per pixel. Only the empty
        // title space expands; the search/controls remain right anchored.
        float cap = min(rightWidth, min(currentSize.x, endpointSize.x));
        float x = point.x >= currentSize.x - cap
            ? endpointSize.x - (currentSize.x - point.x)
            : min(point.x, max(0.0, endpointSize.x - cap - 1.0));
        return vec2(x, point.y) / endpointSize;
    }
    return vec2(point.x / currentSize.x,
        (headerHeight + (point.y - headerHeight)
            * (endpointSize.y - headerHeight) / max(1.0, currentSize.y - headerHeight))
            / endpointSize.y);
}
void main() {
    float p = clamp(earlyMotion > 0.5
        ? mix(preparationProgress, 1.0, settlementProgress) : progress, 0.0, 1.0);
    // Endpoint frames are a direct pixel copy, including borders and padding.
    // Header remapping is exclusively for the intermediate moving layouts.
    if (p <= 0.0) {
        fragColor = texture(source, qt_TexCoord0) * qt_Opacity;
        return;
    }
    if (p >= 1.0) {
        fragColor = texture(targetSource, qt_TexCoord0) * qt_Opacity;
        return;
    }
    vec2 size = mix(sourceRect.zw, targetRect.zw, p);
    vec4 captureUv = mix(sourceCaptureUv, targetCaptureUv, p);
    vec2 point = (qt_TexCoord0 - captureUv.xy) * size / captureUv.zw;
    vec2 oldUv = endpointUv(point, size, sourceRect.zw, headerMetrics.y);
    vec4 oldPixels = texture(source, sourceCaptureUv.xy + oldUv * sourceCaptureUv.zw);
    float blend = smoothstep(0.0, 0.85, earlyMotion > 0.5 ? settlementProgress : p);
    if (blend <= 0.0) {
        fragColor = oldPixels * qt_Opacity;
        return;
    }
    vec2 finalUv = endpointUv(point, size, targetRect.zw, headerMetrics.z);
    vec4 finalPixels = texture(targetSource, targetCaptureUv.xy + finalUv * targetCaptureUv.zw);
    // Complete the layout change before reaching the endpoint. At p=1 this
    // is the final scene at 1:1 scale, so revealing it cannot resize text.
    fragColor = mix(oldPixels, finalPixels, blend) * qt_Opacity;
}
