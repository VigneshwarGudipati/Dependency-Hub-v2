import os
import tempfile
import pytest

from app.services.reporting.report_data import ReportDependencyData
from app.services.reporting.analyzer.code_impact_analyzer import CodeImpactAnalyzer

@pytest.fixture
def analyzer():
    return CodeImpactAnalyzer()

def test_source_unavailable(analyzer):
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    res = analyzer.analyze(dep, source_dir=None)
    assert len(res) == 1
    assert res[0].detected_pattern == "SOURCE_UNAVAILABLE"
    assert res[0].file_path == "UNKNOWN"

def test_unsupported_ecosystem(analyzer):
    dep = ReportDependencyData(id="d1", package_name="lib", ecosystem="unknown-eco", package_version="1.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        res = analyzer.analyze(dep, source_dir=tmpdir)
    assert len(res) == 1
    assert res[0].detected_pattern == "UNSUPPORTED_ECOSYSTEM"
    assert res[0].file_path == "UNKNOWN"

def test_python_import_detection(analyzer):
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "main.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("import requests\nfrom requests import get\nimport os\n")

        res = analyzer.analyze(dep, source_dir=tmpdir)
        assert len(res) == 2

        # Check first import
        assert res[0].file_path == "main.py"
        assert res[0].line_number == 1
        assert res[0].detected_pattern == "import requests"

        # Check second import
        assert res[1].file_path == "main.py"
        assert res[1].line_number == 2
        assert res[1].detected_pattern == "from requests import ..."

def test_python_package_name_normalization(analyzer):
    dep = ReportDependencyData(id="d1", package_name="Flask", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "main.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("import flask\n")

        res = analyzer.analyze(dep, source_dir=tmpdir)
        assert len(res) == 1
        assert res[0].file_path == "main.py"
        assert res[0].detected_pattern == "import flask"

def test_python_package_mapping_unknown(analyzer):
    dep = ReportDependencyData(id="d1", package_name="python-dateutil", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        res = analyzer.analyze(dep, source_dir=tmpdir)
        assert len(res) == 1
        assert res[0].file_path == "UNKNOWN"
        assert res[0].detected_pattern == "PACKAGE_IMPORT_MAPPING_UNKNOWN"

def test_js_import_detection(analyzer):
    dep = ReportDependencyData(id="d1", package_name="axios", ecosystem="npm", package_version="1.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        js_file = os.path.join(tmpdir, "app.js")
        with open(js_file, "w", encoding="utf-8") as f:
            f.write("const axios = require('axios');\n")
            f.write("import axios from 'axios';\n")
            f.write("import { get } from 'axios/lib/core';\n")

        res = analyzer.analyze(dep, source_dir=tmpdir)
        assert len(res) == 3
        assert res[0].line_number == 1
        assert res[0].detected_pattern == "require('axios')"
        assert res[1].line_number == 2
        assert res[1].detected_pattern == "import from 'axios'"
        assert res[2].line_number == 3
        assert res[2].detected_pattern == "import from 'axios'"

def test_no_usage_found(analyzer):
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "main.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("import json\n")

        res = analyzer.analyze(dep, source_dir=tmpdir)
        assert len(res) == 1
        assert res[0].detected_pattern == "NO_USAGE_FOUND"
        assert res[0].file_path == "NONE"

def test_excluded_directories(analyzer):
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        os.makedirs(venv_dir)
        py_file = os.path.join(venv_dir, "bad.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("import requests\n")

        res = analyzer.analyze(dep, source_dir=tmpdir)
        assert len(res) == 1
        assert res[0].detected_pattern == "NO_USAGE_FOUND"

def test_multiple_affected_files(analyzer):
    dep = ReportDependencyData(id="d1", package_name="requests", ecosystem="pypi", package_version="2.0.0", dependency_type="direct", is_direct=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "a.py"), "w", encoding="utf-8") as f:
            f.write("import requests\n")
        with open(os.path.join(tmpdir, "b.py"), "w", encoding="utf-8") as f:
            f.write("import requests\n")

        res = analyzer.analyze(dep, source_dir=tmpdir)
        assert len(res) == 2
        files = {r.file_path for r in res}
        # Windows handles paths but our analyzer normalizes to forward slash
        assert "a.py" in files
        assert "b.py" in files
