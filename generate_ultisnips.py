#!/usr/bin/env python
import sys
from collections import Counter
from pathlib import Path

from parse_playbook import Playbook

# If more then this number of arguments are found for a module, rarely used
# arguments are stripped
FILTER_IF_MORE_THAN = 10
# If the filtering is used (see above), arguments used less often then this are
# not added to the snippet
FILTER_THRESHOLD = 2


def get_all_tasks(playbook):
    pb = Playbook(playbook)
    return pb.find_all_tasks()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file or directory>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print("Path does not exist")
        sys.exit(1)

    all_tasks = []
    if file_path.is_file():
        all_tasks = get_all_tasks(file_path)
    elif file_path.is_dir():
        for file in file_path.iterdir():
            if (
                file.suffix in [".yaml", ".yml"]
                and "test" not in file.stem
                and not file.match(".*")
            ):
                try:
                    all_tasks.extend(get_all_tasks(file))
                except:
                    print(f"WARNING: Failed to parse file {file} – skipping")
    else:
        return "Invalid path or file does not exist"

    stat = {}
    for task in all_tasks:
        if task.is_block():
            continue
        try:
            typ = task.get_type()
        except ValueError:
            continue
        args_raw = task.get_args()
        if args_raw is None:
            continue
        if isinstance(args_raw, str):
            continue
        args = args_raw.keys()
        if typ not in stat:
            stat[typ] = Counter()
        stat[typ].update(args)
    with open("snips", "w") as f:
        for module in stat:
            f.write(f"snippet {module}\n")
            f.write(f"{module}:\n")
            large = len(stat[module].keys()) > FILTER_IF_MORE_THAN
            for c, arg in enumerate(stat[module], 1):
                if c > 2 and large and stat[module][arg] < FILTER_THRESHOLD:
                    continue
                f.write(f"  {arg}: ${c}\n")
            f.write("endsnippet\n\n")
    print("Written snips to file snips")


if __name__ == "__main__":
    main()
