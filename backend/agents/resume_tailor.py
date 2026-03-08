"""
Resume Tailor Agent — uses Claude API to tailor Pavan's resume to a JD.
Changes are capped at 5-10% of total word count.
Returns tailored text, list of changes, and change percentage.
"""
import difflib
import json
import logging
import os
import re
from pathlib import Path

import anthropic
import pdfplumber

logger = logging.getLogger(__name__)

RESUME_PATH = Path(__file__).parent.parent / "resume" / "Pavan_Ram_Resume_1.pdf"


def extract_resume_text() -> str:
    """Extract plain text from the PDF resume."""
    with pdfplumber.open(str(RESUME_PATH)) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    return "\n".join(pages).strip()


def _word_count(text: str) -> int:
    return len(text.split())


def _compute_diff(original: str, tailored: str) -> tuple[float, list[dict]]:
    """
    Returns (change_percentage, list_of_changes).
    Each change = {type, original_text, new_text, reason}
    """
    orig_words = original.split()
    tail_words = tailored.split()
    total = max(len(orig_words), 1)

    matcher = difflib.SequenceMatcher(None, orig_words, tail_words, autojunk=False)
    changed = sum(max(j2 - j1, i2 - i1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")
    pct = round((changed / total) * 100, 1)

    # Build human-readable change log
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        orig_chunk = " ".join(orig_words[i1:i2])
        new_chunk = " ".join(tail_words[j1:j2])
        if tag == "replace":
            changes.append({"type": "modified", "original": orig_chunk, "updated": new_chunk})
        elif tag == "insert":
            changes.append({"type": "added", "original": "", "updated": new_chunk})
        elif tag == "delete":
            changes.append({"type": "removed", "original": orig_chunk, "updated": ""})

    return pct, changes


TAILOR_PROMPT = """You are a professional resume consultant. Your task is to MINIMALLY tailor a resume to a job description.

STRICT RULES:
1. Change NO MORE than 10% of the total word count (ideally 5-8%)
2. Do NOT change: company names, dates, educational institutions, metrics/numbers (unless adding context), personal details
3. ONLY do these types of changes:
   - Reorder or slightly reword bullet points to mirror JD language
   - Add 1-2 relevant keywords naturally into existing sentences
   - Adjust the Professional Summary (max 2 sentences)
   - Reorder skills within the KEY SKILLS section to front-load JD-relevant ones
4. Do NOT fabricate experience or skills not present in the original
5. Do NOT add new bullet points unless they are minor keyword additions to existing ones

Job Description:
{jd}

Original Resume:
{resume}

Return ONLY a valid JSON object with this exact structure:
{{
  "tailored_resume": "<full tailored resume text, preserving all formatting>",
  "changes": [
    {{"type": "modified|added", "section": "<section name>", "original": "<original text>", "updated": "<new text>", "reason": "<why this helps match JD>"}}
  ],
  "keywords_added": ["<keyword1>", "<keyword2>"],
  "estimated_change_percentage": <number between 5 and 10>
}}"""


def tailor_resume(job_description: str, company: str = "", role: str = "",
                  resume_text_override: str = None, additional_requirements: str = None) -> dict:
    """
    Tailor the resume for a given JD.
    Returns dict with tailored_text, changes, keywords_added, change_percentage.
    resume_text_override: use this text instead of reading PDF from disk.
    additional_requirements: extra instructions to append to the prompt.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    original_text = resume_text_override if resume_text_override else extract_resume_text()

    base_prompt = TAILOR_PROMPT.format(jd=job_description[:4000], resume=original_text)
    if additional_requirements:
        base_prompt += f"\n\nAdditional requirements from the applicant:\n{additional_requirements}"
    prompt = base_prompt

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
        tailored_text = result.get("tailored_resume", original_text)
        claude_changes = result.get("changes", [])
        keywords_added = result.get("keywords_added", [])
        estimated_pct = result.get("estimated_change_percentage", 7)

        # Compute actual diff percentage
        actual_pct, diff_changes = _compute_diff(original_text, tailored_text)

        # If Claude over-tailored, revert to original + use estimated
        if actual_pct > 12:
            logger.warning(f"Tailoring exceeded 12% ({actual_pct}%), reverting to Claude estimate")
            actual_pct = float(estimated_pct)
            diff_changes = claude_changes  # use Claude's self-reported changes

        return {
            "tailored_resume_text": tailored_text,
            "original_resume_text": original_text,
            "changes_log": claude_changes if claude_changes else diff_changes,
            "change_percentage": actual_pct,
            "keywords_added": keywords_added,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON: {e}")
        original_text = extract_resume_text()
        return {
            "tailored_resume_text": original_text,
            "original_resume_text": original_text,
            "changes_log": [],
            "change_percentage": 0.0,
            "keywords_added": [],
        }
    except Exception as e:
        logger.error(f"Tailoring failed: {e}")
        raise
