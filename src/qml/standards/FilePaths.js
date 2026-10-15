.pragma library

// Qt dialogs return URLs. Preserve Linux's leading slash, Windows drive/UNC
// paths and literal filename characters instead of removing "file:///".
function localPath(value) {
    var raw = String(value || "")
    if (!/^file:/i.test(raw)) return raw
    var path = raw.substring(5)
    if (path.indexOf("//") === 0) {
        path = path.substring(2)
        if (/^localhost\//i.test(path)) path = path.substring(9)
        else if (path.charAt(0) !== "/") path = "//" + path
    }
    if (/^\/[A-Za-z]:\//.test(path)) path = path.substring(1)
    try { return decodeURIComponent(path) } catch (error) { return path }
}

function encodedPath(value) {
    return value.split("/").map(function(part, index) {
        return index === 0 && /^[A-Za-z]:$/.test(part) ? part : encodeURIComponent(part)
    }).join("/")
}

function fileUrl(value) {
    var path = String(value || "").trim().replace(/\\/g, "/")
    if (!path || /^file:/i.test(path)) return path
    if (path.indexOf("//") === 0) return "file:" + encodedPath(path)
    if (path.charAt(0) === "/") return "file://" + encodedPath(path)
    if (/^[A-Za-z]:\//.test(path)) return "file:///" + encodedPath(path)
    return encodedPath(path)
}

function suggestedFile(folderUrl, fileName) {
    var folder = String(folderUrl || "").replace(/\/$/, "")
    return folder ? folder + "/" + encodeURIComponent(String(fileName || ""))
                  : encodeURIComponent(String(fileName || ""))
}
