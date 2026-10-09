"""Read-only structural, conservation, identity and privacy review of public evidence."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
aggregate = read(ROOT/'docs/CLEANROOM_CREATED_BAND_MOVING_2026-10-08.json')
assert (aggregate['completed'],aggregate['freshPass'],aggregate['freshFail'],aggregate['exactComparisons'],aggregate['inputPass'])==(17,119,0,99,17)
all_slots = []
pixel_failures = 0
for summary in aggregate['runs']:
    target = ROOT/summary['publicEvidence']
    assert sha(target)==summary['publicEvidenceSha256']
    doc = read(target)
    assert {k:v for k,v in summary.items() if k not in ('publicEvidence','publicEvidenceSha256')}==doc['summary']
    raw = ROOT/'logs'/summary['run']/'native_gpu_spike.json'
    assert sha(raw)==summary['rawResultSha256']
    assert summary['protectedHashesMatch']
    assert summary['dllSha256']=='35c914560112a009ec8fdce1459e5f77dd10b41acb1ec2b0ae41124ba4d9f709'
    evidence = doc['evidence']
    for pixel in evidence['pixelComparisons']:
        assert sum(r['pixels'] for r in pixel['regions'].values())==pixel['pixels']
        assert sum(r['differentPixels'] for r in pixel['regions'].values())==pixel['differentPixels']
        pixel_failures += pixel['differentPixels']!=0
    slots = [r for t in evidence['nativeCallHistory'] for r in t['rows'] if r['callName']=='WaitForSingleObjectEx(frame-latency)']
    assert len(slots)==summary['slotSummary']['count']
    assert all(r['result']==0 and r['timeoutMs']==100 and all(r['generationsMatch'].values()) for r in slots)
    assert all(not t['droppedRows'] and t['firstFailure'] is None for t in evidence['nativeCallHistory'])
    all_slots.extend(slots)
assert len(all_slots)==361 and pixel_failures==3
assert max(r['elapsedMs'] for r in all_slots)==54.3261
safety = read(ROOT/'docs/CLEANROOM_CREATED_BAND_SAFETY_2026-10-08.json')
assert len(safety['controls'])==2
assert all(c['exitCode']==0 and not c['failures'] and not c['windowFailures'] and not c['sourceDrift'] and c['protectedUnchanged'] for c in safety['controls'])
assert all(c['primaryDirections']==2 and c['totalDirectionCommands']==5 and all(s['workspaceMatchesFirstTransition'] is True for s in c['snapshots'] if s['label']!='startup') for c in safety['controls'])
assert safety['controls'][0]['reducedMotionEnvironment']=='1' and safety['controls'][0]['observedSurfaceFrameRows']==0
assert safety['controls'][1]['unavailableNativeFallbackLogCount']==5
forbidden = {'hwnd','foregroundHwnd','currentThreadId','currentProcessId','liveThreadId','liveProcessId',
    'nativeThreadId','nativeProcessId','window','foreground','focus','active','owner','parent','process','thread',
    'currentThread','guiThread','workerThread','adapterLuid','sourceRGBA','submittedRGBA','targetRGBA','liveRGBA',
    'endpointDesktopBGR','liveDesktopBGR','channelMeansBGRA','nativePrevious','nativeNext','nativeParent','nativeMonitor',
    'livePrevious','liveNext','liveParent','liveMonitor'}
def privacy(value,path=()):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in forbidden:
                semantic_foreground = key=='foreground' and (
                    path==('bandContract',) and isinstance(item,str) or
                    path and path[0] in ('newPureWin32Control','currentPureWin32Control')
                    and path[-1] in ('before','after') and type(item) is int and item in (0,1))
                assert semantic_foreground, 'Raw identity/pixel key'
            privacy(item,path+(key,))
    elif isinstance(value,list):
        for item in value: privacy(item,path+('[]',))
    elif isinstance(value,str):
        assert not re.search(r'(?:[A-Za-z]:[\\/]|C:/Users|file://|AppData[/\\])',value), 'Private absolute path'
files = sorted((ROOT/'docs').glob('CLEANROOM_CREATED_BAND_*.json'))
for p in files:
    assert p.stat().st_size < 4*1024*1024
    privacy(read(p))
privacy(read(ROOT/'docs/CLEANROOM_CREATED_SOURCE_BAND_2026-10-08.json'))
print(json.dumps(dict(publicFiles=len(files),directions=17,freshPass=119,exact=99,pixelFailures=3,inputPass=17,
    waitPass=361,maxWaitMs=54.3261,safetyControls=2,privacy='PASS',regionConservation='PASS',hashes='PASS')))
