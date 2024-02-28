#!/usr/bin/env python3
import sys
from functools import lru_cache

import yaml

# Safe loader is slower that CLoader but safe to use on untrusted yaml
USE_SAFE_LOADER = False

if USE_SAFE_LOADER:
    Loader = yaml.SafeLoader
else:
    Loader = yaml.CLoader


class Playbook:
    def __init__(self, filename):
        with open(filename, "r") as stream:
            try:
                self.document = yaml.load(stream, Loader=Loader)
            except yaml.YAMLError as exc:
                print(exc)

    def get_plays(self):
        return [Play(p) for p in self.document]

    def find_all_tags(self):
        tag_list = [play.find_all_tags() for play in self.get_plays()]
        return set().union(*tag_list)


class Play:
    def __init__(self, data):
        self.data = data

    def get_tasks(self):
        return [
            Task(p)
            for p in self.data.get("tasks", [])
            + self.data.get("pre_tasks", [])
            + self.data.get("post_tasks", [])
        ]

    def get_roles(self):
        return [RoleInvocation(role) for role in self.data.get("roles", [])]

    def find_all_task(self):
        return self.get_tasks() + [role.get_tasks() for role in self.get_roles()]

    def find_all_tags(self):
        tag_list = [task.get_tags() for task in self.get_tasks()] + [
            role.find_all_tags() for role in self.get_roles()
        ]
        return set().union(*tag_list)


class Task:
    def __init__(self, data):
        self.data = data

    def get_tags(self):
        raw_tag = self.data.get("tags", [])
        if isinstance(raw_tag, str):
            return set([raw_tag])
        return set(raw_tag)

    def __repr__(self):
        return self.data.__repr__()


class RoleInvocation:
    def __init__(self, data):
        self.data = data
        self.name = data["role"]
        self.role = Role(self.name)

    def get_tags(self):
        raw_tag = self.data.get("tags", [])
        if isinstance(raw_tag, str):
            return set([raw_tag])
        return set(raw_tag)

    def find_all_tags(self):
        return self.get_tags().union(self.role.find_all_tags())


@lru_cache
class TaskFile:
    def __init__(self, folder, filename):
        self.task_folder = folder
        with open(filename, "r") as stream:
            try:
                self.data = yaml.load(stream, Loader=Loader)
            except yaml.YAMLError as exc:
                print(exc)

    def get_tasks(self):
        tasks = [Task(p) for p in self.data]
        imported_tasks = []
        for task in tasks:
            if "include_tasks" in task.data:
                tf = TaskFile(
                    self.task_folder, self.task_folder + task.data["include_tasks"]
                )
                imported_tasks.extend(tf.get_tasks())
            if "import_tasks" in task.data:
                tf = TaskFile(
                    self.task_folder, self.task_folder + task.data["import_tasks"]
                )
                imported_tasks.extend(tf.get_tasks())
        return tasks + imported_tasks

    def find_all_tags(self):
        return [task.get_tags() for task in self.get_tasks()]


@lru_cache
class Role:
    def __init__(self, name):
        self.name = name
        # print("Analyse role", name)
        self.task_folder = "roles/" + name + "/tasks/"
        try:
            self.main = TaskFile(self.task_folder, self.task_folder + "main.yml")
        except FileNotFoundError:
            self.main = None

        try:
            with open("roles/" + name + "/meta/main.yml", "r") as stream:
                self.meta_data = yaml.load(stream, Loader=Loader)
        except FileNotFoundError:
            self.meta_data = {}
        except yaml.YAMLError as exc:
            print(exc)

    def get_dependencies(self):
        return [RoleInvocation(d) for d in self.meta_data.get("dependencies", [])]

    def get_tasks(self):
        if self.main:
            return self.main.get_tasks()
        else:
            return []

    def find_all_tags(self):
        tag_lists = [task.get_tags() for task in self.get_tasks()] + [
            dependency.find_all_tags() for dependency in self.get_dependencies()
        ]
        return set().union(*tag_lists)


def main():
    playbook = sys.argv[1]
    pb = Playbook(playbook)
    print(pb.find_all_tags())


if __name__ == "__main__":
    main()


# TODO:
# import playbook
# blocks
# Generate snips
