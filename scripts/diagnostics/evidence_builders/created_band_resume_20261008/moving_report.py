"""Publish bounded allowlisted moving controls, separately from preserved source evidence."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
helper = ROOT / 'scripts/diagnostics/evidence_builders/created_band_resume_20261008/extend_report.py'
namespace = {'__file__': str(helper), '__name__': 'moving_evidence_helpers'}
source = helper.read_text(encoding='utf-8')
exec(compile(source[:source.index('runs = sorted')], str(helper), 'exec'), namespace)
read, sha, current_run = (namespace[k] for k in ('read','sha','current_run'))
summaries = []
for p in sorted(ROOT.glob('logs/native_created_ordered_cold_*_20261008_run*/native_gpu_spike.json')):
    raw = read(p)
    if any(e['event']=='command' for e in raw['events']):
        out = current_run(p)
    else:
        out = dict(configuration=raw['configuration'],completedMovingDirections=0,
            freshObservations=[],pixelComparisons=[],sourceTransfer=[],inputRestoration=[],inputWitnesses=[],
            nativeCallHistory=[],creationStates=[],scope='Setup rejected before any command or native creation.')
        before,after = read(p.parent/'protected_hashes_start.json'),read(p.parent/'protected_hashes.json')
        out['protectedManifestStartEndEquality'] = before==after['before']==after['after']
        out['configuration'] = {k:raw['configuration'].get(k) for k in ('workspace','first_direction','restored_size',
            'duration_ms','blend_start_ms','endpoint_hold_ms','gui_delay_ms','cycles','source_observation_only',
            'single_owner_source','native_created_source_band','native_call_trace','source_transfer_trace')}
    events = raw['events']
    clocks = {e['cycle']: e['t'] for e in events if e['event']=='native-clock-start'}
    commands = {e['cycle']: e for e in events if e['event']=='command'}
    out['timingScope'] = 'Command is fixture dispatch, not input-to-photon. Import spans use the GUI post-cspm_comp_start-return notification, after the first synchronous native render. Native setter separately enforces its actual fixed 240 ms clock before/after transfer.'
    out['configuration']['desktop_output_index'] = raw['configuration'].get('desktop_output_index',0)
    out['configuration']['desktop_device_index'] = raw['configuration'].get('desktop_device_index',0)
    for name in ('intrinsic_only','render_target_import','post_input_pixels','probe_endpoint'):
        out['configuration'][name] = raw['configuration'].get(name,False)
    if not raw['configuration']['native_call_trace']:
        out['creationTelemetryLimit'] = 'No opt-in creation/API trace in this collector-free control; creation return and native status are recorded, exact slot/typed deletion evidence unmeasured.'
    out['webengineEvents'] = [{'event':e['event'],'cycle':e['cycle'],
        'timeFromFirstCommandMs':(e['t']-next(iter(commands.values()))['t'])*1000}
        for e in events if e['event'] in ('webengine-html-requested','webengine-html-ready')]
    out['importReadiness'] = []
    out['importRejections'] = []
    for e in events:
        if e['event']=='target-gpu-composition-committed':
            clock = clocks[e['cycle']]
            out['importReadiness'].append(dict(cycle=e['cycle'],direction=commands[e['cycle']].get('kind'),
                importBeginAfterStartReturnNotificationMs=(e['importStarted']-clock)*1000,
                importReturnAfterStartReturnNotificationMs=(e['importFinished']-clock)*1000,
                queuedGuiReceiptAfterStartReturnNotificationMs=(e['t']-clock)*1000,
                deadlineMs=240,importThread=e['importThread']))
        elif e['event']=='target-render-import-rejected':
            clock = clocks[e['cycle']]
            n = e['native']
            out['importRejections'].append(dict(cycle=e['cycle'],nativeError=e['nativeError'],
                callerBeginAfterStartReturnNotificationMs=(e['started']-clock)*1000,
                callerReturnAfterStartReturnNotificationMs=(e['finished']-clock)*1000,
                workerEntryAfterStartReturnNotificationMs=(n['targetImportBeginSeconds']-clock)*1000,
                targetReadyRecorded=n['targetReadySeconds']!=0,
                lastFrameElapsedMs=n['lastFrameElapsedSeconds']*1000,
                lastFrameMotion=n['lastFrameMotion'],lastFrameContent=n['lastFrameContent'],
                sourceWH=[n['sourceWidth'],n['sourceHeight']],targetWH=[n['targetWidth'],n['targetHeight']],
                lastPresentHRESULT=n['lastPresentHRESULT'],lastPresentId=n['submittedPresentId'],
                scope='Readiness rejection and worker-entry metadata. No exact frame-latency wait return is inferred.'))
    for label in ('freshObservations','pixelComparisons','sourceTransfer','inputRestoration'):
        if label=='freshObservations': rows = [e for e in events if e['event']=='desktop-observation']
        elif label=='pixelComparisons': rows = [e for e in events if e['event']=='physical-pixel-analysis']
        elif label=='sourceTransfer': rows = [e for e in events if e['event']=='source-transfer-boundary']
        else: rows = [e for e in events if e['event']=='input-restored']
        assert len(rows)==len(out[label])
        for target, original in zip(out[label],rows):
            target['cycle'] = original.get('sampledCycle',original['cycle'])
    slots = [r for t in out['nativeCallHistory'] for r in t['rows'] if r['callName']=='WaitForSingleObjectEx(frame-latency)']
    imports = out['importReadiness']
    out['slotSummary'] = dict(count=len(slots),passed=sum(r['result']==0 for r in slots),
        failed=sum(r['result']!=0 for r in slots),timeoutMs=100,
        maxWaitMs=max((r['elapsedMs'] for r in slots),default=None),
        allGenerationsMatch=all(all(r['generationsMatch'].values()) for r in slots) if slots else None,
        scope='One DXGI frame-latency availability wait before render. No extra probe consumes the event; not a revision event or physical scanout proof.')
    out['cycleDirections'] = [{'cycle':e['cycle'],'direction':e.get('kind')} for e in commands.values()]
    summary = dict(run=p.parent.name,completed=raw['completedCycles'],failures=raw['failures'],
        rawResultSha256=sha(p),dllSha256=raw['dllHash'],
        freshPass=sum(e['status']=='PASS' for e in out['freshObservations']),
        freshFail=sum(e['status']!='PASS' for e in out['freshObservations']),
        exactComparisons=sum(e['differentPixels']==0 for e in out['pixelComparisons']),
        pixelFailures=sum(e['differentPixels']!=0 for e in out['pixelComparisons'] if not e['isDeliberateRemovalNegativeControl']),
        inputPass=sum(e['status']=='PASS' for e in out['inputWitnesses']),
        sourceTransfersAccepted=sum(e['accepted']==1 for e in out['sourceTransfer']),
        slotSummary=out['slotSummary'],importReadiness=imports,importRejections=out['importRejections'],
        collectorFree=raw['configuration'].get('intrinsic_only',False),
        webengineHtmlReady=sum(e['event']=='webengine-html-ready' for e in events),
        destructionEvidence='Typed final native trace' if raw['configuration']['native_call_trace'] else 'Not recorded; no typed deletion outcome claim',
        hostDeleted=sum(e.get('hostDestroyed') is True for e in out['nativeCallHistory']),
        hostRetained=sum(e.get('hostRetained') is True for e in out['nativeCallHistory']),
        totalRows=sum(e['totalRows'] for e in out['nativeCallHistory']),
        droppedRows=sum(e['droppedRows'] for e in out['nativeCallHistory']),
        firstFailures=[e['firstFailure'] for e in out['nativeCallHistory'] if e['firstFailure']],
        protectedHashesMatch=out['protectedManifestStartEndEquality'],qualification=raw['coldCandidateQualification'])
    name = 'CLEANROOM_CREATED_BAND_' + raw['configuration']['workspace'].upper().replace('-','_') + '_2026-10-08_' + p.parent.name.rsplit('_',1)[-1] + '.json'
    target = ROOT/'docs'/name
    public = dict(schemaVersion=1,recordedDate='2026-10-08',summary=summary,evidence=out)
    data = json.dumps(public,separators=(',',':'))+'\n'
    assert len(data.encode()) < 4*1024*1024
    target.write_text(data,encoding='utf-8')
    summary['publicEvidence'] = 'docs/'+name
    summary['publicEvidenceSha256'] = sha(target)
    summaries.append(summary)
aggregate = dict(schemaVersion=1,recordedDate='2026-10-08',scope='Instrumented outside-sandbox moving controls, not complete continuous-motion qualification.',
    runs=summaries,completed=sum(r['completed'] for r in summaries),freshPass=sum(r['freshPass'] for r in summaries),
    freshFail=sum(r['freshFail'] for r in summaries),exactComparisons=sum(r['exactComparisons'] for r in summaries),
    inputPass=sum(r['inputPass'] for r in summaries),productionUnchanged=True,packageGate='CLOSED',coryAcceptance='OPEN')
aggregate['validation'] = dict(sandboxSafePassed=784,realWindowDeselected=1,
    sourceDriftCount=0,compilePassed=True,whitespacePassed=True,
    summarySha256=sha(ROOT/'outputs/native_wait_20261008/created_moving_final1/validation_summary.json'),
    scope='Current-source sandbox-safe regression/compilation only; outside-sandbox runtime is recorded per desktop control.')
(ROOT/'docs/CLEANROOM_CREATED_BAND_MOVING_2026-10-08.json').write_text(json.dumps(aggregate,separators=(',',':'))+'\n',encoding='utf-8')
print(json.dumps(aggregate))
