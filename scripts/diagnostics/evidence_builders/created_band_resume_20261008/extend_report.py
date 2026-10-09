"""Append current allowlisted evidence; never publish local application values."""
import ctypes
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'scripts/diagnostics/evidence_builders/native_wait_20261008/created_band_report_constructor.py'
namespace = {'__file__': str(BASE), '__name__': 'preserved_evidence_helpers'}
source = BASE.read_text(encoding='utf-8')
exec(compile(source[:source.index('pop=[populated')], str(BASE), 'exec'), namespace)
contract = namespace['contract']
read, sha, window, row, trace = (namespace[x] for x in ('read', 'sha', 'window', 'row', 'trace'))
PUBLIC = ROOT / 'docs/CLEANROOM_CREATED_SOURCE_BAND_2026-10-08.json'
report = read(PUBLIC)

def creation(value, origin):
    out = {k: value[k] for k in ('version','byteSize','rowByteSize','hostGeneration','frameRevision',
        'enabled','strategy','strategyName','expectedTopmost','requestedStyle','requestedExStyle',
        'sourceValidated','creationAccepted','initializationAccepted','cleanupCompleted','hostRetained',
        'failureStage','createResult','createWin32Error','createElapsedMs','createLastErrorMeaningful')}
    out['rows'] = []
    for r in value['rows']:
        n, l = r['native'], r['live']
        item = dict(phase=r['phaseName'],flags=r['flags'],timeMs=round((r['seconds']-origin)*1000,6),
                    native=window(n,n,l),live=window(l,n,l))
        for side in ('native','live'):
            item[side+'ParentPresent'] = bool(r[side+'Parent'])
            item[side+'PrecedesLive'] = bool(l['window'] and r[side+'Next'] == l['window'])
            item[side+'FollowsLive'] = bool(l['window'] and r[side+'Previous'] == l['window'])
            item[side+'SameMonitorAsLive'] = bool(r['liveMonitor'] and r[side+'Monitor'] == r['liveMonitor'])
        out['rows'].append(item)
    return out

def current_run(p):
    d = read(p)
    commands = {r['cycle']:r for r in d['events'] if r['event']=='command'}
    first_origin = next(iter(commands.values()))['t']
    out = namespace['populated'](p)
    out['scope'] = 'Outside-sandbox disposable populated Qt/D3D11 desktop control; exact source/endpoint and input gates remain separate.'
    out['completedMovingDirections'] = d['completedCycles'] if not d['configuration']['source_observation_only'] else 0
    out['completedSourceControls'] = d['completedCycles'] if d['configuration']['source_observation_only'] else 0
    out['creationTelemetryLimit'] = 'Enabled before initialization; immediate creation/attachment/commit/visibility/lifecycle snapshots are measured.'
    out['timingReference'] = 'Creation, native-call and timing spans are relative to each host cycle command; preserved physical/source-transfer summaries use the first command.'
    out['nativeCallHistory'] = []  # Preserve one final bounded history per host, rather than duplicate snapshots.
    out['creationStates'], out['timings'], out['inputWitnesses'], out['endpointProbe'] = [], [], [], []
    final_traces, final_creations = {}, {}
    for e in d['events']:
        origin = commands.get(e['cycle'], {'t':first_origin})['t']
        if e['event']=='native-call-history':
            host = next(iter(e['rows']),{}).get('hostGeneration')
            final_traces[host] = (e,origin)
        elif e['event']=='native-host-creation-state':
            final_creations[e['hostGeneration']] = (e,origin)
        elif e['event']=='input-restoration-acceptance':
            out['inputWitnesses'].append({k:e.get(k) for k in ('cycle','status','reason','commandToAcceptedMs','inputReleaseToAcceptedMs')})
        elif e['event'] in ('target-gpu-composition-committed','target-render-import-rejected','input-restored','native-started','handoff-complete'):
            v = {k:e.get(k) for k in ('event','cycle','elapsedMs','importThread','nativeError','nativeEnabled','qmlInteractive')}
            v['commandMs'] = round((e['t']-origin)*1000,6)
            for k in ('importStarted','importFinished','started','finished'):
                if e.get(k) is not None: v[k+'Ms'] = round((e[k]-origin)*1000,6)
            out['timings'].append(v)
    for e,origin in final_traces.values():
        v = trace(e,origin)
        v['cycle'] = e['cycle']
        v['boundary'] = e['boundary']
        for k in ('hostDestroyed','hostRetained'):
            if k in e: v[k] = e[k]
        out['nativeCallHistory'].append(v)
    for e,origin in final_creations.values():
        v = creation(e,origin)
        v['cycle'] = e['cycle']
        out['creationStates'].append(v)
    # The pre-existing helper retains one outer creation return; all per-host creation state is above.
    return out

runs = sorted(ROOT.glob('logs/native_*_observed_*_20261008_run*/native_gpu_spike.json'))
runs += sorted(ROOT.glob('logs/native_*_ordered_*_20261008_run*/native_gpu_spike.json'))
report['currentPopulatedRuns'] = [current_run(p) for p in sorted(set(runs))]
report['currentNativeBuilds'] = []
for p in sorted((ROOT/'outputs/created_band_resume_20261008').glob('build*/manifest.json')):
    d = read(p)
    report['currentNativeBuilds'].append(dict(build=p.parent.name,dllSha256=d['dll']['Hash'].lower(),
        sourceHashes=d['sourceHashes'],sourceDrift=d['drift'],noWindowExit=d['noWindowExit'],
        manifestSha256=sha(p),manifestScope=d['scope']))
report['rejectedBuild'] = dict(build='build2',reason='Root added the placement snapshot while this build was running; source bracketing rejected it. No fixture used or DLL promoted from it.')
report['currentSyntheticRuns'] = []
for folder in sorted((ROOT/'outputs/created_band_resume_20261008').glob('sdk*')):
    if not (folder/'manifest.json').exists(): continue
    manifest = read(folder/'manifest.json')
    for run in manifest['runs']:
        p = folder/(run['name']+'.json')
        d = namespace['synthetic'](p)
        d['provenanceLimit'] = 'Contemporaneous executable/DLL/source hashes recorded; matched controls use this same binary and source.'
        d['dllSha256'] = manifest['dll']['Hash'].lower()
        d['executableSha256'] = manifest['exe']['Hash'].lower()
        d['sourceSha256'] = manifest['source']['Hash'].lower()
        d['exitCode'] = run['exit']
        for policy in d['policies']:
            suffix = 'topmost' if policy['topmostPolicy'] else 'ordinary'
            b = folder/(run['name']+'_'+suffix+'_creation.bin')
            if b.exists():
                value = contract._decode_creation(contract.NativeCreationObservation.from_buffer_copy(b.read_bytes()))
                policy['creation'] = creation(value,value['rows'][0]['seconds'])
                policy['creationBinarySha256'] = sha(b)
        report['currentSyntheticRuns'].append(d)
report['currentValidation'] = dict(safeRegressionPassed=784,realWindowDeselected=1,privacyTestsPassed=13,
    safeSuiteSha256=sha(ROOT/'outputs/native_wait_20261008/created_resume_final_full1/validation_summary.json'),
    scope='Sandbox-safe tests/source/ABI/compilation and no-window native contract; no WebEngine runtime.')
manifest = read(ROOT/'outputs/created_band_resume_20261008/sdk1/win32_current_manifest.json')
p = ROOT/'outputs/created_band_resume_20261008/sdk1/win32_current.json'
d = read(p)
control = {k:d[k] for k in ('schemaVersion','scope','relationEnum','gateDefinedBeforeRun','allCasesAccepted','foregroundUnchanged')}
control.update(rawResultSha256=sha(p),sourceSha256=manifest['source']['Hash'].lower(),
    executableSha256=manifest['exe']['Hash'].lower(),exitCode=manifest['exit'],cases=[])
for case in d['cases']:
    c = {k:case[k] for k in ('requestedTopmost','createdBand','accepted','hiddenGate','transferGate','cleanupGate','failure')}
    origin,frequency = case['calls'][0]['beginQpc'],d['qpcFrequency']
    c['calls'] = []
    for call in case['calls']:
        q = {k:call[k] for k in ('api','phase','insertion','result','immediateGetLastError','flags','guiCall','workerCall','before','after')}
        q.update(beginMs=(call['beginQpc']-origin)*1000/frequency,returnMs=(call['returnQpc']-origin)*1000/frequency,
            elapsedMs=(call['returnQpc']-call['beginQpc'])*1000/frequency)
        c['calls'].append(q)
    control['cases'].append(c)
report['currentPureWin32Control'] = control
report['status'] = 'CREATE-IN-BAND INITIALIZATION MEASURED; COMPLETE QUALIFICATION OPEN'
report['currentAggregate'] = dict(
    runs=len(report['currentPopulatedRuns']),
    completedMovingDirections=sum(r['completedMovingDirections'] for r in report['currentPopulatedRuns']),
    completedSourceControls=sum(r['completedSourceControls'] for r in report['currentPopulatedRuns']),
    freshPass=sum(o['status']=='PASS' for r in report['currentPopulatedRuns'] for o in r['freshObservations']),
    freshFail=sum(o['status']!='PASS' for r in report['currentPopulatedRuns'] for o in r['freshObservations']),
    exactComparisons=sum(o['differentPixels']==0 for r in report['currentPopulatedRuns'] for o in r['pixelComparisons']
        if not o['isDeliberateRemovalNegativeControl']),
    inputPass=sum(o['status']=='PASS' for r in report['currentPopulatedRuns'] for o in r['inputWitnesses']))
result = json.dumps(report,separators=(',',':'))+'\n'
assert len(result.encode()) < 4*1024*1024, 'Bounded public artifact exceeds scanner limit'
PUBLIC.write_text(result,encoding='utf-8')
print(json.dumps(report['currentAggregate']))
