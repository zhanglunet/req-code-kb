"""Measure the local stages of one reqkb build, without keeping its output."""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reqkb.parse import parse_repo
from reqkb.render import render_page, update_index
from reqkb.retrieve import build_context


def measure_build(repo: Path, req: Path, requirement: str) -> tuple[tuple[float, ...], int, int, int, int]:
    with TemporaryDirectory(prefix="reqkb-build-timing-") as kb_dir:
        page_dir = Path(kb_dir) / "requirements"
        start = perf_counter()
        files = parse_repo(str(repo))
        parsed = perf_counter()
        context = build_context(files, req.stem, requirement)
        retrieved = perf_counter()
        page = render_page(context, "", "main", str(req), [])
        rendered = perf_counter()
        page_dir.mkdir()
        (page_dir / f"{context.req_id}.md").write_text(page, encoding="utf-8")
        update_index(kb_dir, context)
        written = perf_counter()

    timings = (parsed - start, retrieved - parsed, rendered - retrieved,
               written - rendered, written - start)
    symbols = sum(len(info.symbols) for info in files.values())
    return timings, len(files), symbols, len(context.files), context.total_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="local source directory")
    parser.add_argument("--req", required=True, type=Path, help="requirement Markdown file")
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    if not args.repo.is_dir():
        parser.error("--repo must be an existing local directory")
    if not args.req.is_file():
        parser.error("--req must be an existing file")
    if args.repeat < 1:
        parser.error("--repeat must be positive")

    requirement = args.req.read_text(encoding="utf-8")
    samples = []
    for run in range(1, args.repeat + 1):
        sample, indexed, symbols, selected, tokens = measure_build(
            args.repo, args.req, requirement
        )
        samples.append(sample)
        print(f"run={run} indexed_files={indexed} symbols={symbols} "
              f"selected_files={selected} tokens={tokens} "
              f"total={sample[-1]:.6f}s", flush=True)

    stages = ("parse", "retrieve", "render", "write", "total")
    print("median_seconds " + " ".join(
        f"{stage}={median(values):.6f}" for stage, values in zip(stages, zip(*samples))
    ))


if __name__ == "__main__":
    main()
