pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import "../standards/SemanticTheme.js" as SemanticTheme

Window {
    id: root

    title: "Report Branding"
    visible: false
    modality: Qt.NonModal
    width: 800
    height: 600
    minimumWidth: 720
    minimumHeight: 520

    property var parentWindow: null
    property var t
    property string appStyle: "Professional"
    property var metrics
    property var appRef: null
    property var sfxBus: null
    property var profiles: []
    property var profileNames: []
    property string selectedProfileId: ""
    property string statusText: ""
    property bool dirty: false
    signal brandingChanged()

    property color menuSurface: SemanticTheme.surface(root.t, "popup", "neutral")
    property color menuInk: SemanticTheme.ink(root.t, "popup", "neutral")
    property color menuBorder: SemanticTheme.border(root.t, "popup", "neutral")
    property color accent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property color hoverFill: SemanticTheme.alpha(root.menuInk, 0.08)
    property color inactiveFill: SemanticTheme.alpha(root.menuInk, 0.05)
    property color activeFill: (SemanticTheme.luma(root.accent) > 0.70)
        ? Qt.darker(root.accent, 1.14)
        : root.accent
    property color activeInk: SemanticTheme.readableInk(root.activeFill)

    function open() {
        visible = true
    }

    function close() {
        visible = false
    }

    Shortcut {
        sequence: "Escape"
        onActivated: root.close()
    }

    onVisibleChanged: {
        var p = root.parentWindow
        if (visible && p) {
            root.x = p.x + Math.max(0, (p.width - root.width) / 2)
            if (p.reportId !== undefined) {
                root.y = p.y + Math.max(0, Math.round((p.height - root.height) * 0.22))
            } else {
                root.y = p.y + Math.max(0, (p.height - root.height) / 2)
            }
        }
    }

    onClosing: function(close) {
        if (root.dirty) {
            close.accepted = false
            closeConfirmPopup.open()
        } else {
            close.accepted = true
        }
    }


    function _safeText(value) {
        return String(value === undefined || value === null ? "" : value)
    }

    function _profileId(profile) {
        return _safeText(profile && (profile.id || profile.profileId)).trim()
    }

    function _profileIndexById(profileId) {
        var target = _safeText(profileId).trim()
        for (var i = 0; i < profiles.length; i++) {
            if (_profileId(profiles[i]) === target) return i
        }
        return -1
    }

    function _profileNames(profilesPayload) {
        var names = []
        for (var i = 0; i < profilesPayload.length; i++) {
            names.push(_safeText(profilesPayload[i].name || profilesPayload[i].firmName || ("Profile " + String(i + 1))))
        }
        return names
    }

    function _currentProfile() {
        var index = _profileIndexById(selectedProfileId)
        if (index >= 0) return profiles[index]
        return profiles.length > 0 ? profiles[0] : ({})
    }

    function _setProfiles(result, preferredId) {
        var nextProfiles = result && result.profiles ? result.profiles : []
        profiles = nextProfiles
        profileNames = _profileNames(nextProfiles)
        var nextId = _safeText(preferredId || (result && result.lastProfileId)).trim()
        if (nextId.length <= 0 && nextProfiles.length > 0) nextId = _profileId(nextProfiles[0])
        if (_profileIndexById(nextId) < 0 && nextProfiles.length > 0) nextId = _profileId(nextProfiles[0])
        selectedProfileId = nextId
        _populateFields()
    }

    function openWithProfiles() {
        loadProfiles()
        open()
    }

    function loadProfiles() {
        if (!appRef || !appRef.getReportBrandingProfiles) {
            statusText = "Report branding backend unavailable."
            return
        }
        var result = null
        try {
            result = appRef.getReportBrandingProfiles()
        } catch (e) {
            result = { "ok": false, "message": String(e), "profiles": [] }
        }
        _setProfiles(result, result ? result.lastProfileId : "")
        statusText = result && result.ok === false
            ? _safeText(result.message || "Could not load profiles.")
            : "Ready."
    }

    function _populateFields() {
        var profile = _currentProfile()
        var address = profile.addressLines || []
        profileNameField.text = _safeText(profile.name)
        firmNameField.text = _safeText(profile.firmName)
        subtitleField.text = _safeText(profile.subtitle || profile.firmSubtitle)
        addressLine1Field.text = address.length > 0 ? _safeText(address[0]) : ""
        addressLine2Field.text = address.length > 1 ? _safeText(address[1]) : ""
        phoneField.text = _safeText(profile.phone)
        emailField.text = _safeText(profile.email)
        logoPathField.text = _safeText(profile.logoPath)
        root.dirty = false
    }

    function _payloadFromFields(includeId) {
        var profile = _currentProfile()
        var profileId = includeId === false ? "" : _safeText(selectedProfileId).trim()
        if (profileId.length <= 0 && includeId !== false) profileId = _profileId(profile)
        return {
            "id": profileId,
            "profileId": profileId,
            "name": profileNameField.text,
            "firmName": firmNameField.text,
            "subtitle": subtitleField.text,
            "addressLines": [addressLine1Field.text, addressLine2Field.text],
            "phone": phoneField.text,
            "email": emailField.text,
            "logoPath": logoPathField.text
        }
    }

    function saveCurrent() {
        if (!appRef || !appRef.saveReportBrandingProfile) {
            statusText = "Report branding backend unavailable."
            return false
        }
        var result = null
        try {
            result = appRef.saveReportBrandingProfile(_payloadFromFields(true))
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        if (result && result.ok) {
            var nextId = result.profile ? _profileId(result.profile) : _safeText(result.lastProfileId)
            _setProfiles(result, nextId)
            statusText = "Profile saved."
            root.dirty = false
            root.brandingChanged()
            return true
        }
        statusText = "Save failed: " + _safeText(result && result.message ? result.message : "Unknown error")
        return false
    }

    function createProfile() {
        if (!appRef || !appRef.saveReportBrandingProfile) {
            statusText = "Report branding backend unavailable."
            return
        }
        profileNameField.text = "New Report Profile"
        firmNameField.text = "New Firm"
        subtitleField.text = ""
        addressLine1Field.text = ""
        addressLine2Field.text = ""
        phoneField.text = ""
        emailField.text = ""
        logoPathField.text = ""
        selectedProfileId = ""
        var result = null
        try {
            result = appRef.saveReportBrandingProfile(_payloadFromFields(false))
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        if (result && result.ok) {
            _setProfiles(result, result.profile ? _profileId(result.profile) : "")
            statusText = "Profile created."
            root.dirty = false
            root.brandingChanged()
        } else {
            statusText = "Create failed: " + _safeText(result && result.message ? result.message : "Unknown error")
        }
    }

    function duplicateProfile() {
        if (!appRef || !appRef.saveReportBrandingProfile) {
            statusText = "Report branding backend unavailable."
            return
        }
        var profile = _currentProfile()
        profileNameField.text = (_safeText(profile.name || "Report Profile") + " Copy").trim()
        var result = null
        try {
            result = appRef.saveReportBrandingProfile(_payloadFromFields(false))
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        if (result && result.ok) {
            _setProfiles(result, result.profile ? _profileId(result.profile) : "")
            statusText = "Profile duplicated."
            root.dirty = false
            root.brandingChanged()
        } else {
            statusText = "Duplicate failed: " + _safeText(result && result.message ? result.message : "Unknown error")
        }
    }

    function deleteCurrent() {
        if (!appRef || !appRef.deleteReportBrandingProfile) {
            statusText = "Report branding backend unavailable."
            return
        }
        var target = selectedProfileId
        var result = null
        try {
            result = appRef.deleteReportBrandingProfile(target)
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        if (result && result.ok) {
            _setProfiles(result, result.lastProfileId)
            statusText = "Profile deleted."
            root.dirty = false
            root.brandingChanged()
        } else {
            statusText = _safeText(result && result.message ? result.message : "Delete failed.")
        }
    }

    function importLogo(fileUrl) {
        if (selectedProfileId.length <= 0 && !saveCurrent()) return
        if (!appRef || !appRef.importReportBrandingLogo) {
            statusText = "Report branding backend unavailable."
            return
        }
        var result = null
        try {
            result = appRef.importReportBrandingLogo(selectedProfileId, fileUrl)
        } catch (e) {
            result = { "ok": false, "message": String(e) }
        }
        if (result && result.ok) {
            _setProfiles(result, result.profile ? _profileId(result.profile) : result.lastProfileId)
            statusText = "Logo imported."
            root.dirty = false
            root.brandingChanged()
        } else {
            statusText = "Logo import failed: " + _safeText(result && result.message ? result.message : "Unknown error")
        }
    }

    function clearLogo() {
        logoPathField.text = ""
        saveCurrent()
    }

    FileDialog {
        id: logoDialog
        title: "Choose Report Branding Logo"
        nameFilters: ["Logo/Image files (*.svg *.png *.jpg *.jpeg)", "All files (*)"]
        onAccepted: root.importLogo(selectedFile.toString())
    }

    SemanticPanel {
        anchors.fill: parent
        t: root.t
        role: "popup"
        tone: "neutral"
        radius: 0
        borderWidth: 0
        shadowRadius: 0
        shadowSamples: 0

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: "Report Branding"
                color: root.menuInk
                font.pixelSize: 22
                font.bold: true
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            Button {
                text: "Close"
                Layout.preferredWidth: 88
                onClicked: root.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: SemanticTheme.alpha(root.menuInk, 0.14)
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "Profile"
                color: root.menuInk
                font.pixelSize: 13
                font.bold: true
                Layout.preferredWidth: 72
                verticalAlignment: Text.AlignVCenter
            }

            ComboBox {
                id: profileCombo
                Layout.fillWidth: true
                model: root.profileNames
                currentIndex: root._profileIndexById(root.selectedProfileId)
                onActivated: function(index) {
                    var profile = root.profiles[index] || ({})
                    root.selectedProfileId = root._profileId(profile)
                    if (root.appRef && root.appRef.setLastReportBrandingProfile) {
                        root.appRef.setLastReportBrandingProfile(root.selectedProfileId)
                    }
                    root._populateFields()
                }
            }

            Button { text: "New"; Layout.preferredWidth: 78; onClicked: root.createProfile() }
            Button { text: "Duplicate"; Layout.preferredWidth: 104; onClicked: root.duplicateProfile() }
            Button { text: "Delete"; Layout.preferredWidth: 86; onClicked: root.deleteCurrent() }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 12
            rowSpacing: 8

            Text { text: "Profile Name"; color: root.menuInk; font.bold: true }
            TextField { id: profileNameField; Layout.fillWidth: true; placeholderText: "CS Law"; onTextEdited: root.dirty = true }

            Text { text: "Firm Name"; color: root.menuInk; font.bold: true }
            TextField { id: firmNameField; Layout.fillWidth: true; placeholderText: "Cory Schneider Law Office"; onTextEdited: root.dirty = true }

            Text { text: "Subtitle"; color: root.menuInk; font.bold: true }
            TextField { id: subtitleField; Layout.fillWidth: true; placeholderText: "Practice Management"; onTextEdited: root.dirty = true }

            Text { text: "Address Line 1"; color: root.menuInk; font.bold: true }
            TextField { id: addressLine1Field; Layout.fillWidth: true; placeholderText: "Street address"; onTextEdited: root.dirty = true }

            Text { text: "Address Line 2"; color: root.menuInk; font.bold: true }
            TextField { id: addressLine2Field; Layout.fillWidth: true; placeholderText: "City, province/state, postal code"; onTextEdited: root.dirty = true }

            Text { text: "Phone"; color: root.menuInk; font.bold: true }
            TextField { id: phoneField; Layout.fillWidth: true; placeholderText: "Phone"; onTextEdited: root.dirty = true }

            Text { text: "Email"; color: root.menuInk; font.bold: true }
            TextField { id: emailField; Layout.fillWidth: true; placeholderText: "Email"; onTextEdited: root.dirty = true }

            Text { text: "Logo"; color: root.menuInk; font.bold: true }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: logoPathField
                    Layout.fillWidth: true
                    readOnly: true
                    placeholderText: "No logo"
                }
                Button { text: "Choose"; Layout.preferredWidth: 90; onClicked: logoDialog.open() }
                Button { text: "Clear"; Layout.preferredWidth: 76; onClicked: root.clearLogo() }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            spacing: 12
            visible: logoPathField.text.trim().length > 0

            Text {
                text: "Logo Preview"
                color: root.menuInk
                font.bold: true
                Layout.preferredWidth: 90
                verticalAlignment: Text.AlignVCenter
            }

            Rectangle {
                Layout.preferredWidth: 64
                Layout.preferredHeight: 64
                color: SemanticTheme.alpha(root.menuInk, 0.04)
                border.width: 1
                border.color: SemanticTheme.alpha(root.menuInk, 0.12)
                radius: 4
                clip: true

                Image {
                    anchors.fill: parent
                    anchors.margins: 4
                    source: {
                        var path = logoPathField.text.trim()
                        if (path.length <= 0) return ""
                        if (path.indexOf("file://") === 0 || path.indexOf("qrc:/") === 0) {
                            return path
                        }
                        var cleanPath = path.replace(/\\/g, "/")
                        if (cleanPath.match(/^[a-zA-Z]:/)) {
                            return "file:///" + cleanPath
                        }
                        return "file://" + cleanPath
                    }
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                }
            }

            Item { Layout.fillWidth: true }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            color: root.inactiveFill
            radius: 6

            Text {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                text: root.statusText
                color: root.menuInk
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Item { Layout.fillWidth: true }
            Button {
                text: "Reload"
                Layout.preferredWidth: 96
                onClicked: root.loadProfiles()
            }
            Button {
                text: "Save"
                Layout.preferredWidth: 112
                highlighted: true
                onClicked: root.saveCurrent()
            }
        }
    }

    Popup {
        id: closeConfirmPopup
        modal: true
        focus: true
        anchors.centerIn: parent
        width: 360
        height: 160
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: root.menuSurface
            border.color: root.menuBorder
            border.width: 1
            radius: 8
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 14

            Text {
                text: "Unsaved Changes"
                color: root.menuInk
                font.pixelSize: 16
                font.bold: true
                Layout.fillWidth: true
            }

            Text {
                text: "Would you like to save your report branding changes before closing?"
                color: root.menuInk
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Item { Layout.fillWidth: true }

                Button {
                    text: "Cancel"
                    Layout.preferredWidth: 76
                    onClicked: closeConfirmPopup.close()
                }

                Button {
                    text: "Don't Save"
                    Layout.preferredWidth: 92
                    onClicked: {
                        closeConfirmPopup.close()
                        root.dirty = false
                        root.close()
                    }
                }

                Button {
                    text: "Save"
                    Layout.preferredWidth: 76
                    highlighted: true
                    onClicked: {
                        closeConfirmPopup.close()
                        if (root.saveCurrent()) {
                            root.dirty = false
                            root.close()
                        }
                    }
                }
            }
        }
    }
}
}
