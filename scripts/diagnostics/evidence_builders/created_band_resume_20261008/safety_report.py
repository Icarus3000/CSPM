"""Allowlist existing QML safety lifecycle metadata, never application content."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
controls = []
for label in ('existing_reduced_lifecycle_20261008_run1','existing_selector_fallback_lifecycle_20261008_run1'):
    folder = ROOT/'outputs/created_band_resume_20261008'/label
    raw = ROOT/'logs'/label
    summary,command = read(folder/'summary.json'),read(folder/'command.json')
    frames,window = read(raw/'cleanroom_frames.json'),read(raw/'window_transition_results.json')
    baseline = next(r['activeTab'] for r in window['results'] if r['label']=='cycle 0')
    out = dict(run=label,mode=summary['mode'],exitCode=summary['exitCode'],
        reducedMotionEnvironment=command['environment']['CSPM_EXPERIMENTAL_REDUCED_MOTION'],
        scope=summary['scope'],failures=frames['failures'],windowFailures=window['failures'],
        protectedUnchanged=summary['protectedUnchanged'],sourceDrift=summary['sourceDrift'],
        summarySha256=sha(folder/'summary.json'),framesSha256=sha(raw/'cleanroom_frames.json'),
        windowResultSha256=sha(raw/'window_transition_results.json'),
        sourceHashes=summary['sourceHashes'],primaryDirections=sum(r['primary'] for r in frames['runs']),
        totalDirectionCommands=len(frames['runs']),observedSurfaceFrameRows=len(frames['frames']),
        archivedSurfaceTraceCount=len(frames['surfaceTraces']),
        physicalContinuity=summary['result']['physicalContinuity'],
        nativeBridgeReducedAndFailureRecovery=summary['nativeBridgeReducedAndFailureRecovery'],
        runs=[],snapshots=[])
    for r in frames['runs']:
        out['runs'].append({k:r[k] for k in ('index','primary','kind','engine','sourceRect','targetRect','exactGeometry')})
    for r in window['results']:
        snapshot = {k:r[k] for k in ('label','style','margins','frame','nativeClient','zoomed','qtGeometry',
            'flags','nativeOwner','uiMaximized','final','canvas','radius','overlay','nativeMinimized','nativeVisible','qtVisibility')}
        snapshot['workspaceMatchesFirstTransition'] = r['activeTab']==baseline if r['label']!='startup' else None
        out['snapshots'].append(snapshot)
    log = (raw/'runtime/cspm.log').read_text(encoding='utf-8')
    out['reducedDirectSettlementLogCount'] = log.count('experimental-reduced-motion')
    out['unavailableNativeFallbackLogCount'] = log.count('Clean-room native composition engine unavailable')
    constructor = folder/'constructor_manifest.json'
    if constructor.exists():
        out['constructor'] = {k:v for k,v in read(constructor).items() if k in ('originalRelativePath',
            'originalSha256','constructorSha256','executedSha256','replacementCount','change','executionFileContext','scope')}
    controls.append(out)
target = ROOT/'docs/CLEANROOM_CREATED_BAND_SAFETY_2026-10-08.json'
target.write_text(json.dumps(dict(schemaVersion=1,recordedDate='2026-10-08',controls=controls,
    scope='Outside-sandbox existing QML reduced and selector-unavailable fallback lifecycle; no native bridge integration or physical input/continuity proof.'),separators=(',',':'))+'\n',encoding='utf-8')
print(json.dumps([dict(mode=c['mode'],exitCode=c['exitCode'],commands=c['totalDirectionCommands'],
    frames=c['observedSurfaceFrameRows'],failures=c['failures'],protected=c['protectedUnchanged'],
    reducedLogCount=c['reducedDirectSettlementLogCount'],fallbackLogCount=c['unavailableNativeFallbackLogCount']) for c in controls]))
