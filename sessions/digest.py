"""
Generate compact session digests for token-efficient analysis.

Usage:
    python sessions/digest.py                          # digest all sessions
    python sessions/digest.py session_20260408_003854  # digest one session

Produces session_*.digest.json (~2% of full file size) containing:
  - metadata (unchanged)
  - summary (unchanged)
  - timeline: only activation/deactivation/suppression events with scores
  - attacks (unchanged)

The full session JSON is preserved for deep-dive analysis.
"""
import json
import os
import sys
import glob


def digest_session(full_path):
    """Read a full session JSON and return a compact digest dict."""
    with open(full_path, 'r') as f:
        session = json.load(f)

    # Timeline: only frames with meaningful state changes
    # (suppression alone is too noisy — include only with other changes)
    timeline = []
    for frame in session.get('frames', []):
        has_change = any(k in frame for k in
                         ('activated', 'deactivated', 'silence_gated', 'pedal'))
        if not has_change:
            continue
        entry = {'t': frame['t'], 'scores': frame['scores']}
        for key in ('activated', 'deactivated', 'suppressed',
                     'silence_gated', 'pedal'):
            if key in frame:
                entry[key] = frame[key]
        timeline.append(entry)

    return {
        'metadata': session.get('metadata', {}),
        'summary': session.get('summary', {}),
        'timeline': timeline,
        'attacks': session.get('attacks', []),
    }


def digest_file(full_path):
    """Generate a .digest.json file from a full session JSON."""
    digest = digest_session(full_path)
    digest_path = full_path.replace('.json', '.digest.json')
    with open(digest_path, 'w') as f:
        json.dump(digest, f, indent=2)

    full_size = os.path.getsize(full_path)
    digest_size = os.path.getsize(digest_path)
    ratio = round(100 * digest_size / full_size, 1) if full_size else 0
    print(f'{os.path.basename(digest_path)}: {digest_size:,} bytes '
          f'({ratio}% of {full_size:,})')
    return digest_path


def main():
    session_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) > 1:
        # Digest specific session(s)
        for name in sys.argv[1:]:
            if not name.endswith('.json'):
                name = f'{name}.json'
            path = os.path.join(session_dir, name)
            if os.path.exists(path):
                digest_file(path)
            else:
                print(f'Not found: {path}')
    else:
        # Digest all sessions that don't have a digest yet
        for path in sorted(glob.glob(os.path.join(session_dir, 'session_*.json'))):
            if path.endswith('.digest.json'):
                continue
            digest_path = path.replace('.json', '.digest.json')
            if not os.path.exists(digest_path):
                digest_file(path)
            else:
                print(f'Skipping (digest exists): {os.path.basename(path)}')


if __name__ == '__main__':
    main()
