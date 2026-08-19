from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _function_body(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start)
    return source[start:end]


def test_native_splash_never_shows_the_main_host_during_progress() -> None:
    bootstrap = (ROOT / "src" / "qml" / "BootstrapRoot.qml").read_text(encoding="utf-8")
    shell = (ROOT / "src" / "qml" / "DetachedShellWindow.qml").read_text(encoding="utf-8")
    main_py = (ROOT / "src" / "python" / "main.py").read_text(encoding="utf-8")

    prestage = _function_body(
        bootstrap,
        "    function prestageCinematicBloom() {",
        "    // main.py calls this only after the native plasma",
    )
    assert "retaining visible:false until native plasma handoff" in prestage
    assert '_openLaunchGate("phase2-native-prestage")' not in prestage
    assert "cinematicBloomPrestageComplete()" in prestage

    release = _function_body(
        bootstrap,
        "    function releaseCinematicLaunchGate() {",
        "    function _bindPhaseOneMainWindow(windowRef) {",
    )
    assert '_openLaunchGate("phase2-native-handoff")' in release

    launch = _function_body(
        shell,
        "    function startProfessionalLaunchNow() {",
        "    NumberAnimation {\n        id: startupCinematicBloomAnimation",
    )
    bloom_scale = launch.index("mainWin.startupCinematicBloomScale = 0.002;")
    bloom_active = launch.index("mainWin.startupCinematicBloomActive = true;")
    show_host = launch.index("mainWin.show();")
    raise_host = launch.index("mainWin.raise();", show_host)
    focus_host = launch.index("mainWin.forceLaunchFocus();", show_host)
    assert bloom_scale < show_host
    assert bloom_active < show_host
    assert show_host < raise_host < focus_host

    finish = _function_body(
        main_py,
        "    def _finish_cinematic_to_bloom(self) -> None:",
        "    def _emit_cinematic_reveal_after_splash_hidden(self) -> None:",
    )
    assert "self.hide()" in finish
    assert "_NATIVE_SPLASH_HANDOFF_DELAY_MS" in finish
    assert "self.cinematicRevealReady.emit()" not in finish
    assert "def _emit_cinematic_reveal_after_splash_hidden(self) -> None:" in main_py
    assert "QTimer.singleShot(0, _restore_main_foreground_after_native_splash)" in main_py
