#!/usr/bin/env python

import sys
from pathlib import Path

from parse_playbook import Playbook


def get_all_tags(playbook):
    pb = Playbook(playbook)
    return pb.find_all_tags()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file or directory>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print("Path does not exist")
        sys.exit(1)

    all_tags = []
    if file_path.is_file():
        all_tags = get_all_tags(file_path)
    elif file_path.is_dir():
        for file in file_path.iterdir():
            if (
                file.suffix in [".yaml", ".yml"]
                and "test" not in file.stem
                and not file.match(".*")
            ):
                try:
                    all_tags.extend(get_all_tags(file))
                except:
                    print(f"WARNING: Failed to parse file {file} – skipping")
    else:
        return "Invalid path or file does not exist"

    print(" ".join(sorted(set(all_tags))))


if __name__ == "__main__":
    main()
