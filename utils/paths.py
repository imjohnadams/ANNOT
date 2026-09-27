import os


def book_stem(filepath: str) -> str:
    return os.path.splitext(os.path.basename(filepath))[0]


def converted_pdf_path(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    return os.path.join(
        annot_output_dir(source_filepath, output_root),
        f"{stem}_converted.pdf",
    )


def annot_output_dir(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    if output_root:
        return os.path.join(os.path.abspath(output_root), f"{stem}_annot")
    folder = os.path.dirname(os.path.abspath(source_filepath))
    return os.path.join(folder, f"{stem}_annot")


def json_output_dir(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    return os.path.join(annot_output_dir(source_filepath, output_root), "json")


def csv_output_dir(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    return os.path.join(annot_output_dir(source_filepath, output_root), "csv")


def logs_output_dir(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    return os.path.join(annot_output_dir(source_filepath, output_root), "logs")


def chapter_json_path(
    source_filepath: str,
    chapter_number: int,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    filename = f"{stem}_ch{chapter_number:02d}.json"
    return os.path.join(json_output_dir(source_filepath, output_root), filename)


def chapter_csv_path(
    source_filepath: str,
    chapter_number: int,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    filename = f"{stem}_ch{chapter_number:02d}.csv"
    return os.path.join(csv_output_dir(source_filepath, output_root), filename)


def master_json_path(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    return os.path.join(
        annot_output_dir(source_filepath, output_root),
        f"{stem}_master.json",
    )


def master_csv_path(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    return os.path.join(
        annot_output_dir(source_filepath, output_root),
        f"{stem}_master.csv",
    )


def highlighted_pdf_path(
    source_filepath: str,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    return os.path.join(
        annot_output_dir(source_filepath, output_root),
        f"{stem}_highlighted.pdf",
    )


def failed_response_path(
    source_filepath: str,
    chapter_number: int,
    attempt: int,
    output_root: str | None = None,
) -> str:
    stem = book_stem(source_filepath)
    filename = f"{stem}_ch{chapter_number:02d}_failed_{attempt}.txt"
    return os.path.join(logs_output_dir(source_filepath, output_root), filename)
