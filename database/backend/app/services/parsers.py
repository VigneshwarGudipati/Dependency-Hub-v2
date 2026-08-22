import json
from typing import Dict, List, Tuple

class DependencyInfo:
    def __init__(self, name: str, version_constraint: str, is_dev: bool = False):
        self.name = name
        self.version_constraint = version_constraint
        self.is_dev = is_dev


class ManifestParser:
    """Base class for manifest parsers."""
    @classmethod
    def can_parse(cls, filename: str) -> bool:
        raise NotImplementedError

    def parse(self, content: str) -> List[DependencyInfo]:
        raise NotImplementedError


class PackageJsonParser(ManifestParser):
    @classmethod
    def can_parse(cls, filename: str) -> bool:
        return filename == "package.json"

    def parse(self, content: str) -> List[DependencyInfo]:
        deps = []
        try:
            data = json.loads(content)
            
            dependencies = data.get("dependencies", {})
            for name, ver in dependencies.items():
                deps.append(DependencyInfo(name, str(ver), is_dev=False))
                
            dev_dependencies = data.get("devDependencies", {})
            for name, ver in dev_dependencies.items():
                deps.append(DependencyInfo(name, str(ver), is_dev=True))
                
        except json.JSONDecodeError:
            pass # Malformed, just return empty or what we have
        return deps


class RequirementsTxtParser(ManifestParser):
    @classmethod
    def can_parse(cls, filename: str) -> bool:
        return filename == "requirements.txt"

    def parse(self, content: str) -> List[DependencyInfo]:
        deps = []
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Very basic parsing for name and version
            # e.g., requests==2.25.1 or requests>=2.0.0
            if "==" in line:
                name, ver = line.split("==", 1)
                deps.append(DependencyInfo(name.strip(), f"=={ver.strip()}"))
            elif ">=" in line:
                name, ver = line.split(">=", 1)
                deps.append(DependencyInfo(name.strip(), f">={ver.strip()}"))
            elif "~=" in line:
                name, ver = line.split("~=", 1)
                deps.append(DependencyInfo(name.strip(), f"~={ver.strip()}"))
            else:
                name = line.split()[0] # strip off comments
                deps.append(DependencyInfo(name.strip(), "*"))
        return deps


def get_parser(filename: str) -> ManifestParser:
    if PackageJsonParser.can_parse(filename):
        return PackageJsonParser()
    if RequirementsTxtParser.can_parse(filename):
        return RequirementsTxtParser()
    return None
