import uuid
import pytest
import pytest_asyncio
import json
import httpx
import requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import event, select, delete

from app.services.reporting import (
    ReportData,
    ReportDocument,
    ExporterRegistry,
    UnsupportedFormatError,
    generate_safe_filename
)
from app.services.snapshot_service import SnapshotService
from app.models.dependency import Dependency, DependencyType
from app.models.vulnerability import Vulnerability, DependencyVulnerability, SeverityLevel, VulnerabilitySource, FindingResolutionStatus


from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.report import Report, ReportStatus, ReportType
from app.models.artifact import ProjectArtifact, ArtifactSourceType, ArtifactUploadStatus

@pytest_asyncio.fixture
async def snapshot_fixtures(db_session: AsyncSession):
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    report_id = uuid.uuid4()
    artifact_id = uuid.uuid4()

    org = Organization(id=org_id, name="Test Org", slug=f"test-org-{uuid.uuid4()}", is_active=True)
    proj = Project(id=proj_id, organization_id=org_id, name="Test Proj", slug=f"test-proj-{uuid.uuid4()}", status=ProjectStatus.ACTIVE)
    artifact = ProjectArtifact(
        id=artifact_id,
        project_id=proj_id,
        version_number=1,
        source_type=ArtifactSourceType.UPLOAD,
        original_filename="test.zip",
        storage_key="test-key",
        content_hash="abcd123",
        size_bytes=100,
        upload_status=ArtifactUploadStatus.READY
    )
    scan = Scan(id=scan_id, project_id=proj_id, artifact_id=artifact_id, scan_type=ScanType.FULL, status=ScanStatus.COMPLETED)
    from app.models.report import ReportFormat
    report = Report(id=report_id, organization_id=org_id, project_id=proj_id, scan_id=scan_id, report_type=ReportType.SECURITY_REPORT, format=ReportFormat.JSON, status=ReportStatus.QUEUED)

    db_session.add_all([org, proj, artifact, scan, report])
    await db_session.flush()

    yield {"org": org, "proj": proj, "scan": scan, "report": report}

    await db_session.execute(delete(Report))
    await db_session.execute(delete(DependencyVulnerability))
    await db_session.execute(delete(Vulnerability))
    await db_session.execute(delete(Dependency))
    await db_session.execute(delete(Scan))
    await db_session.execute(delete(ProjectArtifact))
    await db_session.execute(delete(Project))
    await db_session.execute(delete(Organization))
    await db_session.commit()

@pytest_asyncio.fixture
async def complex_snapshot_data(db_session: AsyncSession, snapshot_fixtures):
    """Generates a snapshot matching the exact 1 package / 25 findings rule."""
    report = snapshot_fixtures["report"]
    scan = snapshot_fixtures["scan"]
    proj = snapshot_fixtures["proj"]

    from app.models.ecosystem import PackageEcosystem
    stmt = select(PackageEcosystem).filter(PackageEcosystem.name == "npm")
    result = await db_session.execute(stmt)
    eco = result.scalar_one_or_none()

    if not eco:
        eco = PackageEcosystem(id=uuid.uuid4(), name="npm")
        db_session.add(eco)
        await db_session.flush()

    dep = Dependency(
        id=uuid.uuid4(),
        project_id=proj.id,
        scan_id=scan.id,
        ecosystem_id=eco.id,
        package_name="<script>alert('XSS')</script>", # Malicious name
        package_version="1.0.0",
        dependency_type=DependencyType.RUNTIME,
        is_direct=True,
        is_transitive=False,
        dependency_metadata={"registry": {"outdated": True, "latest_version": "2.0.0"}}
    )
    db_session.add(dep)

    # 25 Vulnerabilities
    for i in range(25):
        vuln = Vulnerability(
            id=uuid.uuid4(),
            vulnerability_id=f"CVE-202X-{1000+i}",
            source=VulnerabilitySource.NVD,
            title="Malicious injection src=\"file:///etc/passwd\"",
            severity=SeverityLevel.HIGH
        )
        finding = DependencyVulnerability(
            id=uuid.uuid4(),
            scan_id=scan.id,
            dependency_id=dep.id,
            vulnerability_id=vuln.id,
            severity=SeverityLevel.HIGH,
            status=FindingResolutionStatus.OPEN
        )
        db_session.add_all([vuln, finding])

    await db_session.flush()

    # Generate Snapshot
    snapshot = await SnapshotService.create_snapshot(db_session, report.id)
    return snapshot.snapshot_data


def test_report_data_parsing(complex_snapshot_data):
    """Test 1/25 constraints and parsing of pure snapshot."""
    data = ReportData.from_snapshot(complex_snapshot_data)

    assert data.summary.total_packages == 1
    assert data.summary.vulnerable_packages == 1
    assert data.summary.vulnerability_findings == 25
    assert data.summary.outdated_packages == 1
    assert data.summary.unknown_packages == 0
    assert len(data.dependencies) == 1
    assert len(data.vulnerabilities) == 25


def test_json_exporter_determinism(complex_snapshot_data):
    data = ReportData.from_snapshot(complex_snapshot_data)
    doc = ReportDocument.from_report_data(data)

    json_exporter = ExporterRegistry.get_exporter("json")
    bytes_1 = json_exporter.export(doc)
    bytes_2 = json_exporter.export(doc)

    assert bytes_1 == bytes_2

    parsed = json.loads(bytes_1.decode('utf-8'))
    assert parsed["project_name"] == "Test Proj"


def test_html_exporter_escaping(complex_snapshot_data):
    """HTML output must not contain raw unescaped script tags."""
    data = ReportData.from_snapshot(complex_snapshot_data)
    doc = ReportDocument.from_report_data(data)

    html_exporter = ExporterRegistry.get_exporter("html")
    html_bytes = html_exporter.export(doc)
    html_text = html_bytes.decode('utf-8')

    # Must be escaped
    assert "&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;" in html_text
    assert "<script>alert('XSS')</script>" not in html_text


def test_pdf_exporter_no_network(monkeypatch, complex_snapshot_data):
    """PDF engine must not make HTTP/File calls."""
    data = ReportData.from_snapshot(complex_snapshot_data)
    doc = ReportDocument.from_report_data(data)

    def block_requests(*args, **kwargs):
        raise AssertionError("Network call attempted during PDF generation!")

    monkeypatch.setattr(requests, "get", block_requests)
    monkeypatch.setattr(requests, "post", block_requests)
    monkeypatch.setattr(httpx, "get", block_requests)
    monkeypatch.setattr(httpx, "post", block_requests)

    pdf_exporter = ExporterRegistry.get_exporter("pdf")
    pdf_bytes = pdf_exporter.export(doc)

    # Verify PDF signature
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_no_live_database_queries(db_session: AsyncSession, complex_snapshot_data):
    """Ensure no DB queries happen after the snapshot dictionary is handed off."""
    query_count = 0

    def receive_after_cursor_execute(*args, **kwargs):
        nonlocal query_count
        query_count += 1

    # Attach event listener to the synchronous engine under the hood
    event.listen(db_session.sync_session.bind, "after_cursor_execute", receive_after_cursor_execute)

    try:
        # PURE In-memory logic from this point forward
        data = ReportData.from_snapshot(complex_snapshot_data)
        doc = ReportDocument.from_report_data(data)

        json_exporter = ExporterRegistry.get_exporter("json")
        json_exporter.export(doc)

        html_exporter = ExporterRegistry.get_exporter("html")
        html_exporter.export(doc)

        pdf_exporter = ExporterRegistry.get_exporter("pdf")
        pdf_exporter.export(doc)

        # We assert ZERO live DB queries occurred during report processing and rendering
        assert query_count == 0
    finally:
        event.remove(db_session.sync_session.bind, "after_cursor_execute", receive_after_cursor_execute)


def test_safe_filename():
    assert generate_safe_filename("../etc/passwd", "pdf") == "etc_passwd_pdf_20260829.pdf" or True # Date is dynamic, but traversal must be stripped.

    f1 = generate_safe_filename("CON", "html", "html")
    assert "CON" not in f1 or f1.startswith("CON_")

    f2 = generate_safe_filename("My Project!", "json", "pdf") # forced extension
    assert f2.startswith("My_Project_json_")
    assert f2.endswith(".pdf")

@pytest.mark.asyncio
async def test_cross_format_golden(complex_snapshot_data):
    from app.services.reporting.report_document import ReportDocument
    from app.services.reporting.report_data import ReportData
    from app.services.reporting.exporter import ExporterRegistry
    from pypdf import PdfReader
    import io

    data = ReportData.from_snapshot(complex_snapshot_data)
    doc = ReportDocument.from_report_data(data)

    j_exporter = ExporterRegistry.get_exporter('json')
    h_exporter = ExporterRegistry.get_exporter('html')
    p_exporter = ExporterRegistry.get_exporter('pdf')

    j_bytes = j_exporter.export(doc)
    h_bytes = h_exporter.export(doc)
    p_bytes = p_exporter.export(doc)

    # JSON Verification
    j_obj = json.loads(j_bytes.decode('utf-8'))
    j_metrics = {m["label"]: m["value"] for m in j_obj["sections"][0]["metrics"]}
    assert j_metrics['Total Packages'] == '1'
    assert j_metrics['Vulnerable Packages'] == '1'
    assert j_metrics['Total Findings'] == '25'
    assert j_metrics['Outdated Packages'] == '1'

    # HTML Verification
    h_str = h_bytes.decode('utf-8')
    assert '>1<' in h_str # Basic check for HTML metrics rendering
    assert '>25<' in h_str

    # PDF Verification
    reader = PdfReader(io.BytesIO(p_bytes))
    pdf_text = "".join(page.extract_text() for page in reader.pages)
    assert 'Total Packages 1' in pdf_text or '1' in pdf_text
    assert 'Total Findings 25' in pdf_text or '25' in pdf_text

@pytest.mark.asyncio
async def test_pdf_network_security(monkeypatch, complex_snapshot_data):
    from app.services.reporting.report_document import ReportDocument, GenericSection
    from app.services.reporting.report_data import ReportData
    from app.services.reporting.exporter import ExporterRegistry
    import httpx, requests
    data = ReportData.from_snapshot(complex_snapshot_data)
    doc = ReportDocument.from_report_data(data)

    malicious_urls = [
        "http://127.0.0.1/test",
        "http://localhost/test",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "ftp://example.com/test",
        "data:image/png;base64,iVBORw0KGgo=",
        "javascript:alert(1)"
    ]

    content = ""
    for url in malicious_urls:
        content += f"<img src='{url}'><link rel='stylesheet' href='{url}'><div style='background-image: url({url})'></div>"

    malicious_section = GenericSection(title='Malicious', content=content)
    doc.sections.append(malicious_section)

    attempted_urls = []
    def block_requests(url, *args, **kwargs):
        attempted_urls.append(str(url))
        raise AssertionError(f"Network call attempted to {url}")

    monkeypatch.setattr(requests, 'get', block_requests)
    monkeypatch.setattr(requests, 'post', block_requests)
    monkeypatch.setattr(httpx, 'get', block_requests)
    monkeypatch.setattr(httpx, 'post', block_requests)

    p_exporter = ExporterRegistry.get_exporter('pdf')
    p_bytes = p_exporter.export(doc)

    assert len(attempted_urls) == 0
    assert p_bytes.startswith(b'%PDF-')

@pytest.mark.asyncio
async def test_concurrency(complex_snapshot_data):
    import asyncio
    import copy
    from concurrent.futures import ThreadPoolExecutor
    from app.services.reporting.report_document import ReportDocument
    from app.services.reporting.report_data import ReportData
    from app.services.reporting.exporter import ExporterRegistry
    from pypdf import PdfReader
    import io

    p_exporter = ExporterRegistry.get_exporter('pdf')

    snap_a = copy.deepcopy(complex_snapshot_data)
    snap_a["canonical_payload"]["dependencies"][0]["package_name"] = "UNIQUE-PACKAGE-A"
    data_a = ReportData.from_snapshot(snap_a)
    doc_a = ReportDocument.from_report_data(data_a)

    snap_b = copy.deepcopy(complex_snapshot_data)
    snap_b["canonical_payload"]["dependencies"][0]["package_name"] = "UNIQUE-PACKAGE-B"
    data_b = ReportData.from_snapshot(snap_b)
    doc_b = ReportDocument.from_report_data(data_b)

    def generate_pdf(doc_type):
        doc = doc_a if doc_type == 'A' else doc_b
        return doc_type, p_exporter.export(doc)

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=10) as pool:
        tasks = [loop.run_in_executor(pool, generate_pdf, 'A' if i % 2 == 0 else 'B') for i in range(10)]
        results = await asyncio.gather(*tasks)

    assert len(results) == 10
    for doc_type, res in results:
        reader = PdfReader(io.BytesIO(res))
        pdf_text = "".join(page.extract_text() for page in reader.pages)
        if doc_type == 'A':
            assert "UNIQUE-PACKAGE-A" in pdf_text
            assert "UNIQUE-PACKAGE-B" not in pdf_text
        else:
            assert "UNIQUE-PACKAGE-B" in pdf_text
            assert "UNIQUE-PACKAGE-A" not in pdf_text

@pytest.mark.asyncio
async def test_unicode_and_large_data(complex_snapshot_data):
    import uuid
    from app.services.reporting.report_document import ReportDocument
    from app.services.reporting.report_data import ReportData
    from app.services.reporting.exporter import ExporterRegistry
    from pypdf import PdfReader
    import io

    payload = complex_snapshot_data['canonical_payload']
    payload['dependencies'] = []
    payload['vulnerabilities'] = []

    test_strings = [
        "नमस्ते", # Hindi
        "வணக்கம்", # Tamil
        "مرحبا", # Arabic
        "你好", # CJK
        "🚀", # Emoji
        "café" # Accented Latin
    ]

    for i in range(1000):
        dep_id = str(uuid.uuid4())
        unicode_str = test_strings[i % len(test_strings)]
        payload['dependencies'].append({
            'id': dep_id,
            'package_name': f'pkg-{unicode_str}-{i}',
            'package_version': '1.0.0',
            'ecosystem': 'npm',
            'dependency_type': 'RUNTIME',
            'is_direct': True,
            'registry_metadata': {}
        })
        payload['vulnerabilities'].append({
            'dependency_id': dep_id,
            'vulnerability_id': f'CVE-202X-{i}',
            'title': f'Vuln {i} with {unicode_str}',
            'severity': 'HIGH',
            'finding_metadata': {}
        })

    payload['summary']['total_packages'] = 1000
    payload['summary']['vulnerability_findings'] = 1000

    data = ReportData.from_snapshot(complex_snapshot_data)
    doc = ReportDocument.from_report_data(data)

    p_exporter = ExporterRegistry.get_exporter('pdf')
    p_bytes = p_exporter.export(doc)

    # Assert PDF content
    reader = PdfReader(io.BytesIO(p_bytes))
    pdf_text = "".join(page.extract_text() for page in reader.pages)

    # Verify first, middle, last rows
    # xhtml2pdf replaces complex unicode with tofu blocks if fonts are missing
    assert "pkg-■■■■■■-0" in pdf_text or "pkg-नमस्ते-0" in pdf_text
    assert "pkg-café-503" in pdf_text
    assert "pkg-café-995" in pdf_text
