"""Start or stop the system under test (fde-02) with a named configuration from config/sut.yaml.

    python scripts/sut.py up --config advanced --index /path/to/index [--port 8001]
    python scripts/sut.py down

FDE02_DIR points at a checkout of fde-02-llm-applications with its virtualenv installed
(default ../fde-02-llm-applications). The process id goes to runs/.sut.pid.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml

PID_FILE = Path("runs/.sut.pid")


def up(args) -> int:
    configs = yaml.safe_load(Path("config/sut.yaml").read_text())["configs"]
    if args.config not in configs:
        raise SystemExit(f"unknown config {args.config!r}; have {sorted(configs)}")
    fde02 = Path(os.getenv("FDE02_DIR", "../fde-02-llm-applications")).resolve()
    python = fde02 / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)
    env = os.environ | {k: str(v) for k, v in configs[args.config].items()}
    env["INDEX_DIR"] = str(Path(args.index).resolve())
    env["DATA_DIR"] = str((fde02 / "data").resolve())
    # The checkout's own source first, so several versions can share one virtualenv.
    env["PYTHONPATH"] = os.pathsep.join(p for p in [str(fde02 / "src"), str(fde02),
                                                    env.get("PYTHONPATH", "")] if p)
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = (PID_FILE.parent / "sut.log").open("w")
    proc = subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--port",
                             str(args.port)], cwd=fde02, env=env, stdout=log, stderr=log)
    PID_FILE.write_text(str(proc.pid))
    url = f"http://127.0.0.1:{args.port}/health/ready"
    for _ in range(int(args.wait * 2)):
        try:
            ready = httpx.get(url, timeout=60).json()    # first call loads the index
            if ready.get("status") == "ready":
                wanted = configs[args.config].get("RETRIEVAL_MODE")
                if wanted and ready.get("retrieval") not in (None, wanted):
                    # fde-02 falls back to BM25 when the index has no dense vectors; a run
                    # labelled "hybrid" would then measure the wrong system.
                    sys.stderr.write(f"SUT runs {ready.get('retrieval')!r}, config wants "
                                     f"{wanted!r} (dense vectors missing?)\n")
                    down(args)
                    return 1
                # Warm-up: the first queries load dense vectors lazily; without this the
                # first cases of a run measure start-up, not answering (p95 8.3 s vs 1.2 s).
                for _ in range(2):
                    httpx.post(url.replace("/health/ready", "/api/v1/ask"), timeout=120,
                               json={"question": "What was total revenue in the latest year?"})
                sys.stdout.write(f"SUT ready ({args.config}): {ready}\n")
                return 0
        except (httpx.HTTPError, ValueError):
            pass
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    sys.stderr.write(f"SUT did not become ready; see {PID_FILE.parent / 'sut.log'}\n")
    down(args)
    return 1


def down(_args) -> int:
    if PID_FILE.exists():
        try:
            os.kill(int(PID_FILE.read_text()), signal.SIGTERM)
        except ProcessLookupError:
            pass
        PID_FILE.unlink()
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("up")
    u.add_argument("--config", default="advanced")
    u.add_argument("--index", required=True)
    u.add_argument("--port", type=int, default=8001)
    u.add_argument("--wait", type=float, default=120)
    u.set_defaults(fn=up)
    sub.add_parser("down").set_defaults(fn=down)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
