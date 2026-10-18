"""Test subprocess nesting — mimics what the GUI app does."""
import multiprocessing as mp
import queue
import sys
import time

from plate_nesting.geometry.seg import Seg
from plate_nesting.materials.inventory import SheetInventory
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet
from plate_nesting.nesting.job import nest_job_subprocess


def main():
    outer = [
        Seg(p0=(0, 0), p1=(200, 0)),
        Seg(p0=(200, 0), p1=(200, 100)),
        Seg(p0=(200, 100), p1=(0, 100)),
        Seg(p0=(0, 100), p1=(0, 0)),
    ]
    parts = [
        Part(name="P1", outer=outer, length=200, width=100,
             thickness=10, grade="350W", qty=2),
    ]
    sheets = [Sheet(6000, 2000, grade="350W", thickness=10)]
    inv = SheetInventory(standard_sizes=sheets)
    opts = NestOptions(time_budget=5)

    q = mp.Queue()
    p = mp.Process(target=nest_job_subprocess, args=(q, parts, inv, opts), daemon=True)
    print(f"Starting subprocess...")
    p.start()

    while True:
        try:
            kind, data = q.get(timeout=0.5)
        except queue.Empty:
            if not p.is_alive():
                print(f"Process died! exit code: {p.exitcode}")
                break
            print(f"  waiting... (pid={p.pid}, alive={p.is_alive()})")
            continue

        if kind == "stage":
            print(f"  Stage: {data}")
        elif kind == "ok":
            print(f"SUCCESS: {data.total_sheets} sheets, "
                  f"{data.total_parts_placed} parts, "
                  f"{data.avg_utilization * 100:.1f}% util")
            break
        elif kind == "error":
            print(f"ERROR: {data}")
            break

    p.join(timeout=5)
    print(f"Exit code: {p.exitcode}")


if __name__ == "__main__":
    main()
