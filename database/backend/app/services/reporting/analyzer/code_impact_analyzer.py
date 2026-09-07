import os
import ast
import re
from typing import List, Optional
import logging

from app.services.reporting.report_data import ReportDependencyData, CodeImpactData

logger = logging.getLogger(__name__)

class CodeImpactAnalyzer:
    """
    Analyzes project source code (if available) to determine the exact usage
    and impact of a dependency, ensuring read-only, safe static analysis.
    """
    def __init__(self):
        self.excluded_dirs = {
            ".git", "node_modules", "venv", ".venv", "__pycache__",
            "build", "dist", "storage", ".tox", ".pytest_cache", "coverage",
            "tmp", "temp"
        }

    def analyze(self, dependency: ReportDependencyData, source_dir: Optional[str] = None) -> List[CodeImpactData]:
        if not source_dir or not os.path.isdir(source_dir):
            return [
                CodeImpactData(
                    file_path="UNKNOWN",
                    detected_pattern="SOURCE_UNAVAILABLE",
                    risk="UNKNOWN",
                    recommendation="Manual review required: source code unavailable for analysis."
                )
            ]

        ecosystem = dependency.ecosystem.lower()
        if ecosystem not in ["npm", "yarn", "pnpm", "pypi", "pip"]:
            return [
                CodeImpactData(
                    file_path="UNKNOWN",
                    detected_pattern="UNSUPPORTED_ECOSYSTEM",
                    risk="UNKNOWN",
                    recommendation=f"Manual review required: ecosystem {ecosystem} not supported for source analysis."
                )
            ]

        if ecosystem in ["pypi", "pip"] and not dependency.package_name.isidentifier():
            return [
                CodeImpactData(
                    file_path="UNKNOWN",
                    detected_pattern="PACKAGE_IMPORT_MAPPING_UNKNOWN",
                    risk="UNKNOWN",
                    recommendation=f"Manual review required: Cannot reliably determine Python import name for package '{dependency.package_name}'."
                )
            ]

        results = []
        for root, dirs, files in os.walk(source_dir):
            # Mutate dirs in-place to prune excluded directories
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, source_dir)
                # Ensure forward slashes for consistent reporting across OS
                rel_path = rel_path.replace("\\", "/")

                if ecosystem in ["pypi", "pip"] and file.endswith(".py"):
                    results.extend(self._analyze_python(file_path, rel_path, dependency.package_name))
                elif ecosystem in ["npm", "yarn", "pnpm"] and file.endswith((".js", ".ts", ".jsx", ".tsx")):
                    results.extend(self._analyze_js(file_path, rel_path, dependency.package_name))

        if not results:
            return [
                CodeImpactData(
                    file_path="NONE",
                    detected_pattern="NO_USAGE_FOUND",
                    risk="LOW",
                    recommendation="No direct usage found in scanned source files."
                )
            ]

        return results

    def _analyze_python(self, file_path: str, rel_path: str, package_name: str) -> List[CodeImpactData]:
        results = []
        # Use the package name directly (case-insensitive) without inventing mappings.
        import_name = package_name.lower()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0].lower() == import_name:
                            results.append(CodeImpactData(
                                file_path=rel_path,
                                line_number=node.lineno,
                                detected_pattern=f"import {alias.name}",
                                risk="MEDIUM",
                                recommendation=f"Verify API compatibility for {alias.name} usage."
                            ))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0].lower() == import_name:
                        results.append(CodeImpactData(
                            file_path=rel_path,
                            line_number=node.lineno,
                            detected_pattern=f"from {node.module} import ...",
                            risk="MEDIUM",
                            recommendation=f"Verify API compatibility for {node.module} usage."
                        ))
        except SyntaxError:
            # Skip files that aren't valid Python (e.g. py2 in py3 env)
            pass
        except Exception as e:
            logger.debug(f"Failed to parse python file {file_path}: {e}")

        return results

    def _analyze_js(self, file_path: str, rel_path: str, package_name: str) -> List[CodeImpactData]:
        results = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Static text regex fallback since full AST parsing for JS/TS would require heavy node dependencies.
            # Captures `require('pkg')`, `import X from 'pkg'`, `import {X} from "pkg"`
            require_pattern = re.compile(rf"require\(['\"]{re.escape(package_name)}(/.*)?['\"]\)")
            import_pattern = re.compile(rf"from\s+['\"]{re.escape(package_name)}(/.*)?['\"]")
            import_side_effect_pattern = re.compile(rf"import\s+['\"]{re.escape(package_name)}(/.*)?['\"]")

            for i, line in enumerate(lines):
                if require_pattern.search(line):
                    results.append(CodeImpactData(
                        file_path=rel_path,
                        line_number=i + 1,
                        detected_pattern=f"require('{package_name}')",
                        risk="MEDIUM",
                        recommendation=f"Verify API compatibility for {package_name} usage."
                    ))
                elif import_pattern.search(line) or import_side_effect_pattern.search(line):
                    results.append(CodeImpactData(
                        file_path=rel_path,
                        line_number=i + 1,
                        detected_pattern=f"import from '{package_name}'",
                        risk="MEDIUM",
                        recommendation=f"Verify API compatibility for {package_name} usage."
                    ))
        except UnicodeDecodeError:
            pass
        except Exception as e:
            logger.debug(f"Failed to parse JS file {file_path}: {e}")

        return results
