#!/usr/bin/env python3
import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

CUTOFF = 2010123118
STAMP_RE = re.compile(r"^\d{10}$")


@dataclass(frozen=True)
class TaskLine:
    subdir: str
    stamp: str


def _manifest_task_1a() -> List[TaskLine]:
    return [
        TaskLine("amsua_aqua", "2002101200"),
        TaskLine("amsua_aqua", "2007110212"),
        TaskLine("amsua_metop-a", "2007052100"),
        TaskLine("amsua_metop-a", "2009011512"),
        TaskLine("amsua_n15", "1998110100"),
        TaskLine("amsua_n15", "1999010112"),
        TaskLine("amsua_n16", "2000110500"),
        TaskLine("amsua_n16", "2001011200"),
        TaskLine("amsua_n16", "2002090800"),
        TaskLine("amsua_n16", "2002112800"),
        TaskLine("amsua_n16", "2003051212"),
        TaskLine("amsua_n16", "2004061700"),
        TaskLine("amsua_n17", "2002071500"),
        TaskLine("amsua_n18", "2005100100"),
        TaskLine("amsua_n18", "2007111618"),
        TaskLine("amsua_n19", "2009041400"),
        TaskLine("amsua_n19", "2009122200"),
    ]


def _manifest_task_1b() -> List[TaskLine]:
    return [
        TaskLine("ssu_n06", "1979070200"),
        TaskLine("ssu_n06", "1985040800"),
        TaskLine("ssu_n07", "1981071100"),
        TaskLine("ssu_n07", "1983070100"),
        TaskLine("ssu_n07", "1985020412"),
        TaskLine("ssu_n08", "1983042600"),
        TaskLine("ssu_n09", "1985032400"),
        TaskLine("ssu_n11", "1988092800"),
        TaskLine("ssu_n14", "1995011900"),
    ]


def _manifest_task_2() -> List[TaskLine]:
    return [
        TaskLine("ssu_n06", "1900010100"),
        TaskLine("ssu_n06", "1983041718"),
        TaskLine("ssu_n06", "1986111800"),
        TaskLine("ssu_n07", "1900010100"),
        TaskLine("ssu_n07", "1985020406"),
        TaskLine("ssu_n07", "1985021900"),
        TaskLine("ssu_n08", "1900010100"),
        TaskLine("ssu_n08", "1984062100"),
        TaskLine("ssu_n09", "1900010100"),
        TaskLine("ssu_n09", "1985010100"),
        TaskLine("ssu_n09", "1988110800"),
        TaskLine("ssu_n11", "1900010100"),
        TaskLine("ssu_n11", "1995010100"),
        TaskLine("ssu_n11", "1998110100"),
        TaskLine("ssu_n11", "1999022600"),
        TaskLine("ssu_n14", "1900010100"),
        TaskLine("ssu_n14", "1998110100"),
        TaskLine("ssu_n14", "2006050500"),
        TaskLine("ssu_tirosn", "1900010100"),
        TaskLine("ssu_tirosn", "1978120100"),
        TaskLine("ssu_tirosn", "1981020500"),
    ]


NON_SSU_NEG4_GUARD = [
    Path("satinfo/atms_n20/1900010100"),
    Path("satinfo/atms_npp/1900010100"),
    Path("satinfo/mws_metop-sg-a1/1900010100"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_token(line: str, start: int, end: int, value: str) -> str:
    width = end - start
    if len(value) > width:
        raise ValueError(f"value '{value}' wider than token span width {width}")
    return line[:start] + value.rjust(width) + line[end:]


def find_tokens(line_no_nl: str) -> List[re.Match[str]]:
    return list(re.finditer(r"\S+", line_no_nl))


def ensure_no_overlap(*groups: List[TaskLine]) -> None:
    all_keys = []
    for group in groups:
        all_keys.extend((item.subdir, item.stamp) for item in group)
    if len(all_keys) != len(set(all_keys)):
        raise AssertionError("task manifests overlap")


def apply_line_rule(rule: str, line: str) -> Tuple[str, bool, Dict[str, str]]:
    line_no_nl = line[:-1] if line.endswith("\n") else line
    newline = "\n" if line.endswith("\n") else ""
    toks = find_tokens(line_no_nl)
    if len(toks) != 11:
        return line, False, {}

    vals = [line_no_nl[m.start() : m.end()] for m in toks]

    if rule == "task1a":
        if vals[1] != "14" or vals[2] != "4" or vals[3] != "4.000" or vals[4] != "4.000":
            return line, False, {}
        updated = line_no_nl
        updated = replace_token(updated, toks[3].start(), toks[3].end(), "1.000")
        updated = replace_token(updated, toks[4].start(), toks[4].end(), "1.000")
        return updated + newline, True, {"old_f5": vals[4], "new_f5": "1.000"}

    if rule == "task1b":
        if vals[1] != "3" or vals[2] != "4" or vals[3] != "1.500" or vals[4] != "0.000":
            return line, False, {}
        updated = replace_token(line_no_nl, toks[3].start(), toks[3].end(), "1.000")
        new_toks = find_tokens(updated)
        new_vals = [updated[m.start() : m.end()] for m in new_toks]
        return updated + newline, True, {"old_f5": vals[4], "new_f5": new_vals[4]}

    if rule == "task2":
        if vals[1] != "3" or vals[2] != "-4":
            return line, False, {}
        updated = replace_token(line_no_nl, toks[2].start(), toks[2].end(), "-1")
        new_toks = find_tokens(updated)
        new_vals = [updated[m.start() : m.end()] for m in new_toks]
        return (
            updated + newline,
            True,
            {
                "old_f4": vals[3],
                "old_f5": vals[4],
                "old_f6": vals[5],
                "new_f4": new_vals[3],
                "new_f5": new_vals[4],
                "new_f6": new_vals[5],
            },
        )

    raise ValueError(f"unknown rule {rule}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply exact satinfo iuse/error fixes")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    satinfo_root = root / "satinfo"

    task1a = _manifest_task_1a()
    task1b = _manifest_task_1b()
    task2 = _manifest_task_2()

    ensure_no_overlap(task1a, task1b, task2)

    expected_ssu = {"ssu_n06", "ssu_n07", "ssu_n08", "ssu_n09", "ssu_n11", "ssu_n14", "ssu_tirosn"}
    actual_ssu = {d.name for d in satinfo_root.iterdir() if d.is_dir() and d.name.startswith("ssu_")}
    if actual_ssu != expected_ssu:
        raise AssertionError(f"SSU subdir mismatch: expected={sorted(expected_ssu)} actual={sorted(actual_ssu)}")

    out_scope_iuse4_files: List[Path] = []
    for sensor_dir in sorted(d for d in satinfo_root.iterdir() if d.is_dir() and not d.name.startswith("ssu_")):
        for f in sorted(sensor_dir.iterdir()):
            if not f.is_file() or not STAMP_RE.match(f.name):
                continue
            if int(f.name) <= CUTOFF:
                continue
            has_iuse4 = False
            for raw in f.read_text().splitlines():
                toks = re.findall(r"\S+", raw)
                if len(toks) == 11 and toks[2] == "4":
                    has_iuse4 = True
                    break
            if has_iuse4:
                out_scope_iuse4_files.append(f.relative_to(root))

    if len(out_scope_iuse4_files) != 11:
        raise AssertionError(f"expected 11 out-of-scope non-SSU iuse=4 files, found {len(out_scope_iuse4_files)}")

    guard_paths = sorted(set(out_scope_iuse4_files + NON_SSU_NEG4_GUARD))
    guard_hash_before = {p: sha256(root / p) for p in guard_paths}

    plan: List[Tuple[str, TaskLine]] = []
    plan.extend(("task1a", x) for x in task1a)
    plan.extend(("task1b", x) for x in task1b)
    plan.extend(("task2", x) for x in task2)

    total_changed_files = 0
    total_changed_lines = 0
    per_task_counts = {"task1a": 0, "task1b": 0, "task2": 0}
    changed_summaries: List[str] = []

    for rule, item in plan:
        rel = Path("satinfo") / item.subdir / item.stamp
        path = root / rel
        if not path.exists():
            raise FileNotFoundError(str(path))

        before_lines = path.read_text().splitlines(keepends=True)
        after_lines = before_lines.copy()

        changed_indices = []
        meta_records = []
        for idx, line in enumerate(before_lines):
            updated, changed, meta = apply_line_rule(rule, line)
            if changed:
                after_lines[idx] = updated
                changed_indices.append(idx)
                meta_records.append(meta)

        if len(changed_indices) != 1:
            raise AssertionError(f"{rel}: expected exactly 1 changed line for {rule}, got {len(changed_indices)}")

        idx = changed_indices[0]
        if len(before_lines[idx]) != len(after_lines[idx]):
            raise AssertionError(f"{rel}: line length changed")

        if rule == "task1b":
            meta = meta_records[0]
            if meta["old_f5"] != meta["new_f5"]:
                raise AssertionError(f"{rel}: task1b field5 changed unexpectedly")
            if meta["new_f5"] != "0.000":
                raise AssertionError(f"{rel}: task1b field5 is not 0.000")

        if rule == "task2":
            meta = meta_records[0]
            if meta["old_f4"] != meta["new_f4"] or meta["old_f5"] != meta["new_f5"] or meta["old_f6"] != meta["new_f6"]:
                raise AssertionError(f"{rel}: task2 changed field 4/5/6 unexpectedly")

        if before_lines != after_lines:
            total_changed_files += 1
            total_changed_lines += 1
            per_task_counts[rule] += 1
            changed_summaries.append(f"{rel}: line {idx + 1} ({rule})")
            if not args.dry_run:
                path.write_text("".join(after_lines))

    if total_changed_files != 47 or total_changed_lines != 47:
        raise AssertionError(
            f"expected 47 files/47 lines changed, got {total_changed_files} files/{total_changed_lines} lines"
        )

    if per_task_counts != {"task1a": 17, "task1b": 9, "task2": 21}:
        raise AssertionError(f"per-task counts mismatch: {per_task_counts}")

    guard_hash_after = {p: sha256(root / p) for p in guard_paths}
    for p in guard_paths:
        if guard_hash_before[p] != guard_hash_after[p]:
            raise AssertionError(f"out-of-scope file changed unexpectedly: {p}")

    print("Planned/Applied changes:")
    for line in changed_summaries:
        print(f"  {line}")

    print(f"Totals: files={total_changed_files} lines={total_changed_lines}")
    print(f"Per-task: task1a={per_task_counts['task1a']} task1b={per_task_counts['task1b']} task2={per_task_counts['task2']}")
    print("Verified: SSU set, field5 preservation (task1b+task2), and out-of-scope byte-identity guards")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
