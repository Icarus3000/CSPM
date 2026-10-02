"""Compare stable desktop marker bounds across completed image/live handoffs."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('audit', type=Path)
args = parser.parse_args()
audit = args.audit
runs = json.loads((audit/'latency_events.json').read_text())
functional = json.loads((audit/'window_transition_results.json').read_text())
with (audit/'window_transition_pixel8.csv').open(newline='') as stream:
    pixels = list(csv.DictReader(stream))
with (audit/'window_transition_pixel8.commands.csv').open(newline='') as stream:
    commands = [(float(t), kind) for t, kind in csv.reader(stream)]
primary = []
for time, kind in commands:
    if kind not in ('maximize','restore'):
        break
    primary.append((time,kind))

def stable_samples(start, end):
    selected = [p for p in pixels if start <= float(p['timestamp']) <= end
                and int(p['top_left_w']) > 0]
    boxes = Counter(tuple(int(p['top_left_'+k]) for k in ('x','y','w','h')) for p in selected)
    box, count = boxes.most_common(1)[0] if boxes else (None,0)
    return dict(bounds=box, matching_samples=count, total_samples=len(selected)), selected

observations = []
failures = list(functional['failures'])
if any(run.get('timedOut') for run in runs):
    failures.append('Transition watchdog timeout; whole fixture fails')
for index,(command_time,kind) in enumerate(primary):
    if kind != 'restore':
        continue
    run = runs[index]
    if run.get('timedOut'):
        continue
    events = dict(run['events'])
    zero = run['events'][0][1]
    seconds = lambda key: command_time + (events[key]-zero)/1000
    # Use the final submitted-image interval, rather than a GUI animation
    # completion notification that can precede the physical endpoint frame.
    target_frame = next(v for k,v in run['events'] if k == 'surface-frame-target-1')
    frozen_start = command_time + (target_frame-zero)/1000 + .030
    frozen, before = stable_samples(frozen_start, seconds('finish-start'))
    live, after = stable_samples(seconds('finish-end')+.050, seconds('finish-end')+.250)
    native = sorted({tuple(int(p['native_'+k]) for k in ('x','y','w','h')) for p in before+after})
    observation = dict(cycle_index=index, frozen_marker=frozen, live_marker=live, native_rectangles=native)
    observations.append(observation)
    if frozen['matching_samples'] < 2 or live['matching_samples'] < 2:
        failures.append(f'Cycle {index}: insufficient repeated stable handoff samples')
    elif frozen['bounds'] != live['bounds']:
        failures.append(f'Cycle {index}: marker bounds differ across handoff')
    if len(native) != 1:
        failures.append(f'Cycle {index}: native window rectangle changed or missing')
if len(observations) != len(primary)//2:
    failures.append('Missing completed primary restore observations')
result = dict(passed=not failures, sample_count=len(pixels), observations=observations, failures=failures)
(audit/'handoff_pixel_comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
raise SystemExit(1 if failures else 0)
