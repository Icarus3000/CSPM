"""Local evidence constructor; publishes only allowlisted relational evidence."""
import collections
import ctypes
import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/CLEANROOM_CREATED_SOURCE_BAND_2026-10-08.json'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

spec = importlib.util.spec_from_file_location('call_contract', ROOT / 'scripts/diagnostics/native_call_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

ROW_KEYS = ('sequence','callName','phaseName','elapsedMs','result','returnHex','win32Error',
    'lastErrorApplicable','lastErrorMeaningful','timeoutMs','resultMeaning','terminalFailure',
    'beforeMotion','flagsBefore','flagsAfter','hostGeneration','sourceGeneration','targetGeneration',
    'expectedHostGeneration','expectedSourceGeneration','expectedTargetGeneration','commitBefore',
    'commitAfter','expectedPresentId','submittedBefore','submittedAfter','displayedBefore','displayedAfter',
    'statisticsHRESULT','bufferIndex','bufferCount','waitStateBeforeName','waitStateAfterName',
    'keyedMutexStateName','generationsMatch','diagnosticMetadataOverheadMs','physicalPresentationProven')

def window(w, native, live):
    return {
        **{k:w.get(k) for k in ('valid','visible','iconic','zoomed','cloaked','cloakHRESULT','style','exstyle',
                              'queryErrors','windowRect','clientRect','workRect','dpi')},
        'ownerPresent': bool(w.get('owner')),
        'foregroundIsLive': bool(live.get('window') and w.get('foreground') == live['window']),
        'foregroundIsNative': bool(native.get('window') and w.get('foreground') == native['window']),
        'focusIsLive': bool(live.get('window') and w.get('focus') == live['window']),
        'activeIsLive': bool(live.get('window') and w.get('active') == live['window']),
        'sameProcessAsLive': bool(w.get('process') and w.get('process') == live.get('process')),
        'sameThreadAsLive': bool(w.get('thread') and w.get('thread') == live.get('thread')),
        'topmost': bool(w.get('exstyle',0)&8),
    }

def row(r, origin):
    out = {k:r[k] for k in ROW_KEYS if k in r}
    out.update(beginMs=round((r['beginSeconds']-origin)*1000,6),returnMs=round((r['returnSeconds']-origin)*1000,6),
        callerIsGui=r['currentThread']==r['guiThread'],callerIsWorker=r['currentThread']==r['workerThread'])
    for side in ('Before','After'):
        n,l=r['native'+side],r['live'+side]
        for name,w in [('native',n),('live',l)]:out[name+side]=window(w,n,l)
    out['foregroundUnchanged']=r['nativeBefore']['foreground']==r['nativeAfter']['foreground']
    return out

def trace(t,origin):
    out={k:t[k] for k in ('version','byteSize','rowByteSize','enabled','totalRows','droppedRows','truncated')}
    out['callCounts']=dict(collections.Counter(r['callName'] for r in t['rows']))
    out['rows']=[row(r,origin) for r in t['rows']]
    out['firstFailure']=row(t['firstFailure'],origin) if t.get('firstFailure') else None
    return out

def provenance(s):
    return {'git':{k:s.get('git',{}).get(k) for k in ('head','branch','workingTreeClean')},
        'startupSourceCount':len(s['sources']),
        'startupSourceHashes':[{ 'sourceOrdinal':i+1,'sha256':v.lower()} for i,(k,v) in enumerate(sorted(s['sources'].items()))],
        'mappingScope':'Stable ordinals follow sorted repository source identifiers; private mirror/evidence paths omitted.'}

def populated(p):
    d=read(p);events=d['events'];origin=next(e['t'] for e in events if e['event']=='command')
    c=d['configuration'];r={'run':p.parent.name,'rawResultSha256':sha(p),'dllSha256':d['dllHash'],
        'scope':'Outside-sandbox populated Qt/D3D11 source-only desktop control; no moving target or WebEngine qualification',
        'configuration':{k:c.get(k) for k in ('cycles','duration_ms','blend_start_ms','gui_delay_ms','endpoint_hold_ms',
            'prepared_target','source_observation_only','source_unlocked','single_owner_source','native_created_source_band',
            'native_call_trace','source_transfer_trace','preserve_foreground','input_witness','input_trace','workspace',
            'first_direction','layout_repair','activation_repair','restored_size')},
        'provenance':provenance(d['sourceProvenance']),'completedSourceControls':d['completedCycles'],
        'completedMovingDirections':0,'failures':d['failures'],'coldCandidateQualification':d['coldCandidateQualification'],
        'freshObservations':[],'pixelComparisons':[],'sourceTransfer':[],'nativeCallHistory':[],'inputRestoration':[],
        'creationTelemetryLimit':'Historical native trace enabled after construction; creation return is recorded but immediate create, attachment and commit band snapshots are not independently bracketed.'}
    for e in events:
        kind=e['event']
        if kind=='desktop-observation':
            r['freshObservations'].append({k:e.get(k) for k in ('label','status','reason','polls','comparisonRectangleXYWH')})
        elif kind=='physical-pixel-analysis':
            q={k:e.get(k) for k in ('comparison','status','pixels','differentPixels','mismatchBoundsLTRB')}
            q['isDeliberateRemovalNegativeControl']=e['comparison']=='source-gpu-to-native-removed-pixels'
            q['regions']={k:{z:v[z] for z in ('pixels','differentPixels') if z in v} for k,v in e['regions'].items()}
            assert sum(v['pixels'] for v in q['regions'].values())==q['pixels']
            assert sum(v['differentPixels'] for v in q['regions'].values())==q['differentPixels']
            r['pixelComparisons'].append(q)
        elif kind=='source-transfer-boundary':
            ob=e['observation'];z={k:ob[k] for k in ('stage','accepted','win32Error','expectedTopmost','sameParent','sameProcess',
                'liveThreadOwned','nativeThreadOwned','liveForegroundEntry','liveForegroundExit','liveOwnerRelation',
                'nativeOwnerRelation','liveStyleEntry','nativeStyleEntry','liveStyleExit','nativeStyleExit','liveVisibleEntry',
                'nativeVisibleEntry','liveVisibleExit','nativeVisibleExit','beginAccepted','liveDeferAccepted',
                'nativeDeferAccepted','endAccepted','policySampled')}
            z.update(apiBeginMs=round((e['apiBeginSeconds']-origin)*1000,6),apiReturnMs=round((e['apiReturnSeconds']-origin)*1000,6))
            z['messages']=[{**{k:m[k] for k in ('sequence','message','phase','insertAfterBandBefore','insertAfterBandAfter',
                'flagsBefore','flagsAfter','styleBefore','styleAfter','expectedTopmost','visibleAfter')},
                'timeMs':round((m['timeSeconds']-origin)*1000,6)} for m in e['messages']]
            r['sourceTransfer'].append(z)
        elif kind=='native-call-history':
            q=trace(e,origin);q['boundary']=e['boundary']
            for k in ('hostDestroyed','hostRetained'):
                if k in e:q[k]=e[k]
            r['nativeCallHistory'].append(q)
        elif kind=='input-restored':r['inputRestoration'].append({k:e[k] for k in ('nativeEnabled','qmlInteractive')})
        elif kind=='native-host-created':
            r['creationReturn']={k:e[k] for k in ('accepted','createdSourceBand','nativeError')}
            r['creationReturn'].update(beginMs=round((e['apiBeginSeconds']-origin)*1000,6),returnMs=round((e['apiReturnSeconds']-origin)*1000,6))
    start,end=p.parent/'protected_hashes_start.json',p.parent/'protected_hashes.json'
    if start.exists() and end.exists():
        r['protectedManifestSha256']={'start':sha(start),'end':sha(end)}
        a,b=read(start),read(end)
        r['protectedManifestStartEndEquality']=a==b.get('before')==b.get('after')
        r['protectedHashes']=[{'artifactOrdinal':i+1,'sha256':v} for i,(k,v) in enumerate(sorted(a.items()))]
    return r

POLICY_KEYS=('topmostPolicy','accepted','stage','foregroundFalse','foregroundUnchanged','cleanupForegroundUnchanged',
    'liveHidden','nativeVisible','bandMatches','markerSamples','markerMismatchCount','liveStyleEntry','liveStyleExit',
    'nativeStyleEntry','nativeStyleExit','sameProcess','sameParent','liveThreadOwned','nativeThreadOwned','expectedTopmost',
    'setupCall','setupResult','setupWin32Error','setupStyleBefore','setupStyleAfter','setupBandMatches',
    'setupForegroundUnchanged','setupAccepted','guardUsed','nativeCallTraceEnabled','destroyStatus',
    'nativeCallCount','nativeCallTotal','nativeCallDropped','firstFailureCall','firstFailureResult','firstFailureWin32Error')

def synthetic(p):
    raw=p.read_text();prefix=''
    try:d=json.loads(raw)
    except json.JSONDecodeError:
        prefix,body=raw.split('\n',1)
        # The earliest partial result lacks its enclosing closing array/object.
        d=json.loads(body.rstrip()+']}')
    r={'run':p.stem,'rawResultSha256':sha(p),'scope':'Outside-sandbox SDK-only Win32/D3D11 synthetic GPU control; no Qt/desktop observer/WebEngine',
        'rawSerialization':'failure-prefixed incomplete JSON fragment' if prefix else 'complete JSON',
        'retainedFailure':prefix or None,'allPoliciesPass':d.get('allPoliciesPass',False),
        'createdLiveBand':d.get('createdLiveBand',False),'createdNativeBand':d.get('createdNativeBand',False),
        'guardRequested':d.get('guardRequested'),'provenanceLimit':'Historical result does not record contemporaneous DLL hash, source map, Git state or executable build bracket.',
        'policies':[]}
    for q in d['policies']:
        v={k:q[k] for k in POLICY_KEYS if k in q}
        v['windowPositions']=q['windowPositions']
        if 'setupBeginSeconds' in q:
            v['setupElapsedMs']=round((q['setupReturnSeconds']-q['setupBeginSeconds'])*1000,6)
        v['setupRejectedBeforeTransfer']=q.get('setupAccepted') is False
        # Pre-setup rejection leaves relation fields zero-initialized and unmeasured.
        v['relationFieldsMeasured']=not v['setupRejectedBeforeTransfer']
        band='topmost' if q['topmostPolicy'] else 'ordinary'
        name=p.stem.removesuffix('_result')+'_'+band+'_native_calls.bin'
        b=p.parent/name
        if b.exists():
            binary=b.read_bytes();assert len(binary)==ctypes.sizeof(contract.NativeCallTrace)
            decoded=contract._decode_trace(contract.NativeCallTrace.from_buffer_copy(binary))
            origin=decoded['rows'][0]['beginSeconds'];v['traceRawSha256']=sha(b);v['trace']=trace(decoded,origin)
        r['policies'].append(v)
    return r

def bracket(prefix):
    base=ROOT/'outputs/native_wait_20261008';a,b=read(base/(prefix+'_before.json')),read(base/(prefix+'_after.json'))
    aa=a if isinstance(a,list) else a['inputs'];bb=b if isinstance(b,list) else b['inputs']
    shared={x['Path']:x['Hash'].lower() for x in aa};post={x['Path']:x['Hash'].lower() for x in bb}
    dll=[x['Hash'].lower() for x in bb if x['Path'].lower().endswith('.dll')]
    if not dll and isinstance(b,dict):dll=[b['dll']['Hash'].lower()]
    return {'beforeManifestSha256':sha(base/(prefix+'_before.json')),'afterManifestSha256':sha(base/(prefix+'_after.json')),
        'nativeSourceSha256':next(v for k,v in shared.items() if k.endswith('cleanroom_composition.cpp')),
        'buildScriptSha256':next(v for k,v in shared.items() if k.endswith('build_cleanroom_native.ps1')),
        'inputsUnchanged':all(post.get(k)==v for k,v in shared.items()),'dllSha256':dll[0]}

def win32_control():
    base=ROOT/'outputs/created_band_resume/win32_control1';p=base/'result.json'
    d=read(p);before,after=read(base/'source_before.json'),read(base/'source_binary_result_after.json')
    r={k:d[k] for k in ('schemaVersion','scope','relationEnum','gateDefinedBeforeRun','allCasesAccepted','foregroundUnchanged')}
    r.update(rawResultSha256=sha(p),sourceSha256=before['Hash'].lower(),
        sourceBracketUnchanged=before['Hash']==after[0]['Hash'],executableSha256=after[1]['Hash'].lower(),
        buildLogSha256=sha(base/'build.log'),exitCode=read(base/'execution.json')['exitCode'],cases=[])
    for case in d['cases']:
        c={k:case[k] for k in ('requestedTopmost','createdBand','accepted','hiddenGate','transferGate','cleanupGate','failure')}
        origin=case['calls'][0]['beginQpc'];freq=d['qpcFrequency'];c['calls']=[]
        for call in case['calls']:
            q={k:call[k] for k in ('api','phase','insertion','result','immediateGetLastError','flags','guiCall','workerCall','before','after')}
            q.update(beginMs=(call['beginQpc']-origin)*1000/freq,returnMs=(call['returnQpc']-origin)*1000/freq,
                elapsedMs=(call['returnQpc']-call['beginQpc'])*1000/freq)
            c['calls'].append(q)
        r['cases'].append(c)
    return r

pop=[populated(ROOT/'logs'/n/'native_gpu_spike.json') for n in (
    'native_wait_source_guarded_20261008_run1','native_wait_source_unlocked_20261008_run1',
    'native_wait_created_source_guarded_20261008_run1')]
sdk=[synthetic(ROOT/'outputs/native_wait_20261008/sdk1'/n) for n in (
    'unguarded_result.json','guarded_result.json','unguarded2_result.json','guarded2_result.json',
    'created_live_result.json','matched_late_band_result.json','matched_created_band_result.json',
    'matched_created_band_guard_result.json')]
public={
    'schemaVersion':1,'recordedDate':'2026-10-08','status':'PRESERVED SOURCE-ONLY SUCCESS; FULL QUALIFICATION OPEN',
    'scope':'Recovery of preserved experiment before new matched telemetry controls; private captures/content/colors/handles/IDs/paths omitted.',
    'productionRemainsDefault':True,'packageOrInstallAuthorizedByQualification':False,'coryAcceptance':'OPEN',
    'bandContract':{
        'meaning':'Ordinary versus topmost Win32 Z-order class observed through WS_EX_TOPMOST and WINDOWPOS; no privileged or undocumented band APIs.',
        'windows':'Independent unowned top-level windows in one process; GUI-owned live source and worker-owned native host. Owned source means process/thread authority, not GW_OWNER.',
        'hostFlags':['nonactivating','input-transparent','no-redirection-bitmap','tool-window'],
        'hiddenPreparation':'Host remains hidden; matches currently sampled live-source topmost style before attachment, commit and transfer. Live source is not mutated during native creation.',
        'transfer':'Revalidate source/current host state, preserve band/parent/thread relationships, hide live source and show native host.',
        'adjacency':'Immediate adjacency after source hiding is not a requirement; fresh complete-client physical evidence establishes effective visibility.',
        'foreground':'Passive controls retain foreground without activation requests.',
        'cleanup':'Restore visible/enabled live source and QML interactivity; bounded native destruction yields deleted or safely retained allocation.'},
    'predeclaredThresholds':{
        'band':'Observed style/visibility/ownership must satisfy every strict stage; API success alone is insufficient.',
        'creation':'Immediately verify creation, source attachment and DComp commit; reject changed source policy before visible motion.',
        'physical':'Fresh observed frame, correct state/crop/witness, complete client including corners/margins, zero mismatches at required source/submitted/target/live endpoints.',
        'sdk':'Both ordinary/topmost policies, exact CPU-authored source/submitted markers, unchanged foreground, safe restoration/destruction.',
        'nativeMotionMs':350,'targetTransferDeadlineMs':240,'presentationSlotDeadlineMs':100,
        'coldPreparedTarget':False,'coldEndpointHoldMs':0,'coldIntentionalGuiDelayMs':0,
        'completeCandidate':'Stable source band plus exact presentation wait/revision, input, pixels, uninterrupted motion and lifecycle matrix; user installed acceptance remains final.'},
    'nativeBuildProvenance':{'historicalPromotion':bracket('native_build'),'historicalCreateBand':bracket('created_band_build')},
    'newPureWin32Control':win32_control(),
    'populatedSourceRuns':pop,'syntheticRuns':sdk,
    'sourceEquality':{
        'guardedVsUnlockedStartupSourcesEqual':pop[0]['provenance']['startupSourceHashes']==pop[1]['provenance']['startupSourceHashes'],
        'guardedVsUnlockedDllEqual':pop[0]['dllSha256']==pop[1]['dllSha256'],
        'createdBandVsHistoricalSameDll':False,
        'createdBandVsHistoricalDifferingStartupOrdinals':[a['sourceOrdinal'] for a,b in zip(pop[0]['provenance']['startupSourceHashes'],pop[2]['provenance']['startupSourceHashes']) if a!=b],
        'comparisonLimit':'Earlier SDK A/B filenames/configuration are descriptive only without contemporaneous source/DLL provenance; populated historical/create paths are not a one-variable same-DLL causal match.'},
    'validationSplit':{
        'preservedSandboxSafe':{'regressionPassed':760,'realWindowDeselected':1,'privacyScannerPassed':13,'createdBandFocusedPassed':226,
            'scope':'No-window/source/ABI/metadata/unit checks and compilation; no WebEngine runtime.'},
        'preservedOutsideSandbox':'SDK-only real HWND/D3D11 and populated disposable Qt/D3D11/fresh desktop source observations. No new WebEngine rendering is established.',
        'newReportInspection':'Safe JSON/native-binary ABI decoding, hashes, per-region count conservation and allowlist privacy inspection; no desktop runtime launched by this constructor.',
        'realWebEngineValidation':'NOT VALIDATED FOR THIS CONTINUATION'},
    'protectedBaselineScope':'Production EXE/workbooks match prior preserved baselines. Later source-run start/end settings and this session start match; an earlier settings hash differs and predates the three preserved source runs. No whole-history settings equality is claimed.',
    'preservedHistoricalArtifacts':[{ 'artifact':p.name,'sha256':sha(p)} for p in [
        ROOT/'docs/CLEANROOM_SOURCE_TRANSFER_READINESS_2026-10-08.md',ROOT/'docs/CLEANROOM_SOURCE_TRANSFER_READINESS_2026-10-08.json',
        ROOT/'docs/CLEANROOM_SUBMITTED_PROBE_QUALIFICATION_2026-10-08.md',ROOT/'docs/CLEANROOM_SUBMITTED_PROBE_QUALIFICATION_2026-10-08.json',
        ROOT/'docs/CLEANROOM_PHYSICAL_QUALIFICATION_RESULTS_2026-10-04.json',ROOT/'docs/CLEANROOM_OWNERSHIP_READINESS_RESULTS_2026-10-04.json']],
    'measurementLimits':[
        'One stopped populated maximized source control does not qualify a restore or maximize moving direction.',
        'Four exact full-client source comparisons do not establish rounded restored corners or target margins.',
        'Three stopped-preparation frame-latency waits do not reproduce the earlier moving post-import slot failure.',
        'Native return and DComp completion are independent of fresh physical presentation.',
        'QML interactivity state restoration is not accepted QML key/input delivery.',
        'Historical post-construction trace cannot establish immediate creation/attachment/commit gates.',
        'Failure-prefixed partial SDK output and stage-zero setup rejections are retained separately from transfer rejection.',
        'WINDOWPOS pseudo-handle class numbers are diagnostic classifications, not undocumented Windows band IDs.'],
    'remainingQualification':['fresh same-DLL matched creation-versus-promotion telemetry','presentation-slot contract after moving target import',
        'Time Entry four directions','Home both directions','Productivity at least five toggles','Directory both directions',
        'existing invoice-preview WebEngine both directions','reduced motion','failure cleanup','repeated native/Qt/QML input restoration',
        'uninterrupted physical motion without preparation pause/endpoint hold/second settlement','mixed DPI/monitor/lifecycle checks','Cory installed acceptance'],
}
public['aggregateValidation']={
    'sourceRunCount':len(pop),'syntheticResultCount':len(sdk),
    'freshPass':sum(x['status']=='PASS' for r in pop for x in r['freshObservations']),
    'freshFail':sum(x['status']!='PASS' for r in pop for x in r['freshObservations']),
    'exactSourceComparisons':sum(x['differentPixels']==0 for r in pop for x in r['pixelComparisons'] if not x['isDeliberateRemovalNegativeControl']),
    'deliberateRemovalNegativeCount':sum(x['isDeliberateRemovalNegativeControl'] for r in pop for x in r['pixelComparisons']),
    'allNativeBinaryTracesDecoded':True,'allPublishedRegionTotalsConserved':True,
}
assert public['aggregateValidation']['freshPass']==7
assert public['aggregateValidation']['exactSourceComparisons']==4
assert public['aggregateValidation']['deliberateRemovalNegativeCount']==1
OUT.write_text(json.dumps(public,separators=(',',':'))+'\n',encoding='utf-8')
print(json.dumps(public['aggregateValidation']))
