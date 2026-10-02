#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float progress;
    vec4 sourceRect;
    vec4 targetRect;
    vec4 headerMetrics;
};
layout(binding = 1) uniform sampler2D source;
layout(binding = 2) uniform sampler2D targetSource;

vec2 endpointUv(vec2 point, vec2 currentSize, vec2 endpointSize, float rightWidth) {
    float headerHeight = min(headerMetrics.x, min(currentSize.y, endpointSize.y));
    if (headerHeight > 0.0 && point.y < headerHeight) {
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
    float p = clamp(progress, 0.0, 1.0);
    vec2 size = mix(sourceRect.zw, targetRect.zw, p);
    vec2 point = qt_TexCoord0 * size;
    vec4 oldPixels = texture(source, endpointUv(point, size, sourceRect.zw, headerMetrics.y));
    vec4 finalPixels = texture(targetSource, endpointUv(point, size, targetRect.zw, headerMetrics.z));
    // Complete the layout change before reaching the endpoint. At p=1 this
    // is the final scene at 1:1 scale, so revealing it cannot resize text.
    fragColor = mix(oldPixels, finalPixels, smoothstep(0.0, 0.85, p)) * qt_Opacity;
}
