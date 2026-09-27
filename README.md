# ANNOT

ANNOT is a terminal tool that reads one research document and writes grounded notes onto a PDF, a JSON file, and a CSV file. It is for students working through psychology, engineering, and social-science articles, reports, and chapters they already have.

## Overview

You give ANNOT a document, choose the sections to analyze, and set a maximum number of notes per page. It sends that text to a language model, checks that each quote appears in the section, then highlights the quotes and draws the notes on the PDF.

The notes explain what the author is doing in the supplied text. They are reading aids for a document you are already reading. The tool does not search other papers, run a literature review, or decide whether a claim is true outside this document. If a course requires you to say when a tool helped, say so.

Page numbers in the output are PDF page numbers, not the printed page numbers in a book or journal.

## Features

- Reads a PDF directly. EPUB, MOBI, AZW, AZW3, and plain TXT are converted to PDF with Calibre.
- Finds sections from the PDF outline, large headings, chapter labels, or common article headings such as Abstract, Methods, and Results.
- Lets you pick sections and cap notes per page from 1 to 10. The cap is a maximum. A blank or unimportant page can have no note.
- Offers three quality levels: what an important passage means, why it matters, or the concepts, evidence, methods, assumptions, and limits the text supports.
- Stores a category and a grounding label on every note: `source_fact`, `interpretation`, or `uncertain`. The model is instructed to use `interpretation` when a note goes beyond the passage.
- Rejects a quote that is not in the section. That quote becomes `[UNKNOWN]`, its note is cleared, and it is not highlighted. A failed quote does not take a density slot from a quote that is on the page.
- Writes a highlighted PDF, a master JSON file, and a master CSV file.
- Can place notes from an existing JSON or CSV onto a PDF without calling the model.
- Can compare the quotes chosen in two CSV runs.

Figure and table notes use the caption and nearby text.

## Tech Stack

- **Language:** Python 3.10 or newer
- **PDF:** PyMuPDF, for text extraction and for drawing highlights and notes
- **Model API:** the OpenAI Python SDK, using Chat Completions with `max_completion_tokens` and a strict JSON schema
- **Configuration:** python-dotenv
- **Token estimates:** tiktoken (`cl100k_base`)
- **Optional conversion:** Calibre (`ebook-convert`)
- **Tests:** pytest

## Architecture

`main.py` is the entry point. A run follows this path:

1. **Ingest.** A PDF is used as it is. EPUB, MOBI, AZW, AZW3, and TXT are converted with Calibre into a temporary PDF in the output folder.
2. **Parse.** PyMuPDF reads the text layer. Lines that repeat at the top or bottom of many pages are removed before the model sees the text. Title and author come from PDF metadata. A missing title becomes the working PDF's file name. A missing author is left blank and shown as unavailable. Neither value is guessed. A page with no selectable text is stored as `[NO TEXT FOUND]`.
3. **Sections.** Detection tries the PDF outline, then large headings near the top of a page, then lines that look like "Chapter" or "Part," then common article headings. A method is kept only when it finds at least two sections. Otherwise the document is one section titled "Full document," starting at the first page that does not look like front matter. If none is found in the first 25 pages, it starts at page 1. Outline, heading, and chapter-label detection also skip book-style front matter. Article-heading detection does not.
4. **Settings.** You choose sections, a density cap, and a quality level. Before you confirm, the terminal prints a local token and cost estimate from the fixed rates in `config.py`. The same rates are applied to actual token counts after each section. The terminal warns when the high end of the estimate is above $0.75. A selection of 100 or more pages skips the quality prompt and uses Medium.
5. **Model.** The request combines `prompt.md`, a short overlay for the density cap and quality level, a document frame, and the current pages. The frame is the title, the author, the section list, and the opening pages, within a token cap. When a long section is split, each later chunk also receives the previous page as context. The model is told not to quote that page. The default model is `gpt-5.6-luna`. `LUNA_BASE_URL` must accept an OpenAI Chat Completions request that sets `max_completion_tokens` and a strict JSON schema. Each section is tried up to three times. A failed response is saved under `logs/`.
6. **Checks.** A quote must appear in the cleaned text of its page, or in that text with whitespace collapsed. If it appears on a different page in the same section, the page number is corrected. If it cannot be found, `book_text` and the note become `[UNKNOWN]`. The density cap then keeps at most the chosen number of notes per page and prefers a quote that is still in the document. An invalid category becomes `CONTEXT`. An invalid grounding label becomes `uncertain`.
7. **Output.** Each finished section is saved as JSON and CSV, then combined into the master files. When you stop selecting sections, and at least one attempt succeeded, the per-section files are removed and PDFER highlights the quotes in yellow. Each note is drawn as black text in a white box along the right margin. If the free margin is narrower than 72 points, the box is still 72 points wide and can cover the text beside it. The master files and `logs/` remain. If no quote can be placed, the highlighted PDF is not created. The temporary converted PDF is deleted after a successful highlight.

Where to read next:

- `cli/` — prompts, section selection, and the pre-run summary
- `ingest/` — Calibre conversion
- `pdf/` — text extraction, header and footer stripping, and section detection
- `ai/` — the model client, JSON schema, document frame, and chunking
- `prompt.md` — instructions sent with every request
- `validate/` — quote checks and the density cap
- `output/` — JSON and CSV writers
- `pipeline/` — the analysis run and the call into PDFER
- `PDFER/` — highlight and note placement, including a standalone script
- `compare_csvs.py` — quote comparison between two CSV files

## Getting Started

### Prerequisites

- Python 3.10 or newer
- An API key for an endpoint that accepts the Chat Completions request described above
- Calibre, only for EPUB, MOBI, AZW, AZW3, or TXT

### Installation

From the repository root:

```text
python -m venv .venv
```

On Windows (PowerShell):

```text
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On Windows (Command Prompt):

```text
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

On macOS or Linux:

```text
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment

Copy `.env.example` to `.env` in the repository root. ANNOT loads that file from the directory that contains `config.py`. A variable already set in the environment is left as it is.

- `LUNA_API_KEY` (required) — API key. The program stops if this is empty.
- `LUNA_BASE_URL` (optional) — API base URL. Default: `https://api.openai.com/v1`.
- `LUNA_MODEL` (optional) — model name. Default: `gpt-5.6-luna`.
- `CALIBRE_PATH` (optional) — path to `ebook-convert`, or to the folder that contains it (`ebook-convert.exe` on Windows). Set this when `ebook-convert` is not on `PATH`. On Windows, ANNOT also looks in the standard `Calibre2` folders under Program Files. The variable can live in `.env` or in the environment. PDF input does not need it.

```text
LUNA_API_KEY=your-api-key-here
LUNA_BASE_URL=https://api.openai.com/v1
LUNA_MODEL=gpt-5.6-luna
```

Keep the key out of source code. `.env` is listed in `.gitignore`.

### Run

From the repository root:

```text
python main.py
```

## Usage

1. Enter the document path.
2. Choose whether to use a custom output folder. The files still go in `{stem}_annot` inside that folder, where `stem` is the document name without its extension.
3. Review the detected sections. The index shows page ranges and a token estimate.
4. Select sections. Examples: `5`, `4-7`, `5, 7, 9`, `2-4, 6`. Numbers that are not in the document are skipped.
5. Set annotation density, the maximum notes per page (1–10). Press Enter for the default, `1`.
6. Set quality, unless the selection is 100 or more pages:
   - `1` Low — what important passages mean
   - `2` Medium — meaning and why the passage matters (default)
   - `3` High — concepts, evidence, methods, assumptions, and limits
7. Confirm. A density of 3 or more combined with High quality asks you to confirm again.
8. Optionally analyze more sections. After you stop, the highlighted PDF is written if at least one attempt succeeded.

For a file named `study.pdf`, the default output folder is `study_annot` next to that file:

- `study_highlighted.pdf` — the original pages with yellow highlights and notes
- `study_master.json` — notes for each section, a UTC timestamp, and run metadata (model name, token totals, quality, and density cap)
- `study_master.csv` — one row per note
- `logs/` — failed model responses
- `json/` and `csv/` — one file per section while you are still selecting sections. Those files are removed when highlighting starts. The master files remain.

CSV columns:

`document`, `chapter`, `chapter_title`, `page`, `category`, `grounding`, `source_text`, `annotation`, `quality`, `density`

Categories: CONCEPT, METHOD, RESULT, EVIDENCE, DEFINITION, INTERPRETATION, LIMITATION, ASSUMPTION, IMPORTANT, QUESTION, CONTEXT, TECHNICAL.

Each JSON note includes the page, the source quote (`book_text`), the note, a category, and a grounding label. A row can also include `validation_flags` when a quote was repaired or a note was flagged. If an attempt fails, section files already saved are kept. The highlighted PDF is written when you stop selecting sections, and only if at least one attempt in the session finished successfully.

To place notes from an existing JSON or CSV onto a PDF without calling the model:

```text
python PDFER/highlight.py --pdf paper.pdf --json paper_master.json --out paper_highlighted.pdf
```

`--json` accepts a master or section JSON file, or a CSV. Prefer JSON. The CSV loader can mangle quotes that contain commas or newlines. Other flags:

- `--color r,g,b` — highlight color, channels from 0–1 or 0–255. Default is yellow.
- `--report report.json` — write hits and misses
- `--neighbor-pages` — if a quote is missing on its page, also search the adjacent pages
- `--no-notes` — highlights only

Without `--pdf` and `--json`, the script asks for the paths.

To compare quote selections in two CSV files:

```text
python compare_csvs.py first.csv second.csv
```

Quotes on the same page match when one contains the other, or when their similarity is at least `--threshold` (default `0.85`). Empty quotes and `[UNKNOWN]` are skipped. `PDFER/highlight.py` and `compare_csvs.py` do not call the model and do not read `LUNA_API_KEY`.

### Limitations

- Only the text layer is read. A scanned page without selectable text cannot be analyzed. Images are not interpreted.
- Unusual layouts can fall through to a single "Full document" section.
- A selection of 100 or more pages uses Medium quality.
- On a narrow margin, a note box can cover the right edge of the page.
- Notes can be wrong, shallow, or overly cautious. Check them against the page.
- A password-protected or unreadable PDF stops when the file is opened.

## Testing

Install the project requirements, then the test dependency, and run pytest from the repository root:

```text
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest
```

The tests cover section-selection parsing, article-heading detection, category and grounding fallback, quote verification and the density cap, JSON and CSV export, the document frame, and highlight placement. They do not call the API. `pytest.ini` puts the repository root on the Python path.

## License

Released under the MIT License. See [LICENSE](LICENSE).
