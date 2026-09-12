#!/usr/bin/env python3
"""Write live benchmark progress only; this process never grants acceptance."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def snapshot(path):
    manifest = path / "manifest.json"
    if not manifest.exists():
        return {
            "run": str(path),
            "status": "QUEUED",
            "planned": None,
            "recorded": 0,
            "valid": 0,
        }
    plan = json.loads(manifest.read_text())
    raw = path / "per_case.jsonl"
    lines = raw.read_text().splitlines() if raw.exists() else []
    rows, partial = [], False
    for index, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines) - 1:
                raise ValueError("CORRUPT_RESULT_LOG")
            partial = True  # concurrent append; retry on the next snapshot
    ids = [r["case_id"] for r in rows]
    if len(ids) != len(set(ids)) or not set(ids) <= set(plan["planned_ids"]):
        raise ValueError("DUPLICATE_OR_UNPLANNED_RESULT")
    valid = sum(r.get("status") == "ok" and r.get("valid", True) for r in rows)
    return {
        "run": str(path),
        "status": "RECORDED_NOT_ACCEPTED"
        if (path / "metrics.json").exists()
        else "RUNNING",
        "planned": len(plan["planned_ids"]),
        "recorded": len(rows),
        "valid": valid,
        "invalid_or_error": len(rows) - valid,
        "partial_line_pending": partial,
    }


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(text)
    os.replace(temporary, path)


def process_identity(pid):
    try:
        fields = (
            (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        )
        return fields[19] if fields[0] != "Z" else None
    except (OSError, IndexError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--batch-pid", type=int)
    args = parser.parse_args()
    identity = process_identity(args.batch_pid) if args.batch_pid else None
    while True:
        rows = []
        for path in args.run:
            try:
                rows.append(snapshot(path))
            except (ValueError, OSError) as exc:
                rows.append(
                    {
                        "run": str(path),
                        "status": "PROGRESS_READ_ERROR",
                        "error": type(exc).__name__,
                    }
                )
        stopped = bool(
            args.batch_pid
            and (not identity or process_identity(args.batch_pid) != identity)
        )
        if stopped:
            for row in rows:
                if row["status"] in {"QUEUED", "RUNNING"}:
                    row["status"] = "BATCH_STOPPED_WITHOUT_COMPLETE_RESULTS"
        report = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "overall": "NOT_ACCEPTED",
            "batch_stopped": stopped,
            "runs": rows,
        }
        atomic(
            Path("docs/evidence/live-benchmark-progress.json"),
            json.dumps(report, indent=2) + "\n",
        )
        text = (
            "# Benchmark 实时进度\n\n更新："
            + report["updated_at"]
            + "。本页每15秒更新，仅为运行进度；正式验收仍为 **NOT_ACCEPTED**。\n\n"
        )
        text += "| 运行目录 | 状态 | 计划 | 已记录 | 有效 |\n|---|---|---:|---:|---:|\n"
        text += "\n".join(
            f"| {r['run']} | {r['status']} | {r.get('planned', '—')} | {r.get('recorded', '—')} | {r.get('valid', '—')} |"
            for r in rows
        )
        text += "\n\n空缺结果、错误和无效输出不能算作防护成功。RECORDED_NOT_ACCEPTED 仅表示结果工件已写出；通过门槛、全量攻击、重复/消融及独立标注仍需配对验收报告。若进程停止，更新时间不会继续变化。\n"
        atomic(Path("docs/05-validation/live-benchmark-progress.md"), text)
        if (
            args.once
            or stopped
            or all(r["status"] == "RECORDED_NOT_ACCEPTED" for r in rows)
        ):
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
