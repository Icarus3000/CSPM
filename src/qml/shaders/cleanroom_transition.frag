#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix; float qt_Opacity; float clock; float transferStart;
    vec4 sourceRect; vec4 targetRect; vec4 headerMetrics;
    vec4 sourceCaptureUv; vec4 targetCaptureUv;
};
layout(binding = 1) uniform sampler2D source;
layout(binding = 2) uniform sampler2D targetSource;
float flow(float t) { t=clamp(t,0.0,1.0); return t*t*t*t*(35.0+t*(-84.0+t*(70.0-20.0*t))); }
vec2 mapEndpoint(vec2 point,vec2 size,vec2 endSize,float rightWidth) {
    float h=min(headerMetrics.x,min(size.y,endSize.y));
    if (h>0.0 && point.y>=0.0 && point.y<h && point.x>=0.0 && point.x<size.x) {
        float cap=min(rightWidth,min(size.x,endSize.x));
        float x=point.x>=size.x-cap ? endSize.x-(size.x-point.x) : min(point.x,max(0.0,endSize.x-cap-1.0));
        return vec2(x,point.y)/endSize;
    }
    return vec2(point.x/size.x,(h+(point.y-h)*(endSize.y-h)/max(1.0,size.y-h))/endSize.y);
}
void main() {
    if (clock<=0.0) { fragColor=texture(source,qt_TexCoord0)*qt_Opacity; return; }
    if (clock>=1.0) { fragColor=texture(targetSource,qt_TexCoord0)*qt_Opacity; return; }
    float p=flow(clock);
    vec2 size=mix(sourceRect.zw,targetRect.zw,p);
    vec4 uv=mix(sourceCaptureUv,targetCaptureUv,p);
    vec2 point=(qt_TexCoord0-uv.xy)*size/uv.zw;
    vec2 a=mapEndpoint(point,size,sourceRect.zw,headerMetrics.y);
    vec2 b=mapEndpoint(point,size,targetRect.zw,headerMetrics.z);
    float alpha=flow((clock-transferStart)/max(0.001,1.0-transferStart));
    fragColor=mix(texture(source,sourceCaptureUv.xy+a*sourceCaptureUv.zw),
        texture(targetSource,targetCaptureUv.xy+b*targetCaptureUv.zw),alpha)*qt_Opacity;
}
