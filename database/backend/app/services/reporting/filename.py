import re
from datetime import datetime, timezone

def generate_safe_filename(project_name: str, report_type: str = "security", extension: str = "pdf") -> str:
    """
    Generates a deterministic, path-traversal safe filename.
    Strictly strips control characters, slashes, and reserved names.
    """
    # 1. Base sanitization (alphanumeric, dashes, underscores)
    safe_project = re.sub(r'[^a-zA-Z0-9_-]', '_', project_name)
    safe_type = re.sub(r'[^a-zA-Z0-9_-]', '_', report_type)

    # Compress multiple underscores
    safe_project = re.sub(r'_+', '_', safe_project).strip('_')
    safe_type = re.sub(r'_+', '_', safe_type).strip('_')

    # 2. Defaults if empty
    if not safe_project:
        safe_project = "project"
    if not safe_type:
        safe_type = "report"

    # 3. Reserved Windows names check (CON, NUL, AUX, PRN, COM1-9, LPT1-9)
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if safe_project.upper() in reserved:
        safe_project += "_report"

    # 4. Truncation (prevent overlong names, max 255 typically, leave room for date + ext)
    safe_project = safe_project[:100]

    # 5. Extension enforcement
    valid_extensions = {"json", "html", "pdf"}
    if extension not in valid_extensions:
        extension = "pdf"

    # 6. Final assembly: project_type_YYYYMMDD.ext
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    filename = f"{safe_project}_{safe_type}_{date_str}.{extension}"
    return filename
