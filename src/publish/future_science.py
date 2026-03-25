"""
Upload a completed AutoInterp project to Future Science.

Endpoint: POST https://future-science.org/api/v1/contributions/api-bots
Auth:     x-api-key header
Format:   multipart/form-data

Fields sent:
  data                   - JSON string with contribution metadata
  file                   - Main Markdown report
  cover                  - First figure image (optional)
  additionalMaterialsZip - ZIP of repo/ scripts, results, notebooks, README (optional)
"""

import io
import json
import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

FUTURE_SCIENCE_ENDPOINT = "https://future-science.org/api/v1/contributions/api-bots"


# ---------------------------------------------------------------------------
# Project file discovery
# ---------------------------------------------------------------------------

def find_report(project_dir: Path) -> Optional[Path]:
    """
    Return the main Markdown report file for a completed project.

    Search order:
    1. repo/paper/*.md  (excluding README.md)
    2. reports/*.md     (excluding *_log.md, sorted newest-first)
    """
    paper_dir = project_dir / "repo" / "paper"
    if paper_dir.is_dir():
        candidates = sorted(
            [p for p in paper_dir.glob("*.md") if p.name.lower() != "readme.md"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

    reports_dir = project_dir / "reports"
    if reports_dir.is_dir():
        candidates = sorted(
            [
                p for p in reports_dir.glob("*.md")
                if not p.name.lower().endswith("_log.md")
                and p.name.lower() != "readme.md"
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

    return None


def find_cover_image(project_dir: Path) -> Optional[Path]:
    """Return the first figure PNG to use as the cover image."""
    for search_dir in [project_dir / "repo" / "paper", project_dir / "visualizations"]:
        if not search_dir.is_dir():
            continue
        pngs = sorted(search_dir.glob("*.png"))
        if pngs:
            return pngs[0]
    return None


def build_additional_zip(project_dir: Path) -> Optional[bytes]:
    """
    Build a ZIP archive containing repo/ supplementary materials:
    scripts/, results/, notebooks/, and README.md.

    Returns None if none of those exist.
    """
    repo_dir = project_dir / "repo"
    if not repo_dir.is_dir():
        return None

    include_dirs = ["scripts", "results", "notebooks"]
    buf = io.BytesIO()
    any_added = False

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        readme = repo_dir / "README.md"
        if readme.exists():
            zf.write(readme, "README.md")
            any_added = True

        for subdir_name in include_dirs:
            subdir = repo_dir / subdir_name
            if not subdir.is_dir():
                continue
            for f in sorted(subdir.rglob("*")):
                if f.is_file():
                    arcname = f.relative_to(repo_dir)
                    zf.write(f, str(arcname))
                    any_added = True

    if not any_added:
        return None
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Metadata extraction via Claude CLI
# ---------------------------------------------------------------------------

def extract_metadata_with_claude(report_path: Path) -> Dict[str, Any]:
    """
    Use the Claude Code CLI to extract title, abstract, and keywords from the
    report Markdown file.

    Returns a dict with keys:
        "title"    – str
        "abstract" – str
        "keywords" – list of {"text": str} dicts (3–8 items)

    Raises RuntimeError if the claude CLI is not found or exits non-zero.
    """
    if not shutil.which("claude"):
        raise RuntimeError(
            "claude CLI not found. Install Claude Code to enable metadata extraction."
        )

    prompt = (
        f"Read the Markdown file at {report_path} and extract the following metadata. "
        "Return ONLY a JSON object with these exact fields:\n"
        '  "title":    the main title of the paper (string)\n'
        '  "abstract": the full abstract text (string)\n'
        '  "keywords": an array of 3–8 keywords, each as {"text": "<keyword>"}\n\n'
        "If a field is not explicitly present, infer the best value from the content. "
        "Output ONLY the raw JSON object — no markdown fences, no explanation."
    )

    result = subprocess.run(
        ["claude", "-p", "--dangerously-skip-permissions", prompt],
        capture_output=True,
        text=True,
        cwd=str(report_path.parent),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Claude CLI exited with code {result.returncode}: {result.stderr[:500]}"
        )

    output = result.stdout.strip()
    # Strip markdown fences if the model adds them anyway
    if output.startswith("```"):
        lines = output.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        output = "\n".join(lines[1:end])

    return json.loads(output)


# ---------------------------------------------------------------------------
# Main publish function
# ---------------------------------------------------------------------------

def publish_project(
    project_dir: Path,
    api_key: str,
    initiative_id: str = "",
    contributor_email: str = "",
    author_first_name: str = "AutoInterp",
    author_last_name: str = "Agent",
    author_institution: str = "AutoInterp",
    author_email: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Upload a completed AutoInterp project to Future Science.

    Args:
        project_dir:        Path to the project directory.
        api_key:            Future Science API key.
        initiative_id:      documentId of the target initiative (may be empty).
        contributor_email:  Email of the submitting contributor.
        author_*:           Author metadata fields.
        dry_run:            If True, print what would be sent but don't POST.

    Returns:
        API response dict on success, or raises on error.
    """
    project_dir = Path(project_dir).resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    # --- Locate report ---
    report_path = find_report(project_dir)
    if report_path is None:
        raise FileNotFoundError(
            f"No Markdown report found in {project_dir}. "
            "Run the full pipeline first (repo assembly or report generation)."
        )
    logger.info(f"Report: {report_path}")

    # --- Extract metadata via Claude ---
    metadata = extract_metadata_with_claude(report_path)
    title = metadata.get("title") or report_path.stem.replace("_", " ")
    abstract = metadata.get("abstract") or title
    keywords = metadata.get("keywords") or [{"text": "mechanistic interpretability"}]

    author_entry: Dict[str, Any] = {
        "firstName": author_first_name,
        "lastName": author_last_name,
        "institution": author_institution,
        "email": author_email or contributor_email or "",
    }

    payload: Dict[str, Any] = {
        "data": {
            "title": title,
            "type": "Article",
            "abstract": abstract,
            "language": "English",
            "keywords": keywords,
            "author": [author_entry],
            "coauthorsNotified": True,
            "isFormatCompliant": True,
            "sourceLinkCorrect": True,
            "isOriginal": True,
            "isMarkdown": True,
            "comments": "",
            "linkOriginalContribution": "",
        }
    }
    if initiative_id:
        payload["data"]["initiative"] = initiative_id
    if contributor_email:
        payload["data"]["contributorEmail"] = contributor_email

    # --- Build multipart files dict ---
    files: Dict[str, Any] = {
        "data": (None, json.dumps(payload), "application/json"),
        "file": (report_path.name, report_path.read_bytes(), "text/markdown"),
    }

    cover_path = find_cover_image(project_dir)
    if cover_path:
        logger.info(f"Cover image: {cover_path}")
        files["cover"] = (cover_path.name, cover_path.read_bytes(), "image/png")

    zip_bytes = build_additional_zip(project_dir)
    if zip_bytes:
        logger.info("Additional materials ZIP: included")
        files["additionalMaterialsZip"] = (
            "supplementary.zip", zip_bytes, "application/zip"
        )

    # --- Dry run ---
    if dry_run:
        print("\n[DRY RUN] Would POST to:", FUTURE_SCIENCE_ENDPOINT)
        print("[DRY RUN] Headers: x-api-key: <redacted>")
        print("[DRY RUN] Payload:")
        print(json.dumps(payload, indent=2))
        print(f"[DRY RUN] file: {report_path.name} ({len(files['file'][1])} bytes)")
        if "cover" in files:
            print(f"[DRY RUN] cover: {cover_path.name} ({len(files['cover'][1])} bytes)")
        if "additionalMaterialsZip" in files:
            print(f"[DRY RUN] additionalMaterialsZip: supplementary.zip ({len(zip_bytes)} bytes)")
        return {"dry_run": True, "payload": payload}

    # --- POST ---
    headers = {"x-api-key": api_key}
    logger.info(f"Submitting '{title}' to Future Science...")

    response = requests.post(
        FUTURE_SCIENCE_ENDPOINT,
        headers=headers,
        files=files,
        timeout=120,
    )

    if response.status_code == 201:
        data = response.json()
        logger.info(f"Submission successful. documentId: {data.get('documentId', '')}")
        return data

    # Surface API errors clearly
    try:
        err = response.json()
    except Exception:
        err = {"error": response.text}
    raise RuntimeError(
        f"Future Science API returned {response.status_code}: {err}"
    )
