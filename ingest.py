"""Create a human-review rule-pack draft from an official regulation PDF.

By default this only extracts text. With --ai-draft, Groq may suggest explicit
numerical rules, but every suggestion remains AI-DRAFT/HUMAN_REVIEW_REQUIRED and
is never activated automatically.
"""
import argparse
import os
from pathlib import Path

import fitz
import yaml

from src.ai_agent import AIServiceError, AIUnavailableError, extract_candidate_rules


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    document = fitz.open(path)
    return [(index + 1, page.get_text("text")) for index, page in enumerate(document)]


def chunk_pages(pages: list[tuple[int, str]], max_chars: int = 10000) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    labels: list[int] = []
    size = 0
    for page_number, text in pages:
        page_text = text.strip()
        if not page_text:
            continue
        if current and size + len(page_text) > max_chars:
            chunks.append((f"pages {labels[0]}-{labels[-1]}", "\n\n".join(current)))
            current, labels, size = [], [], 0
        current.append(f"[Page {page_number}]\n{page_text}")
        labels.append(page_number)
        size += len(page_text)
    if current:
        chunks.append((f"pages {labels[0]}-{labels[-1]}", "\n\n".join(current)))
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--output", type=Path, default=Path("data/rules/draft.yaml"))
    parser.add_argument("--ai-draft", action="store_true", help="Ask Groq to suggest candidate numerical rules for human review.")
    parser.add_argument("--max-ai-chunks", type=int, default=8, help="Safety/cost cap for Groq chunks (default: 8).")
    args = parser.parse_args()

    pages = extract_pdf_pages(args.pdf)
    full_text = "\n\n".join(f"[Page {number}]\n{text}" for number, text in pages)
    draft_rules: list[dict] = []
    uncertainties: list[str] = []

    if args.ai_draft:
        if not os.getenv("GROQ_API_KEY"):
            raise SystemExit("--ai-draft requires GROQ_API_KEY. Text-only draft creation works without a key.")
        try:
            for source_label, chunk in chunk_pages(pages)[: max(1, args.max_ai_chunks)]:
                result = extract_candidate_rules(
                    chunk, authority=args.authority, source_label=f"{args.pdf.name}, {source_label}"
                )
                draft_rules.extend(rule.model_dump() for rule in result.rules)
                uncertainties.extend(result.uncertainties)
        except (AIServiceError, AIUnavailableError) as error:
            raise SystemExit(f"AI drafting failed safely; no rules were activated: {error}") from error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "authority": args.authority,
            "version": "DRAFT",
            "status": "HUMAN_REVIEW_REQUIRED",
            "source_file": args.pdf.name,
            "generated_with_ai": bool(args.ai_draft),
            "activation_allowed": False,
        },
        "extracted_text_preview": full_text[:12000],
        "ai_uncertainties": uncertainties,
        "rules": draft_rules,
    }
    args.output.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Draft written to {args.output}. Every rule requires licensed-architect review before activation.")


if __name__ == "__main__":
    main()
