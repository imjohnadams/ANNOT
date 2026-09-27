import csv
import json
import os
import re
from datetime import datetime, timezone

from utils.paths import (
    annot_output_dir,
    book_stem,
    chapter_csv_path,
    chapter_json_path,
    csv_output_dir,
    json_output_dir,
    logs_output_dir,
    master_csv_path,
    master_json_path,
)


def ensure_output_dirs(
    source_filepath: str,
    output_root: str | None = None,
) -> None:
    for folder in (
        annot_output_dir(source_filepath, output_root),
        json_output_dir(source_filepath, output_root),
        csv_output_dir(source_filepath, output_root),
        logs_output_dir(source_filepath, output_root),
    ):
        os.makedirs(folder, exist_ok=True)


def save_chapter_json(
    source_filepath: str,
    chapter_number: int,
    data: dict,
    output_root: str | None = None,
) -> str:
    ensure_output_dirs(source_filepath, output_root)
    path = chapter_json_path(source_filepath, chapter_number, output_root)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    return path


def export_chapter_csv(
    source_filepath: str,
    chapter_number: int,
    data: dict,
    output_root: str | None = None,
) -> str:
    ensure_output_dirs(source_filepath, output_root)
    path = chapter_csv_path(source_filepath, chapter_number, output_root)

    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "document",
            "chapter",
            "chapter_title",
            "page",
            "category",
            "grounding",
            "source_text",
            "annotation",
            "quality",
            "density",
        ])
        for row in data.get("annotations", []):
            writer.writerow([
                data.get("source_filename", ""),
                data.get("chapter_number", chapter_number),
                data.get("chapter_title", ""),
                row.get("page", ""),
                row.get("category", ""),
                row.get("grounding", ""),
                row.get("book_text", ""),
                row.get("annotation", ""),
                data.get("quality", ""),
                data.get("density", ""),
            ])

    return path


def save_master_json(
    source_filepath: str,
    book_title: str,
    run_metadata: dict,
    output_root: str | None = None,
) -> str:
    ensure_output_dirs(source_filepath, output_root)
    path = master_json_path(source_filepath, output_root)
    stem = book_stem(source_filepath)
    pattern = re.compile(rf"^{re.escape(stem)}_ch(\d+)\.json$")

    chapters: list[dict] = []
    json_dir = json_output_dir(source_filepath, output_root)

    if os.path.isdir(json_dir):
        for filename in sorted(os.listdir(json_dir)):
            match = pattern.match(filename)
            if not match:
                continue
            file_path = os.path.join(json_dir, filename)
            with open(file_path, "r", encoding="utf-8") as file:
                chapters.append(json.load(file))

    chapters.sort(key=lambda item: item.get("chapter_number", 0))

    payload = {
        "book": book_title,
        "document": book_title,
        "source_filename": os.path.basename(source_filepath),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_metadata": run_metadata,
        "chapters": chapters,
    }

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    return path


def export_master_csv(
    source_filepath: str,
    output_root: str | None = None,
    master_json_file: str | None = None,
) -> str:
    ensure_output_dirs(source_filepath, output_root)

    if master_json_file is None:
        master_json_file = master_json_path(source_filepath, output_root)

    with open(master_json_file, "r", encoding="utf-8") as file:
        payload = json.load(file)

    meta = payload.get("run_metadata") or {}
    document = meta.get("source_filename") or payload.get("book") or ""
    quality = meta.get("quality", "")
    density = meta.get("quotes_per_page", "")

    path = master_csv_path(source_filepath, output_root)

    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "document",
            "chapter",
            "chapter_title",
            "page",
            "category",
            "grounding",
            "source_text",
            "annotation",
            "quality",
            "density",
        ])

        for chapter in payload.get("chapters", []):
            chapter_number = chapter.get("chapter_number", "")
            chapter_title = chapter.get("chapter_title", "")

            for row in chapter.get("annotations", []):
                writer.writerow([
                    document,
                    chapter_number,
                    chapter_title,
                    row.get("page", ""),
                    row.get("category", ""),
                    row.get("grounding", ""),
                    row.get("book_text", ""),
                    row.get("annotation", ""),
                    quality,
                    density,
                ])

    return path


def delete_chapter_outputs(
    source_filepath: str,
    output_root: str | None = None,
) -> int:
    """Delete individual chapter JSON/CSV files. Returns count removed."""
    stem = book_stem(source_filepath)
    json_pattern = re.compile(rf"^{re.escape(stem)}_ch\d+\.json$")
    csv_pattern = re.compile(rf"^{re.escape(stem)}_ch\d+\.csv$")
    removed = 0

    json_dir = json_output_dir(source_filepath, output_root)
    if os.path.isdir(json_dir):
        for filename in os.listdir(json_dir):
            if json_pattern.match(filename):
                os.remove(os.path.join(json_dir, filename))
                removed += 1

    csv_dir = csv_output_dir(source_filepath, output_root)
    if os.path.isdir(csv_dir):
        for filename in os.listdir(csv_dir):
            if csv_pattern.match(filename):
                os.remove(os.path.join(csv_dir, filename))
                removed += 1

    return removed


def remove_empty_chapter_dirs(
    source_filepath: str,
    output_root: str | None = None,
) -> None:
    """Remove json/ and csv/ folders when empty."""
    for folder in (
        json_output_dir(source_filepath, output_root),
        csv_output_dir(source_filepath, output_root),
    ):
        if os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)


def finalize_chapter_outputs(
    source_filepath: str,
    output_root: str | None = None,
) -> int:
    """Delete chapter files and remove empty json/csv dirs."""
    removed = delete_chapter_outputs(source_filepath, output_root)
    remove_empty_chapter_dirs(source_filepath, output_root)
    return removed


def save_failed_response(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
