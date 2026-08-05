import QtQuick

QtObject {
    id: theme
    
    property bool isDark: typeof trayController !== "undefined" ? trayController.isDarkMode : false
    
    readonly property color background: isDark ? "#1E1E1E" : "#FFFFFF"
    readonly property color surface: isDark ? "#2D2D2D" : "#F4F6F8"
    readonly property color textPrimary: isDark ? "#E0E0E0" : "#0B1A30"
    readonly property color textSecondary: isDark ? "#A0A0A0" : "#637381"
    readonly property color accentTeal: isDark ? "#228B9E" : "#196472"
    readonly property color accentBlue: isDark ? "#4B88E5" : "#2065D1"
    readonly property color timerGreen: isDark ? "#21C47A" : "#118D57"
    readonly property color timerRed: isDark ? "#E64843" : "#B71D18"
    readonly property color border: isDark ? "#3E3E3E" : "#E5E8EB"
    readonly property color hover: isDark ? "#333333" : "#F4F6F8"
    
    readonly property int radiusLarge: 16
    readonly property int radiusMedium: 8
    readonly property int radiusSmall: 4
}
