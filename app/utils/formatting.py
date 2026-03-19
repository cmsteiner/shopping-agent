"""
SMS formatting utilities.

Provides format_list and split_sms for turning a list_data dict into
one or more SMS-sized text chunks.
"""
from datetime import date

from app.utils.category import CANONICAL_CATEGORIES, normalize_category

FOOTER = "* = pending confirmation\nReply DONE when finished."


def _category_sort_key(category: str) -> int:
    """Return sort index for a category (canonical order; unknowns go last)."""
    normalized = normalize_category(category)
    try:
        return CANONICAL_CATEGORIES.index(normalized)
    except ValueError:
        return len(CANONICAL_CATEGORIES)


def _format_quantity(qty) -> str:
    """Format a quantity as 'x2' or 'x2.5' etc., stripping unnecessary decimals."""
    if qty is None:
        return ""
    # Convert to int if it is a whole number
    try:
        float_val = float(qty)
    except (TypeError, ValueError):
        return f" x{qty}"
    if float_val == int(float_val):
        return f" x{int(float_val)}"
    return f" x{float_val}"


def format_list(list_data: dict) -> str:
    """
    Format a list_data dict (as returned by list_service.get_list) into a
    single SMS string.

    Parameters
    ----------
    list_data : dict
        Must have key "items_by_category" mapping category -> list of item dicts.

    Returns
    -------
    str
        Formatted SMS text including header, category blocks, and footer.
    """
    today = date.today()
    # strftime('%#d') strips leading zero on Windows; '%-d' works on Linux/Mac.
    # Use int() conversion to avoid platform-specific format codes.
    header = f"SHOPPING LIST - {today.strftime('%b')} {today.day}"

    items_by_category: dict = list_data.get("items_by_category", {})

    # Sort categories by canonical order
    sorted_categories = sorted(items_by_category.keys(), key=_category_sort_key)

    lines = [header, ""]

    for category in sorted_categories:
        items = items_by_category[category]
        lines.append(category.upper())
        for item in items:
            name = item["name"]
            qty_suffix = _format_quantity(item.get("quantity"))
            brand = item.get("brand_pref")
            brand_suffix = f" ({brand})" if brand else ""
            pending_suffix = "*" if item.get("status") == "PENDING" else ""
            lines.append(f"- {name}{qty_suffix}{brand_suffix}{pending_suffix}")
        lines.append("")  # blank line after each category block

    lines.append(FOOTER)

    return "\n".join(lines)


def split_sms(text: str, max_chars: int = 1500) -> list[str]:
    """
    Split a formatted list string into SMS-sized chunks at category boundaries.

    If the text fits within max_chars, returns it as a single-element list
    with no part-number prefix.

    If it does not fit, splits at blank lines that precede a category header
    (i.e., the blank line before a non-item, non-header, non-footer line).
    Each chunk is prefixed with (N/M)\n. The footer only appears on the last chunk.

    Parameters
    ----------
    text : str
    max_chars : int

    Returns
    -------
    list[str]
    """
    if len(text) <= max_chars:
        return [text]

    # Separate footer from body
    footer_marker = "* = pending confirmation"
    if footer_marker in text:
        footer_start = text.index(footer_marker)
        body = text[:footer_start].rstrip("\n")
        footer = text[footer_start:]
    else:
        body = text
        footer = ""

    # Split body into "segments" — each segment is a category block
    # (the category header line + its item lines + trailing blank).
    # The first segment is the header block (SHOPPING LIST - ... + blank line).
    segments: list[str] = []
    current_lines: list[str] = []

    raw_lines = body.split("\n")
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        # Detect start of a new category block: a blank line followed by an
        # ALL-CAPS category header (not an item line, not the SMS header).
        if (
            line == ""
            and i + 1 < len(raw_lines)
            and raw_lines[i + 1]
            and not raw_lines[i + 1].startswith("-")
            and not raw_lines[i + 1].startswith("(")
            and raw_lines[i + 1] == raw_lines[i + 1].upper()
            and not raw_lines[i + 1].startswith("SHOPPING LIST")
        ):
            # Save current segment (strip trailing blank)
            if current_lines:
                segments.append("\n".join(current_lines).rstrip("\n"))
            current_lines = []
            i += 1  # skip the blank line before the category header
        else:
            current_lines.append(line)
            i += 1

    if current_lines:
        segments.append("\n".join(current_lines).rstrip("\n"))

    # Now greedily pack segments into chunks, keeping each chunk <= max_chars.
    # The prefix "(N/M)\n" is added later once we know N and M.
    # The footer is appended only to the last chunk.
    # We estimate prefix length as "(99/99)\n" = 8 chars; we'll verify after.

    def _build_chunks(segments: list[str], footer: str, max_chars: int) -> list[str]:
        # Greedy packing: estimate chunk sizes using a fixed prefix-length
        # placeholder ("(99/99)\n" = 8 chars). Correct prefixes are added in
        # the second pass once the total chunk count is known.
        placeholder_prefix_len = 8

        chunks_content: list[str] = []
        current_parts: list[str] = []

        for seg in segments:
            if not current_parts:
                current_parts = [seg]
            else:
                joined = "\n\n".join(current_parts + [seg])
                # Estimate: prefix + joined + footer (for last chunk)
                estimated = placeholder_prefix_len + len(joined) + len("\n\n" + footer) + 10
                if estimated <= max_chars:
                    current_parts.append(seg)
                else:
                    chunks_content.append("\n\n".join(current_parts))
                    current_parts = [seg]

        if current_parts:
            chunks_content.append("\n\n".join(current_parts))

        # Now we know n_chunks; build final chunks with correct prefixes
        n = len(chunks_content)
        result = []
        for idx, content in enumerate(chunks_content):
            prefix = f"({idx + 1}/{n})\n"
            if idx == n - 1 and footer:
                chunk = prefix + content + "\n\n" + footer
            else:
                chunk = prefix + content
            # If this chunk still exceeds max_chars, we can't split further
            # (no more category boundaries), just include it as-is.
            result.append(chunk)

        return result

    chunks = _build_chunks(segments, footer, max_chars)

    # Verify all chunks fit; if not, return them anyway (can't split mid-category)
    return chunks
