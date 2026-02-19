from typing import Any, Dict, List
import xml.etree.ElementTree as ET
import re



# Helper Functions

def _strip_namespace(tag: str) -> str:
    """Remove XML namespace if present."""
    return tag.rsplit("}", 1)[-1]


def _detect_convention(name: str) -> str:
    """Detect naming convention."""
    if "_" in name and name.upper() == name:
        return "SCREAMING_SNAKE"

    if "_" in name and name.lower() == name:
        return "snake_case"

    if re.fullmatch(r"[a-z]+([A-Z][a-z0-9]*)+", name):
        return "camelCase"

    if re.fullmatch(r"[A-Z][a-zA-Z0-9]*", name):
        return "PascalCase"

    return "other"


def _tokenize_identifier(name: str) -> List[str]:
    """Split identifier into tokens."""
    tokens = []

    # split snake_case first
    parts = name.split("_")

    for part in parts:
        # split camel/pascal case
        matches = re.findall(
            r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+",
            part
        )
        tokens.extend(matches)

    return [t.lower() for t in tokens if t]


# Identifier Extraction (DOM)


def extract_identifiers_dom(xml_str: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_str)
    identifiers = []

    # namespace handling
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    def tag(name):
        return f"{ns}{name}"

    def add_identifier(name, kind, scope):
        if not name:
            return

        name = name.strip()
        tokens = _tokenize_identifier(name)

        identifiers.append({
            "name": name,
            "kind": kind,
            "convention": _detect_convention(name),
            "length": len(name),
            "n_tokens": len(tokens),
            "tokens": tokens,
            "scope": scope,
        })

    # ---------- classes ----------
    for cls in root.findall(f".//{tag('class')}"):
        name_node = cls.find(tag("name"))
        if name_node is not None:
            add_identifier(name_node.text, "class", "global")

    # ---------- functions ----------
    for fn in root.findall(f".//{tag('function')}"):

        # function name
        name_node = fn.find(tag("name"))
        if name_node is not None:
            add_identifier(name_node.text, "function", "global")

        # parameters
        for param in fn.findall(f".//{tag('parameter')}"):
            name_node = param.find(f".//{tag('name')}")
            if name_node is not None:
                add_identifier(name_node.text, "parameter", "parameter")

        # local variables ONLY inside block
        for block in fn.findall(f".//{tag('block')}"):
            for decl in block.findall(f".//{tag('decl')}"):
                name_node = decl.find(tag("name"))
                if name_node is not None:
                    add_identifier(name_node.text, "variable", "local")

    # ---------- global variables ----------
    for decl in root.findall(f"./{tag('decl_stmt')}/{tag('decl')}"):
        name_node = decl.find(tag("name"))
        if name_node is not None:
            add_identifier(name_node.text, "variable", "global")

    return identifiers

# Aggregation

def aggregate_identifier_features(
    identifiers: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute file-level metrics.
    """

    if not identifiers:
        return {
            "n_identifiers": 0,
            "avg_identifier_length": 0.0,
            "avg_tokens_per_identifier": 0.0,
            "vocab_size": 0,
            "vocab_diversity": 0.0,
            "pct_snake_case": 0.0,
            "pct_camel_case": 0.0,
            "pct_pascal_case": 0.0,
        }

    n = len(identifiers)

    avg_length = sum(i["length"] for i in identifiers) / n
    avg_tokens = sum(i["n_tokens"] for i in identifiers) / n

    # collect vocabulary
    all_tokens = []
    for row in identifiers:
        all_tokens.extend(row.get("tokens", []))

    vocab = set(all_tokens)

    vocab_size = len(vocab)
    total_tokens = len(all_tokens)

    if total_tokens == 0:
        vocab_diversity = 0.0
    else:
        vocab_diversity = vocab_size / total_tokens

    pct_snake = sum(
        1 for i in identifiers if i["convention"] == "snake_case"
    ) / n

    pct_camel = sum(
        1 for i in identifiers if i["convention"] == "camelCase"
    ) / n

    pct_pascal = sum(
        1 for i in identifiers if i["convention"] == "PascalCase"
    ) / n

    return {
        "n_identifiers": n,
        "avg_identifier_length": avg_length,
        "avg_tokens_per_identifier": avg_tokens,
        "vocab_size": vocab_size,
        "vocab_diversity": vocab_diversity,
        "pct_snake_case": pct_snake,
        "pct_camel_case": pct_camel,
        "pct_pascal_case": pct_pascal,
    }

# Dataset Builder

def build_file_identifier_dataset(
    xml_by_file: Dict[str, str],
    parser: str = "dom"
) -> List[Dict[str, Any]]:
    """
    Build dataset rows for multiple files.
    """

    parser = parser.lower().strip()

    if parser not in {"dom", "sax"}:
        raise ValueError("parser must be 'dom' or 'sax'")

    dataset: List[Dict[str, Any]] = []

    for file_path in sorted(xml_by_file.keys()):
        xml_str = xml_by_file[file_path]

        # we only implemented DOM
        identifiers = extract_identifiers_dom(xml_str)

        agg = aggregate_identifier_features(identifiers)

        row = {
            "file_path": file_path,
            **agg
        }

        dataset.append(row)

    return dataset


# ============================================================
# SAX version not required for this assignment
# ============================================================

def extract_identifiers_sax(xml_str: str) -> List[Dict[str, Any]]:
    raise NotImplementedError(
        "SAX parser not implemented (DOM version used for DA1)."
    )
