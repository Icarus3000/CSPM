.pragma library

// Effective Item.visible includes invisible ancestors. Keep only the font
// scalar steady while hidden; visible items, including opacity-zero targets,
// use their current input immediately. The scalar belongs to the visual owner;
// this library keeps no QObject wrappers in a JavaScript collection. That
// avoids the QtQml access violation isolated by the matched font-off control.

function pixelSize(owner, value, enabled) {
    if (!owner || typeof owner.visible !== "boolean") return value
    if (!enabled || owner.visible) {
        // Do not read the cache in a visible font binding: doing so would
        // introduce a dependency on the scalar being published by that bind.
        try { owner.cspmHeldFontPixelSize = value } catch (error) { }
        return value
    }
    var held = owner.cspmHeldFontPixelSize
    if (typeof held !== "number") return value
    if (held < 0) {
        owner.cspmHeldFontPixelSize = value
        return value
    }
    return held
}
