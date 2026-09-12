"""Finite local serving experiment. Never change a running quality benchmark."""

import argparse
import hashlib
import json
import math
import os
import signal
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/autodl-tmp/AgentSentry')
URL = 'http://127.0.0.1:18080'
PLAN = ROOT / 'artifacts/vllm-tuning-plan.json'
BASE = ROOT / 'artifacts/local-model-27b-32k-command.json'
OUTPUT = ROOT / 'artifacts/vllm-tuning-v1'
STATE = ROOT / 'docs/evidence/vllm-tuning-report.json'
REPORT = ROOT / 'docs/05-validation/vllm-tuning-report.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process(pid):
    try:
        parts = (Path('/proc') / str(pid) / 'stat').read_text().rpartition(')')[2].split()
        if parts[0] in {'Z', 'X'}:
            return None
        return {'pid': pid, 'start_ticks': parts[19], 'pgrp': int(parts[2]),
                'session': int(parts[3])}
    except FileNotFoundError:
        return None


def same_process(expected):
    actual = process(expected['pid'])
    return actual is not None and actual['start_ticks'] == expected['start_ticks']


def server_command(pid):
    return (Path('/proc') / str(pid) / 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')


def group_members(pgrp):
    members = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            item = process(int(path.name))
            if item and item['pgrp'] == pgrp:
                members.append(item)
    return members


def stop_owned_group(expected):
    actual = process(expected['pid'])
    if actual is not None and (not same_process(expected) or actual['pgrp'] != expected['pid']):
        raise RuntimeError('REFUSE_TO_STOP_CHANGED_PROCESS_IDENTITY')
    members = group_members(expected['pid'])
    if any(p['session'] != expected['pid'] or int(p['start_ticks']) < int(expected['start_ticks']) for p in members):
        raise RuntimeError('REFUSE_TO_STOP_UNOWNED_PROCESS_GROUP')
    # A failed API process can leave its engine alive. Session ownership and
    # individual start times remain verifiable even after its leader exits.
    for item in members:
        if same_process(item):
            try:
                os.kill(item['pid'], signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 60
    while any(same_process(p) for p in members) and time.monotonic() < deadline:
        time.sleep(1)
    # Never kill a reused PID or a newly discovered process.
    for item in members:
        if same_process(item):
            os.kill(item['pid'], signal.SIGKILL)
    deadline = time.monotonic() + 15
    while group_members(expected['pid']) and time.monotonic() < deadline:
        time.sleep(1)
    if group_members(expected['pid']):
        raise RuntimeError('OWNED_GROUP_DID_NOT_STOP')


def request(path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(URL + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    # Localhost traffic does not use proxy configuration or external credentials.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as response:
        return json.load(response)


def assert_no_clients():
    names = {'run_agentdojo.py', 'run_injecagent.py', 'run_asb.py'}
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit() or int(directory.name) == os.getpid():
            continue
        try:
            argv = (directory / 'cmdline').read_bytes().decode().split('\0')
            if any(Path(arg).name in names for arg in argv):
                cwd = (directory / 'cwd').resolve()
                if cwd == ROOT or ROOT in cwd.parents:
                    raise RuntimeError('QUALITY_BENCHMARK_CLIENT_STILL_RUNNING:' + directory.name)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue


def assert_idle():
    for _ in range(3):
        assert_no_clients()
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(URL + '/metrics', timeout=10) as response:
            metrics = response.read().decode().splitlines()
        found = []
        for line in metrics:
            if line.startswith(('vllm:num_requests_running{', 'vllm:num_requests_waiting{')):
                found.append(float(line.rsplit(' ', 1)[1]))
        if len(found) < 2 or any(value != 0 for value in found):
            raise RuntimeError('MODEL_SERVER_NOT_CONFIRMED_IDLE')
        time.sleep(2)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def save(state):
    state['updated_at'] = datetime.now(timezone.utc).isoformat()
    write_json(STATE, state)
    rows = ['# vLLM 调优实时记录', '', '状态：`' + state['status'] + '`。更新：' + state['updated_at'],
            '', '固定 27B NVFP4 权重；依次等待 v4 配对及 task-plan-v1 小样结束。调优结束后恢复原服务配置。',
            '本页仅记录服务性能试验，不代表 AgentSentry 的 benchmark 验收通过。', '',
            '| 配置 | 状态 | 正确性检查 | 性能工件数 |', '|---|---|---:|---:|']
    for trial in state['trials']:
        checks = trial.get('checks', [])
        rows.append('| ' + trial['id'] + ' | ' + trial['status'] + ' | '
                    + (str(sum(c['passed'] for c in checks)) + '/' + str(len(checks)) if checks else 'NOT_RUN')
                    + ' | ' + str(len(trial.get('measurements', []))) + ' |')
    rows += ['', '机器状态与原始工件路径见 [JSON](../evidence/vllm-tuning-report.json)。',
             '16 条固定长度随机请求仅用于筛选配置；即使变快，仍需真实 Agent 工作负载和完整质量配对验证。', '']
    temporary = REPORT.with_suffix('.tmp')
    temporary.write_text('\n'.join(rows))
    temporary.replace(REPORT)


def start_server(argv, log_path, state):
    env = dict(os.environ)
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', VLLM_USE_FLASHINFER_SAMPLER='0')
    env.pop('PYTHONPATH', None)
    with log_path.open('xb') as stream:
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
    identity = process(child.pid)
    if identity is None:
        raise RuntimeError('MODEL_PROCESS_EXITED_AT_START')
    state['owned_server'] = identity
    save(state)
    started = time.monotonic()
    deadline = started + 1500
    alias = argv[argv.index('--served-model-name') + 1]
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('MODEL_STARTUP_FAILED:' + str(child.returncode))
        try:
            if [m['id'] for m in request('/v1/models')['data']] == [alias]:
                return identity, time.monotonic() - started
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(5)
    raise TimeoutError('MODEL_STARTUP_EXCEEDED_25_MINUTES')


def checks(model):
    common = {'model': model, 'temperature': 0, 'seed': 0, 'max_tokens': 128}
    shared = 'This is a synthetic cache consistency test with no external tools. ' * 64
    scenarios = [
        ('short', {'messages': [{'role': 'user', 'content': 'Reply with exactly READY and no other text.'}]}, 'READY'),
        ('json', {'messages': [{'role': 'user', 'content': 'Return a JSON object with value 37 and unit "test". No other fields.'}],
                  'response_format': {'type': 'json_object'}}, {'value': 37, 'unit': 'test'}),
        ('prefix_a', {'messages': [{'role': 'system', 'content': shared},
                                   {'role': 'user', 'content': 'Reply with exactly ALPHA17 and nothing else.'}]}, 'ALPHA17'),
        ('prefix_b', {'messages': [{'role': 'system', 'content': shared},
                                   {'role': 'user', 'content': 'Reply with exactly BETA29 and nothing else.'}]}, 'BETA29'),
        ('tool', {'messages': [{'role': 'user', 'content': 'Call record_value with value 37 and label "check".'}],
                  'tools': [{'type': 'function', 'function': {'name': 'record_value', 'description': 'Record a synthetic value.',
                      'parameters': {'type': 'object', 'properties': {'value': {'type': 'integer'}, 'label': {'type': 'string'}},
                                     'required': ['value', 'label'], 'additionalProperties': False}}}],
                  'tool_choice': {'type': 'function', 'function': {'name': 'record_value'}}}, {'value': 37, 'label': 'check'}),
    ]
    records = []
    for name, body, expected in scenarios:
        item = {'name': name, 'passed': False, 'request': common | body}
        start = time.monotonic()
        try:
            result = request('/v1/chat/completions', item['request'], timeout=240)
            item['response'] = result
            message = result['choices'][0]['message']
            if name == 'tool':
                calls = message.get('tool_calls', [])
                item['passed'] = len(calls) == 1 and calls[0]['function']['name'] == 'record_value' and json.loads(calls[0]['function']['arguments']) == expected
            elif name == 'json':
                item['passed'] = json.loads(message['content']) == expected
            else:
                item['passed'] = message['content'].strip() == expected
        except Exception as exc:
            item['error'] = type(exc).__name__ + ':' + str(exc)
        item['seconds'] = time.monotonic() - start
        records.append(item)
    return records


def measure(trial, plan, directory, state):
    model = trial['argv'][trial['argv'].index('--served-model-name') + 1]
    executable = str(Path(trial['argv'][0]).parent / 'vllm')
    tokenizer = trial['argv'][trial['argv'].index('--model') + 1]
    env = dict(os.environ)
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', OPENAI_API_KEY='EMPTY', NO_PROXY='127.0.0.1,localhost')
    env.pop('PYTHONPATH', None)
    for concurrency in plan['workload']['client_concurrencies']:
        for cache_state in plan['workload']['cache_states']:
            name = 'c' + str(concurrency) + '-' + cache_state
            argv = [executable, 'bench', 'serve', '--backend', 'openai', '--base-url', URL,
                    '--endpoint', '/v1/completions', '--model', model, '--tokenizer', tokenizer,
                    '--dataset-name', 'random', '--random-input-len', '1024', '--random-output-len', '256',
                    '--random-range-ratio', '1.0', '--random-prefix-len', '0', '--num-prompts', '16',
                    '--max-concurrency', str(concurrency), '--seed', str({2: 0, 4: 1}[concurrency]),
                    '--ignore-eos', '--num-warmups', '0', '--ready-check-timeout-sec', '0',
                    '--save-result', '--save-detailed', '--result-dir', str(directory),
                    '--result-filename', name + '.json', '--percentile-metrics', 'ttft,tpot,itl,e2el',
                    '--metric-percentiles', '50,95,99', '--disable-tqdm']
            write_json(directory / (name + '-command.json'), {'argv': argv})
            peak = 0
            with (directory / (name + '.log')).open('xb') as stream:
                child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                worker = process(child.pid)
                deadline = time.monotonic() + 1200
                try:
                    while child.poll() is None:
                        if time.monotonic() > deadline:
                            raise TimeoutError('PERFORMANCE_WORKLOAD_TIMEOUT')
                        memory = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True, timeout=10)
                        peak = max(peak, max(int(line.strip()) for line in memory.splitlines()))
                        time.sleep(1)
                finally:
                    if child.poll() is None and worker and same_process(worker):
                        stop_owned_group(worker)
                if child.returncode != 0:
                    raise RuntimeError('PERFORMANCE_WORKLOAD_FAILED:' + str(child.returncode))
            result_path = directory / (name + '.json')
            result = json.loads(result_path.read_text())
            keys = ['duration', 'completed', 'failed', 'total_input_tokens', 'total_output_tokens',
                    'output_throughput', 'mean_ttft_ms', 'mean_tpot_ms', 'p95_e2el_ms']
            measurement = {key: result.get(key) for key in keys}
            measurement.update(name=name, client_concurrency=concurrency, seed={2: 0, 4: 1}[concurrency],
                               cache_state=cache_state, gpu_memory_peak_mib=peak,
                               result_path=str(result_path.relative_to(ROOT)), result_sha256=sha(result_path))
            if any(isinstance(v, float) and not math.isfinite(v) for v in measurement.values()):
                raise ValueError('NONFINITE_PERFORMANCE_RESULT')
            trial['measurements'].append(measurement)
            save(state)
            if result.get('completed') != 16 or result.get('failed') != 0 or result.get('total_output_tokens') != 4096:
                raise ValueError('INCOMPLETE_PERFORMANCE_WORKLOAD')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    base = json.loads(BASE.read_text())
    if sha(BASE) != plan['base_command_sha256']:
        raise ValueError('BASE_COMMAND_CHANGED')
    if any(trial['argv'][trial['argv'].index('--model') + 1] != base['argv'][base['argv'].index('--model') + 1] for trial in plan['trials']):
        raise ValueError('MODEL_WEIGHTS_MUST_REMAIN_FIXED')
    if args.preflight:
        print(json.dumps({'status': 'PREFLIGHT_ONLY_NO_MODEL_CALLS', 'trials': len(plan['trials']),
                          'dependencies': [same_process(p) for p in plan['required_dependencies']]}))
        return
    OUTPUT.mkdir(exist_ok=False)
    state = {'status': 'WAITING_FOR_QUALITY_BENCHMARKS', 'pid': os.getpid(), 'trials': [],
             'plan_sha256': sha(PLAN), 'executor_sha256': sha(Path(__file__)),
             'required_dependencies': plan['required_dependencies'], 'owned_server': None,
             'restored': False, 'quality_acceptance': 'NOT_ACCEPTED'}
    save(state)
    original_stopped = False
    try:
        deadline = time.monotonic() + 24 * 3600
        while any(same_process(p) for p in plan['required_dependencies']):
            if time.monotonic() > deadline:
                raise TimeoutError('DEPENDENCY_WAIT_EXCEEDED_24H')
            time.sleep(30)
        completed = json.loads((ROOT / 'artifacts/benchmark-27b-full-status.json').read_text())
        pilot = json.loads((ROOT / 'artifacts/task-plan-pilot-queue.json').read_text())
        if len(completed) != 4 or any('exit_code' not in item for item in completed):
            raise RuntimeError('V4_TERMINAL_RECORDS_MISSING')
        if pilot['status'] != 'PILOT_FINISHED_REVIEW_REQUIRED':
            raise RuntimeError('TASK_PLAN_PILOT_NOT_FINISHED')
        if sha(PLAN) != state['plan_sha256'] or sha(BASE) != plan['base_command_sha256']:
            raise RuntimeError('SERVING_PLAN_CHANGED_WHILE_WAITING')
        current = plan['current_model_process']
        actual_argv = server_command(current['pid'])
        if actual_argv != base['argv']:
            raise RuntimeError('MODEL_COMMAND_CHANGED')
        assert_idle()
        state['status'] = 'STOPPING_ORIGINAL_SERVER'
        save(state)
        # From this point all failures require a restoration attempt.
        original_stopped = True
        stop_owned_group(current)
        for specification in plan['trials']:
            assert_no_clients()
            directory = OUTPUT / specification['id']
            directory.mkdir()
            trial = {'id': specification['id'], 'argv': specification['argv'], 'status': 'STARTING', 'measurements': []}
            state['trials'].append(trial)
            state['status'] = 'RUNNING_TUNING'
            save(state)
            try:
                identity, seconds = start_server(trial['argv'], directory / 'server.log', state)
                trial.update(server_identity=identity, startup_seconds=seconds, status='CHECKING')
                trial['checks'] = checks(trial['argv'][trial['argv'].index('--served-model-name') + 1])
                save(state)
                if not all(item['passed'] for item in trial['checks']):
                    raise RuntimeError('CORRECTNESS_CHECK_FAILED')
                trial['status'] = 'MEASURING'
                measure(trial, plan, directory, state)
                trial['status'] = 'MEASURED_REVIEW_REQUIRED'
            except Exception as exc:
                trial.update(status='FAILED_REVIEW_REQUIRED', error=type(exc).__name__ + ':' + str(exc))
            finally:
                owned = state.get('owned_server')
                if owned:
                    stop_owned_group(owned)
                state['owned_server'] = None
                save(state)
        state['status'] = 'TUNING_FINISHED_REVIEW_REQUIRED'
    except Exception as exc:
        state.update(status='STOPPED_REVIEW_REQUIRED', error=type(exc).__name__ + ':' + str(exc))
    finally:
        if original_stopped:
            try:
                owned = state.get('owned_server')
                if owned:
                    stop_owned_group(owned)
                if group_members(plan['current_model_process']['pid']):
                    raise RuntimeError('ORIGINAL_GROUP_STILL_PRESENT')
                identity, seconds = start_server(base['argv'], OUTPUT / 'restored-server.log', state)
                state.update(restored=True, restored_server=identity, restoration_startup_seconds=seconds)
                write_json(ROOT / 'artifacts/vllm-restored-server.json', {'argv': base['argv'], **identity, 'health': 'MODELS_ENDPOINT_READY'})
            except Exception as exc:
                state.update(status='RESTORATION_FAILED_REVIEW_REQUIRED', restoration_error=type(exc).__name__ + ':' + str(exc))
        save(state)


if __name__ == '__main__':
    main()
