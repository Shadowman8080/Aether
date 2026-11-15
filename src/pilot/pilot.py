#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Aether Pilot — the assistant proposes, the person confirms, the log remembers.

Copilot-shaped help without giving a language model a shell. The model may only
name an action from a fixed catalog (`actions.json`) and fill that action's typed
parameters. Pilot revalidates everything against the catalog, shows exactly what
would run, waits for an explicit confirmation, and appends an audit line. There
are no free-form commands, no shell, and no way for a model to invent an action.
"""
import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA = 1
CATALOG_PATHS = (Path('/usr/share/aether/pilot/actions.json'), Path(__file__).with_name('actions.json'))
HELPER = '/usr/libexec/aether-pilot-admin'
ID = re.compile(r'[a-z][a-z0-9]*(?:\.[a-z0-9][a-z0-9-]*)+\Z')
ARG = re.compile(r'[A-Za-z0-9/.=:_+@%-]{1,256}\Z')
PARAM = re.compile(r'\{([a-z][a-z0-9_]{0,31})\}\Z')
TTL = 300
RISKS = ('read', 'low', 'medium', 'high')
PRIVILEGES = ('user', 'admin')


def state_dir():
    path = Path(os.environ.get('AETHER_PILOT_STATE') or
                Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'aether/pilot')
    if path.is_symlink():
        raise ValueError('Pilot state must not be a symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def atomic_json(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_catalog(value):
    """Reject anything that could turn the catalog back into a command line."""
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise ValueError('Action catalog must use schema %d' % SCHEMA)
    actions = value.get('actions')
    if not isinstance(actions, list) or not 0 < len(actions) <= 64:
        raise ValueError('Action catalog must list 1-64 actions')
    clean, seen = {}, set()
    for raw in actions:
        if not isinstance(raw, dict):
            raise ValueError('Each action must be an object')
        action_id = raw.get('id')
        if not isinstance(action_id, str) or not ID.fullmatch(action_id):
            raise ValueError('Invalid action id')
        if action_id in seen:
            raise ValueError('Duplicate action id: ' + action_id)
        seen.add(action_id)
        for field in ('title', 'summary'):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise ValueError('Action %s needs a %s' % (action_id, field))
        privilege, risk = raw.get('privilege'), raw.get('risk')
        if privilege not in PRIVILEGES or risk not in RISKS:
            raise ValueError('Action %s has an invalid privilege or risk' % action_id)
        params = raw.get('params', {})
        if not isinstance(params, dict) or len(params) > 4:
            raise ValueError('Action %s has an invalid parameter list' % action_id)
        for name, spec in params.items():
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', name):
                raise ValueError('Action %s has an invalid parameter name' % action_id)
            if not isinstance(spec, dict) or spec.get('type') not in ('pattern', 'choice'):
                raise ValueError('Action %s parameter %s has an invalid type' % (action_id, name))
            if spec['type'] == 'choice':
                values = spec.get('values')
                if not isinstance(values, list) or not values or not all(isinstance(v, str) and ARG.fullmatch(v) for v in values):
                    raise ValueError('Action %s parameter %s has invalid choices' % (action_id, name))
            else:
                pattern = spec.get('pattern')
                if not isinstance(pattern, str) or not 1 <= len(pattern) <= 200:
                    raise ValueError('Action %s parameter %s has an invalid pattern' % (action_id, name))
                try:
                    re.compile(pattern)
                except re.error:
                    raise ValueError('Action %s parameter %s has an invalid pattern' % (action_id, name)) from None
        argv = raw.get('argv')
        if not isinstance(argv, list) or not 1 <= len(argv) <= 16:
            raise ValueError('Action %s needs an argv list' % action_id)
        used = set()
        for token in argv:
            if not isinstance(token, str):
                raise ValueError('Action %s has a non-string argument' % action_id)
            placeholder = PARAM.fullmatch(token)
            if placeholder:
                if placeholder.group(1) not in params:
                    raise ValueError('Action %s uses an undeclared parameter' % action_id)
                used.add(placeholder.group(1))
            elif not ARG.fullmatch(token):
                raise ValueError('Action %s has an unsafe argument: %r' % (action_id, token))
        if used != set(params):
            raise ValueError('Action %s must use every declared parameter' % action_id)
        phrases = raw.get('phrases', [])
        if not isinstance(phrases, list) or not all(isinstance(p, str) and p.strip() for p in phrases):
            raise ValueError('Action %s has invalid phrases' % action_id)
        clean[action_id] = {
            'id': action_id,
            'title': raw['title'][:120],
            'summary': raw['summary'][:400],
            'phrases': [p.strip().lower()[:120] for p in phrases],
            'privilege': privilege,
            'risk': risk,
            'params': params,
            'argv': argv,
            'requires_confirmation': risk != 'read',
        }
    return clean


def catalog(path=None):
    for candidate in ((Path(path),) if path else CATALOG_PATHS):
        if candidate.exists():
            return validate_catalog(json.loads(candidate.read_text(encoding='utf-8')))
    raise ValueError('No Aether Pilot action catalog is installed')


def clean_params(action, values):
    """Typed, bounded, catalog-checked. Nothing free-form reaches a subprocess."""
    values = values or {}
    if not isinstance(values, dict):
        raise ValueError('Parameters must be an object')
    extra = set(values) - set(action['params'])
    if extra:
        raise ValueError('Unexpected parameter: ' + ', '.join(sorted(extra)))
    result = {}
    for name, spec in action['params'].items():
        if name not in values:
            raise ValueError('Action %s needs the %s parameter' % (action['id'], name))
        value = values[name]
        if not isinstance(value, str) or not 1 <= len(value) <= 256:
            raise ValueError('Parameter %s must be a short string' % name)
        if spec['type'] == 'choice':
            if value not in spec['values']:
                raise ValueError('Parameter %s must be one of: %s' % (name, ', '.join(spec['values'])))
        elif not re.fullmatch(spec['pattern'], value):
            raise ValueError('Parameter %s does not match this action\'s allowed format' % name)
        result[name] = value
    return result


def build_command(action, params):
    """The exact argv, with the administrator helper as the only privileged path."""
    argv = [params.get(PARAM.fullmatch(token).group(1), token) if PARAM.fullmatch(token) else token
            for token in action['argv']]
    if action['privilege'] == 'admin':
        return ['pkexec', HELPER, action['id'], *[params[name] for name in action['params']]]
    return argv


def pending_path():
    return state_dir() / 'pending.json'


def load_pending():
    try:
        value = json.loads(pending_path().read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def save_pending(value):
    atomic_json(pending_path(), value)


def enabled():
    try:
        return not json.loads((state_dir() / 'disabled.json').read_text(encoding='utf-8')).get('disabled')
    except (FileNotFoundError, ValueError):
        return True


def set_enabled(value):
    path = state_dir() / 'disabled.json'
    if value:
        path.unlink(missing_ok=True)
    else:
        atomic_json(path, {'disabled': True, 'time': int(time.time())})
    return {'enabled': bool(value)}


def issue(action, params, actions=None):
    """Record a proposal a person still has to confirm. Changing nothing yet."""
    params = clean_params(action, params)
    entry = {
        'id': secrets.token_hex(8),
        'action': action['id'],
        'title': action['title'],
        'summary': action['summary'],
        'params': params,
        'privilege': action['privilege'],
        'risk': action['risk'],
        'requires_confirmation': action['requires_confirmation'],
        'command': build_command(action, params),
        'created': int(time.time()),
        'expires': int(time.time()) + TTL,
    }
    store = load_pending()
    now = int(time.time())
    store = {k: v for k, v in store.items() if isinstance(v, dict) and v.get('expires', 0) > now}
    store[entry['id']] = entry
    save_pending(store)
    return entry


def propose(text, actions=None):
    """Local intent matching against catalog phrases. No model call, no network."""
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ValueError('Give Pilot a request between 1 and 2,000 characters')
    actions = actions or catalog()
    request = ' '.join(text.lower().split())
    best, best_score, matched = None, 0, ''
    for action in actions.values():
        for phrase in action['phrases']:
            if phrase in request and len(phrase) > best_score:
                best, best_score, matched = action, len(phrase), phrase
        if action['id'].replace('.', ' ') in request and best_score < 1:
            best, best_score, matched = action, 1, action['id'].replace('.', ' ')
    if not best:
        return []
    # Words that only appear in the matched phrase are intent, not arguments.
    ignore = {word.strip('.,:;') for word in matched.split()}
    params = {name: _guess(name, spec, text, ignore) for name, spec in best['params'].items()}
    if any(value is None for value in params.values()):
        # Ask for the missing value instead of guessing one.
        return [{'action': best['id'], 'title': best['title'], 'summary': best['summary'],
                 'missing': [n for n, v in params.items() if v is None],
                 'params': {n: v for n, v in params.items() if v is not None}}]
    return [issue(best, params, actions)]


def _guess(name, spec, text, ignore=()):
    if spec['type'] == 'choice':
        for value in spec['values']:
            if value in text:
                return value
        return None
    for token in re.findall(r'[A-Za-z0-9][A-Za-z0-9._+@/-]{1,255}', text):
        if token.lower() in ignore:
            continue
        if re.fullmatch(spec['pattern'], token):
            return token
    return None


def propose_from_model(answer, actions=None):
    """Accept only a catalog action with valid typed parameters from model output."""
    if not isinstance(answer, str) or len(answer) > 20000:
        raise ValueError('Assistant answer is missing or too long')
    blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', answer, flags=re.S) or \
             re.findall(r'(\{[^{}]*"action"[^{}]*\})', answer, flags=re.S)
    if not blocks:
        raise ValueError('The assistant did not propose an action')
    actions = actions or catalog()
    for block in reversed(blocks):
        try:
            value = json.loads(block)
        except ValueError:
            continue
        if not isinstance(value, dict):
            continue
        action_id = value.get('action')
        action = actions.get(action_id if isinstance(action_id, str) else '')
        if not action:
            raise ValueError('The assistant proposed an action that is not available')
        return issue(action, value.get('params') or {}, actions)
    raise ValueError('The assistant proposal was not valid JSON')


def audit_path():
    return state_dir() / 'audit.jsonl'


def record(entry):
    with audit_path().open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(entry, sort_keys=True) + '\n')
    os.chmod(audit_path(), 0o600)


def audit(limit=20):
    try:
        lines = audit_path().read_text(encoding='utf-8').splitlines()[-int(limit):]
    except FileNotFoundError:
        return []
    result = []
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def execute(action, params, runner=subprocess.run):
    command = build_command(action, params)
    started = time.time()
    timeout = 120 if action['risk'] == 'read' else 3600
    result = runner(command, capture_output=True, text=True, timeout=timeout, shell=False)
    return {
        'command': command,
        'exit': result.returncode,
        'stdout': (result.stdout or '')[-4000:],
        'stderr': (result.stderr or '')[-4000:],
        'seconds': round(time.time() - started, 2),
    }


def run(proposal_id, *, yes=False, actions=None, runner=subprocess.run):
    """Single-use confirmation. The proposal is consumed before it executes."""
    if not enabled():
        raise ValueError('Aether Pilot is disabled for this account in Aether Settings')
    actions = actions or catalog()
    store = load_pending()
    entry = store.get(proposal_id)
    if not isinstance(entry, dict):
        raise ValueError('That proposal is unknown, already used or expired')
    if entry.get('expires', 0) <= time.time():
        store.pop(proposal_id, None)
        save_pending(store)
        raise ValueError('That proposal expired. Ask Pilot again')
    if entry['risk'] == 'high' and not yes:
        raise ValueError('This action is high risk. Re-run with --yes after reading what it does')
    action = actions.get(entry.get('action'))
    if not action:
        raise ValueError('The proposed action is no longer in the catalog')
    params = clean_params(action, entry.get('params'))
    store.pop(proposal_id, None)
    save_pending(store)
    try:
        result = execute(action, params, runner=runner)
        status = 'completed' if result['exit'] == 0 else 'failed'
    except (OSError, subprocess.SubprocessError) as error:
        result = {'command': build_command(action, params), 'exit': None, 'stdout': '', 'stderr': str(error)[:500]}
        status = 'failed'
    receipt = {'schema': 1, 'action': action['id'], 'params': params, 'privilege': action['privilege'],
               'risk': action['risk'], 'status': status, **result}
    record({'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'action': action['id'],
            'params': params, 'privilege': action['privilege'], 'risk': action['risk'],
            'status': status, 'exit': result['exit']})
    return receipt


def main():
    parser = argparse.ArgumentParser(prog='aether-pilot',
                                     description='Suggest, confirm and log system actions.')
    commands = parser.add_subparsers(dest='action_name', required=True)
    suggest = commands.add_parser('suggest', help='propose an action for a request')
    suggest.add_argument('text', nargs='*')
    suggest.add_argument('--model-answer', help='file holding an assistant answer to validate')
    run_command = commands.add_parser('run', help='execute one pending proposal')
    run_command.add_argument('proposal')
    run_command.add_argument('--yes', action='store_true', help='required for high-risk actions')
    listing = commands.add_parser('catalog', help='list available actions')
    listing.add_argument('--json', action='store_true')
    history = commands.add_parser('audit', help='show what Pilot ran')
    history.add_argument('--limit', type=int, default=20)
    commands.add_parser('status', help='show whether Pilot is enabled')
    for name in ('enable', 'disable'):
        commands.add_parser(name)
    args = parser.parse_args()
    if args.action_name == 'catalog':
        actions = catalog()
        if args.json:
            print(json.dumps(list(actions.values()), indent=2))
        else:
            for action in actions.values():
                print('%-20s %-8s %s' % (action['id'], action['privilege'], action['title']))
        return 0
    if args.action_name == 'audit':
        for entry in audit(args.limit):
            print('%s  %-20s %-8s %s' % (entry.get('time', ''), entry.get('action', ''),
                                         entry.get('status', ''), json.dumps(entry.get('params', {}))))
        return 0
    if args.action_name == 'status':
        print(json.dumps({'enabled': enabled(), 'actions': len(catalog())}))
        return 0
    if args.action_name in ('enable', 'disable'):
        print(json.dumps(set_enabled(args.action_name == 'enable')))
        return 0
    if args.action_name == 'suggest':
        if args.model_answer:
            proposal = propose_from_model(Path(args.model_answer).read_text(encoding='utf-8'))
            print(json.dumps(proposal, indent=2))
            return 0
        print(json.dumps(propose(' '.join(args.text)), indent=2))
        return 0
    receipt = run(args.proposal, yes=args.yes)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['status'] == 'completed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('aether-pilot: ' + str(error), file=sys.stderr)
        sys.exit(2)
