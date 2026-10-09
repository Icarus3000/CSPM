.pragma library

// Effective Item.visible includes invisible ancestors. Keep only the font
// scalar steady while hidden; visible items, including opacity-zero targets,
// use their current input immediately. Weak ownership avoids retaining views.
var heldPixelSizes = new WeakMap()

function pixelSize(owner, value, enabled) {
    if (!enabled) {
        if (owner) heldPixelSizes.delete(owner)
        return value
    }
    if (!owner || typeof owner.visible !== "boolean") return value
    if (!owner.visible && heldPixelSizes.has(owner)) return heldPixelSizes.get(owner)
    heldPixelSizes.set(owner, value)
    return value
}
