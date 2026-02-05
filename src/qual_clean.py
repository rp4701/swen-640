from typing import Any, Dict, Optional, Tuple
import re


# ---- User Canonicalization ----

BOT_PATTERNS = [
    r"\[bot\]$",
    r"^dependabot$",
    r"^renovate$",
    r"^github-actions$",
    r"^gitlab-ci$",
]


def canonicalize_user(login: Optional[str]) -> Tuple[str, bool]:
    """Canonicalize a user login and detect bot accounts."""
    if not login:
        return "", False

    login_norm = login.strip().lower()
    is_bot = any(re.search(pattern, login_norm) for pattern in BOT_PATTERNS)

    return login_norm, is_bot


# ---- Text Normalization ----

# FIX 1: Remove optional language from fenced code blocks
FENCED_CODE_RE = re.compile(
    r"```(?:\w+)?\n(.*?)```",
    re.DOTALL
)

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
HEADING_RE = re.compile(r"^\s*#+\s*", re.MULTILINE)

# FIX 2: Include '+' as valid list marker
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+", re.MULTILINE)

CONTROL_CHARS_RE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")
MULTI_BLANK_RE = re.compile(r"\n{3,}")
MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


def normalize_text(md: Optional[str]) -> str:
    """Convert Markdown-like text into clean plain text for analysis."""
    if md is None:
        return ""

    text = md

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Fenced code blocks FIRST
    text = FENCED_CODE_RE.sub(lambda m: f"<CODE>{m.group(1)}</CODE>", text)

    # Inline code SECOND
    text = INLINE_CODE_RE.sub(lambda m: f"<CODE>{m.group(1)}</CODE>", text)

    # Remove markdown headings
    text = HEADING_RE.sub("", text)

    # Remove list markers
    text = LIST_RE.sub("", text)

    # Remove ASCII control characters except newline
    text = CONTROL_CHARS_RE.sub("", text)

    # Collapse excessive blank lines
    text = MULTI_BLANK_RE.sub("\n\n", text)

    # Collapse multiple spaces/tabs
    text = MULTI_SPACE_RE.sub(" ", text)

    return text.strip()


# ---- Commit Message Parsing ----

CC_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?:\s+"
    r"(?P<subject>.+)$"
)


def split_commit_message(msg: Optional[str]) -> Dict[str, Any]:
    """Parse a commit message into Conventional Commit components."""
    if not msg:
        return {
            "subject": "",
            "body": "",
            "type": None,
            "scope": None,
            "breaking": False,
        }

    # Normalize newlines
    msg = msg.replace("\r\n", "\n").replace("\r", "\n")

    lines = msg.split("\n", 1)
    first_line = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    match = CC_RE.match(first_line)

    if match:
        cc_type = match.group("type").lower()
        scope = match.group("scope")
        breaking = bool(match.group("breaking"))
        subject = match.group("subject").strip()
    else:
        cc_type = None
        scope = None
        breaking = False
        subject = first_line

    return {
        "subject": subject,
        "body": body,
        "type": cc_type,
        "scope": scope,
        "breaking": breaking,
    }
