#!/usr/bin/env python3
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
class Role:
    def __init__(self, name):
        self.name = name
        # print("Analyse role", name)
        try:
            with open("roles/" + name + "/tasks/main.yml", "r") as stream:
                self.data = yaml.load(stream, Loader=Loader)
        except FileNotFoundError:
            self.data = []
        except yaml.YAMLError as exc:
            print(exc)

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
        return set(Task(p) for p in self.data)

    def find_all_tags(self):
        tag_lists = [task.get_tags() for task in self.get_tasks()] + [
            dependency.find_all_tags() for dependency in self.get_dependencies()
        ]
        return set().union(*tag_lists)


def main():
    pb = Playbook("deploy-pretix.yml")
    print(pb.find_all_tags())


if __name__ == "__main__":
    main()


# TODO:
# includes & imports
# blocks
# Generate snips
