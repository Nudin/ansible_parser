#!/usr/bin/env python3
import itertools
import sys
from functools import lru_cache
from pathlib import Path

import yaml

# Safe loader is slower that CLoader but safe to use on untrusted yaml
USE_SAFE_LOADER = False

if USE_SAFE_LOADER:
    Loader = yaml.SafeLoader
else:
    Loader = yaml.CLoader


def flatten_list(list_of_lists):
    return list(itertools.chain(*list_of_lists))


class Playbook:
    def __init__(self, filename):
        self.folder = filename.parent
        with open(filename, "r") as stream:
            try:
                self.document = yaml.load(stream, Loader=Loader)
            except yaml.YAMLError as exc:
                print(exc)

    def get_plays(self):
        return [Play(p, self.folder) for p in self.document]

    def find_all_tasks(self):
        task_list = [play.find_all_tasks() for play in self.get_plays()]
        return flatten_list(task_list)

    def find_all_tags(self):
        tag_list = [play.find_all_tags() for play in self.get_plays()]
        return set().union(*tag_list)


class Play:
    def __init__(self, data, folder):
        self.data = data
        self.folder = folder

    def get_tasks(self):
        tasks = TaskList(self.data.get("tasks", []), self.folder)
        pre_tasks = TaskList(self.data.get("pre_tasks", []), self.folder)
        post_tasks = TaskList(self.data.get("post_tasks", []), self.folder)
        return (
            tasks.find_all_tasks()
            + pre_tasks.find_all_tasks()
            + post_tasks.find_all_tasks()
        )

    def get_roles(self):
        return [
            RoleInvocation(role, self.folder)
            for role in self.data.get("roles", []) or []
        ]

    def find_all_tasks(self):
        imported_tasks = []
        if "import_playbook" in self.data:
            imported = Playbook(self.folder / self.data["import_playbook"])
            imported_tasks = imported.find_all_tasks()
        return (
            self.get_tasks()
            + flatten_list([role.find_all_tasks() for role in self.get_roles()])
            + imported_tasks
        )

    def find_all_tags(self):
        tag_list = [task.get_tags() for task in self.get_tasks()] + [
            role.find_all_tags() for role in self.get_roles()
        ]
        if "import_playbook" in self.data:
            imported = Playbook(self.folder / self.data["import_playbook"])
            tag_list.append(imported.find_all_tags())
        return set().union(*tag_list)


class TaskList:
    def __init__(self, data, folder):
        self.folder = folder
        self.data = data

    def get_tasks(self):
        return [Task(p) for p in self.data]

    def find_all_tasks(self, include_blocks=False):
        tasks = self.get_tasks()
        imported_tasks = []
        for task in tasks:
            if "include_tasks" in task.data:
                arg = task.data["include_tasks"]
                if isinstance(arg, str):
                    filename = arg
                else:
                    filename = arg["file"]
                tf = TaskFile(self.folder, filename)
                imported_tasks.extend(tf.get_tasks())
            if "import_tasks" in task.data:
                arg = task.data["import_tasks"]
                if isinstance(arg, str):
                    filename = arg
                else:
                    filename = arg["file"]
                tf = TaskFile(self.folder, filename)
                imported_tasks.extend(tf.get_tasks())
            if task.is_block():
                block_task = [Task(t) for t in task.data.get("block", [])]
                rescue_task = [Task(t) for t in task.data.get("rescue", [])]
                always_task = [Task(t) for t in task.data.get("always", [])]
                if not include_blocks:
                    tasks.remove(task)
                tasks.extend(block_task + rescue_task + always_task)
        return tasks + imported_tasks

    def find_all_tags(self):
        return [task.get_tags() for task in self.find_all_tasks(include_blocks=True)]


class Task:
    RESERVED_OPTIONS = [
        "name",
        "delegate_to",
        "ignore_errors",
        "when",
        "loop",
        "tags",
        "changed_when",
        "notify",
        "args",
        "loop_control",
        "become",
        "become_user",
        "register",
        "with_items",
        "check_mode",
        "failed_when",
        "throttle",
        "environment",
        "run_once",
        "with_nested",
        "delegate_facts",
        "diff",
        "with_fileglob",
        "vars",
        "retries",
        "until",
        "delay",
        "no_log",
        "with_subelements",
    ]

    def __init__(self, data):
        self.data = data

    def get_tags(self):
        raw_tag = self.data.get("tags", [])
        if isinstance(raw_tag, str):
            return set([raw_tag])
        return set(raw_tag)

    def _get_type_candidates(self):
        keys = self.data.keys()
        return keys - self.RESERVED_OPTIONS

    def get_type(self):
        candidates = self._get_type_candidates()
        if len(candidates) == 1:
            return candidates.pop()
        else:
            raise ValueError("Cannot guess type of task")

    def get_args(self):
        # TODO: Include arguments in "args"?
        return self.data[self.get_type()]

    def is_block(self):
        return "block" in self._get_type_candidates()

    def __repr__(self):
        return self.data.__repr__()


class RoleInvocation:
    def __init__(self, data, folder):
        self.folder = folder
        if isinstance(data, str):
            data = {"role": data}
        self.data = data
        self.name = data["role"]
        self.role = Role(folder, self.name)

    def get_tags(self):
        raw_tag = self.data.get("tags", [])
        if isinstance(raw_tag, str):
            return set([raw_tag])
        return set(raw_tag)

    def find_all_tasks(self):
        return self.role.find_all_tasks()

    def find_all_tags(self):
        return self.get_tags().union(self.role.find_all_tags())


@lru_cache
class TaskFile:
    def __init__(self, folder, filename):
        self.task_folder = folder
        with open(folder / filename, "r") as stream:
            try:
                self.data = yaml.load(stream, Loader=Loader)
                self.task_list = TaskList(self.data, self.task_folder)
            except yaml.YAMLError as exc:
                print(exc)

    def get_tasks(self):
        return self.task_list.get_tasks()

    def find_all_tasks(self):
        return self.task_list.find_all_tasks()

    def find_all_tags(self):
        return self.task_list.find_all_tags()


@lru_cache
class Role:
    def __init__(self, folder, name):
        self.name = name
        # print("Analyse role", name)
        self.playbook_folder = folder
        self.folder = folder / "roles" / name
        self.task_folder = self.folder / "tasks"
        try:
            self.main = TaskFile(self.task_folder, "main.yml")
        except FileNotFoundError:
            self.main = None

        try:
            with open(self.folder / "meta" / "main.yml", "r") as stream:
                self.meta_data = yaml.load(stream, Loader=Loader)
        except FileNotFoundError:
            self.meta_data = {}
        except yaml.YAMLError as exc:
            print(exc)

    def get_dependencies(self):
        return [
            RoleInvocation(d, self.playbook_folder)
            for d in self.meta_data.get("dependencies", [])
        ]

    def get_tasks(self):
        if self.main:
            return self.main.find_all_tasks()
        else:
            return []

    def find_all_tasks(self):
        dependency_tasks = [
            dependency.find_all_tasks() for dependency in self.get_dependencies()
        ]
        return self.get_tasks() + flatten_list(dependency_tasks)

    def find_all_tags(self):
        tag_lists = [task.get_tags() for task in self.get_tasks()] + [
            dependency.find_all_tags() for dependency in self.get_dependencies()
        ]
        return set().union(*tag_lists)


# Demo usage
def main():
    playbook = Path(sys.argv[1])
    pb = Playbook(playbook)
    print(f"Found {len(pb.find_all_tags())} tags")
    print(f"Found {len(pb.find_all_tasks())} tasks")


if __name__ == "__main__":
    main()
