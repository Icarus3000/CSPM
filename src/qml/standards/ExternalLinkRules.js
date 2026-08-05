.pragma library

function clean(value) {
    return String(value === undefined || value === null ? "" : value).trim()
}

function digits(value) {
    return clean(value).replace(/\D+/g, "")
}

function withScheme(url) {
    var raw = clean(url)
    if (raw.length <= 0) return ""
    if (raw.indexOf("http://") === 0 || raw.indexOf("https://") === 0 || raw.indexOf("file:") === 0) return raw
    return "https://" + raw
}

function cipoLookupUrl(applicationNumber, registrationNumber, trademarkText) {
    var lookup = digits(applicationNumber)
    if (lookup.length <= 0) lookup = digits(registrationNumber)
    var mark = clean(trademarkText)
    var query = mark.length > 0 ? mark.toLowerCase() : lookup
    var payload = {
        "domIntlFilter": "1",
        "searchfield1": "all",
        "textfield1": query,
        "display": "list",
        "maxReturn": "1000",
        "nicetextfield1": null,
        "cipotextfield1": null
    }
    var encodedPayload = encodeURIComponent(JSON.stringify(payload)).replace(/%20/g, "+")
    if (lookup.length > 0) {
        return "https://ised-isde.canada.ca/cipo/trademark-search/" + lookup
            + "?lang=eng&payload=" + encodedPayload
            + "&pageNum=0&pageLen=100"
    }
    if (query.length <= 0) {
        return "https://ised-isde.canada.ca/cipo/trademark-search/srch?lang=eng"
    }
    return "https://ised-isde.canada.ca/cipo/trademark-search/srch?lang=eng&payload=" + encodedPayload
}

function usptoLookupUrl(applicationNumber, registrationNumber) {
    var lookup = digits(applicationNumber)
    if (lookup.length <= 0) lookup = digits(registrationNumber)
    if (lookup.length > 0) {
        return "https://tsdr.uspto.gov/#caseNumber=" + lookup + "&caseSearchType=US_APPLICATION&caseType=DEFAULT&searchType=statusSearch"
    }
    return "https://tsdr.uspto.gov/"
}

function isCipoTrademarkSearchUrl(url) {
    var raw = clean(url).toLowerCase()
    return raw.indexOf("ised-isde.canada.ca/cipo/trademark-search/") >= 0
}

function isCipoSearchResultsUrl(url) {
    var raw = clean(url).toLowerCase()
    return raw.indexOf("ised-isde.canada.ca/cipo/trademark-search/srch") >= 0
}

function buildTrademarkRegistryUrl(jurisdiction, applicationNumber, registrationNumber, trademarkText, existingUrl) {
    var office = clean(jurisdiction).toUpperCase()
    var existing = clean(existingUrl)
    if (office === "USPTO") return usptoLookupUrl(applicationNumber, registrationNumber)
    if (office === "CIPO") return cipoLookupUrl(applicationNumber, registrationNumber, trademarkText)
    return withScheme(existing)
}

function openableTrademarkRegistryUrl(jurisdiction, applicationNumber, registrationNumber, trademarkText, existingUrl) {
    var office = clean(jurisdiction).toUpperCase()
    var existing = withScheme(existingUrl)
    if (office === "CIPO" && (existing.length <= 0 || isCipoSearchResultsUrl(existing))) {
        return cipoLookupUrl(applicationNumber, registrationNumber, trademarkText)
    }
    if (existing.length > 0) return existing
    return buildTrademarkRegistryUrl(jurisdiction, applicationNumber, registrationNumber, trademarkText, existing)
}

function shouldOpenInEdge(url) {
    return isCipoTrademarkSearchUrl(url)
}
