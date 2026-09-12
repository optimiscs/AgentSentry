"""Finite frozen ASB pilot after serving experiments release and restore the GPU."""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/autodl-tmp/AgentSentry')
CANDIDATE = ROOT / 'artifacts/development/asb-local-v1'
OUTPUT = ROOT / 'artifacts/asb-pilot-v1'
STATE = ROOT / 'docs/evidence/asb-pilot-progress.json'
REPORT = ROOT / 'docs/05-validation/asb-pilot-progress.md'
DEPENDENCY = {'pid': 684948, 'start_ticks': '442655721'}
PINS = {
    'artifacts/development/asb-local-v1/candidate-manifest.json': '7c2982b6a64f3e0ffdc0ed0bd812893f32ab4d22e9485039604cc3c61ee82151',
    'artifacts/asb-protocol-v1/scenario-index.jsonl': '66c492187839f941332e5f1a7c77f6e9d5394536f9e2143622cb8759264f8d62',
    'artifacts/asb-memory-e5-v1/manifest.json': '22519988182c24a5bc315ce76f66c40f0f33e5cbd7438b1ff0f56fd6327ee411',
    'artifacts/local-model-27b-32k-command.json': '48c8bfd1abb77eaa56924956b394a192ae3c81834ea56a540515d3d9f04bf82a',
    'artifacts/vllm-tuning-plan.json': 'ea8975fee697cda7d64ff410c2f47768f139d7b72b0a9e051ac0c55b57f7d18e',
    'artifacts/run_vllm_tuning_after_benchmarks.py': '1c2ef72aefd6f24e4cefe510838d80b50362e953f8a90139ad808cf324710183',
}


def load_helper():
    path = ROOT / 'artifacts/run_vllm_tuning_after_benchmarks.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != PINS[str(path.relative_to(ROOT))]:
        raise ValueError('FROZEN_QUEUE_HELPER_CHANGED')
    spec = importlib.util.spec_from_file_location('frozen_serving_checks', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def verify_inputs(helper):
    for name, expected in PINS.items():
        if helper.sha(ROOT / name) != expected:
            raise ValueError('ASB_PILOT_INPUT_CHANGED:' + name)
    candidate = json.loads((CANDIDATE / 'candidate-manifest.json').read_text())
    if candidate['archive_sha256'] != 'f473485ab1149a1c42cf355a2a8a6e2af700d4b962db32f2c492a6f0b9d671a9':
        raise ValueError('ASB_CANDIDATE_ARCHIVE_CHANGED')
    for name, expected in candidate['files'].items():
        if helper.sha(CANDIDATE / name) != expected:
            raise ValueError('ASB_CANDIDATE_SOURCE_CHANGED:' + name)
    memory = ROOT / 'artifacts/asb-memory-e5-v1'
    for name, expected in json.loads((memory / 'manifest.json').read_text())['files'].items():
        if helper.sha(memory / name) != expected:
            raise ValueError('ASB_MEMORY_CHANGED:' + name)
    plan = {}
    for line in (ROOT / 'artifacts/asb-protocol-v1/scenario-index.jsonl').read_text().splitlines():
        row = json.loads(line)
        plan.setdefault((row['mode'], row['agent']), row['case_id'])
    if len(plan) != 40 or len(set(plan.values())) != 40:
        raise ValueError('ASB_PILOT_SELECTION_CHANGED')
    return list(plan.values())


def restored_identity(helper):
    report = json.loads((ROOT / 'docs/evidence/vllm-tuning-report.json').read_text())
    if (report.get('status') != 'TUNING_FINISHED_REVIEW_REQUIRED' or report.get('restored') is not True
            or report.get('pid') != DEPENDENCY['pid']):
        raise ValueError('TUNING_NOT_FINISHED_AND_RESTORED')
    if report.get('plan_sha256') != PINS['artifacts/vllm-tuning-plan.json']:
        raise ValueError('TUNING_PLAN_CHANGED')
    if report.get('executor_sha256') != PINS['artifacts/run_vllm_tuning_after_benchmarks.py']:
        raise ValueError('TUNING_EXECUTOR_CHANGED')
    record = json.loads((ROOT / 'artifacts/vllm-restored-server.json').read_text())
    expected = report.get('restored_server')
    if not expected or any(record.get(key) != value for key, value in expected.items()) or not helper.same_process(expected):
        raise ValueError('RESTORED_SERVER_IDENTITY_CHANGED')
    base = json.loads((ROOT / 'artifacts/local-model-27b-32k-command.json').read_text())
    if record.get('argv') != base['argv'] or helper.server_command(record['pid']) != base['argv']:
        raise ValueError('RESTORED_SERVER_COMMAND_CHANGED')
    return expected


def save(helper, state):
    state['updated_at'] = datetime.now(timezone.utc).isoformat()
    helper.write_json(STATE, state)
    rows = ['# ASB 本地模型配对小样', '', '状态：`' + state['status'] + '`。更新：' + state['updated_at'],
            '', '固定asb-local-v1；四种混合攻击各10例，每组40例，基线/完整防护共80例。',
            '等待vLLM调优进程结束，并核验原服务恢复后开始。小样用于判断适配可行性，不是1600场景全量验收。', '',
            '| 配置 | 状态 | 记录 / 计划 | 有效 |', '|---|---|---:|---:|']
    for job in state['jobs']:
        metrics = job.get('metrics', {})
        rows.append('| ' + job['configuration'] + ' | ' + job['status'] + ' | '
                    + str(metrics.get('recorded_cases', 0)) + '/40 | ' + str(metrics.get('valid_cases', 0)) + ' |')
    rows += ['', '原生文本代理分数、模拟分派结果和错误分别保留；ASK不自动批准。',
             '版本、命令与模型状态见[机器进度](../evidence/asb-pilot-progress.json)。', '']
    temporary = REPORT.with_suffix('.tmp')
    temporary.write_text('\n'.join(rows))
    temporary.replace(REPORT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    helper = load_helper()
    planned_ids = verify_inputs(helper)
    if args.preflight:
        print(json.dumps({'status': 'PREFLIGHT_ONLY_NO_MODEL_CALLS', 'planned_per_configuration': len(planned_ids),
                          'dependency_is_live': helper.same_process(DEPENDENCY), 'frozen_inputs_verified': True}))
        return
    OUTPUT.mkdir(exist_ok=False)
    state = {'status': 'WAITING_FOR_TUNING_RESTORATION', 'pid': os.getpid(), 'dependency': DEPENDENCY,
             'executor_sha256': helper.sha(Path(__file__)), 'pins': PINS, 'planned_ids': planned_ids,
             'planned_records': 80, 'quality_acceptance': 'NOT_ACCEPTED', 'jobs': []}
    save(helper, state)
    try:
        deadline = time.monotonic() + 24 * 3600
        while helper.same_process(DEPENDENCY):
            if time.monotonic() > deadline:
                raise TimeoutError('DEPENDENCY_WAIT_EXCEEDED_24H')
            time.sleep(30)
        verify_inputs(helper)
        identity = restored_identity(helper)
        state['restored_server'] = identity
        env = dict(os.environ)
        env.update(PYTHONPATH=str(CANDIDATE / 'src') + ':' + str(CANDIDATE / 'benchmarks'),
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        for configuration in ('baseline', 'full'):
            if helper.sha(Path(__file__)) != state['executor_sha256']:
                raise ValueError('ASB_PILOT_EXECUTOR_CHANGED')
            verify_inputs(helper)
            if restored_identity(helper) != identity:
                raise ValueError('MODEL_CHANGED_BETWEEN_ASB_PAIRS')
            helper.assert_idle()
            output = ROOT / ('artifacts/benchmarks/asb/asb-local-v1-pilot-' + configuration + '-s0')
            output.mkdir(parents=True, exist_ok=False)
            argv = [str(ROOT / 'artifacts/benchmark-venv/bin/python'), 'benchmarks/run_asb.py',
                    '--source', str(ROOT / 'artifacts/upstream/ASB-1f561dccf92d'),
                    '--index', str(ROOT / 'artifacts/asb-protocol-v1/scenario-index.jsonl'),
                    '--memory', str(ROOT / 'artifacts/asb-memory-e5-v1'), '--output', str(output),
                    '--configuration', configuration, '--modes', 'mixed', 'DPI_OPI', 'DPI_MP', 'OPI_MP',
                    '--limit-per-agent', '1', '--workers', '2', '--max-tokens', '4096',
                    '--guard-max-tokens', '4096', '--max-workflow-steps', '12', '--seed', '0']
            job = {'configuration': configuration, 'argv': argv, 'status': 'RUNNING'}
            state['jobs'].append(job)
            state['status'] = 'RUNNING_ASB_PILOT'
            save(helper, state)
            with (OUTPUT / (configuration + '.log')).open('xb') as log:
                result = subprocess.run(argv, cwd=CANDIDATE, env=env, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=7200, check=False)
            job.update(status='RECORDED_NOT_ACCEPTED', exit_code=result.returncode)
            if (output / 'metrics.json').exists():
                job['metrics'] = json.loads((output / 'metrics.json').read_text())
            if (output / 'manifest.json').exists():
                manifest = json.loads((output / 'manifest.json').read_text())
                if manifest['planned_ids'] != planned_ids:
                    raise ValueError('ASB_CASE_MANIFEST_CHANGED')
                job['manifest_sha256'] = helper.sha(output / 'manifest.json')
            save(helper, state)
        state['status'] = 'ASB_PILOT_FINISHED_REVIEW_REQUIRED'
        save(helper, state)
    except Exception as exc:
        state.update(status='STOPPED_REVIEW_REQUIRED', error=type(exc).__name__ + ':' + str(exc))
        save(helper, state)
        raise


if __name__ == '__main__':
    main()
