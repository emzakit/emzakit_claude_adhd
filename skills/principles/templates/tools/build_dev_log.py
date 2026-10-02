"""Build the styled diary from individual Markdown entries; no web server needed."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
from html import escape, unescape
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import textwrap
from urllib.parse import unquote, urlsplit

try:
    from bs4 import BeautifulSoup, Comment, NavigableString, Tag
    from markdown_it import MarkdownIt
    import yaml
except ImportError as error:
    raise SystemExit(
        "Missing documentation dependency. Install tools/requirements-dev-log.txt "
        "with this Python interpreter."
    ) from error


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "tools/dev-log-config.json"
PLACEHOLDER = "        <!-- DEV_LOG_ENTRIES -->"
SIGNATURE = re.compile(rb"\A<!-- Generated dev log; content-sha256: ([a-f0-9]{64}) -->\n")
REQUIRED = {"id", "date", "status", "title"}
ALLOWED = REQUIRED | {"status_class"}


class BuildError(ValueError):
    """An authoring error that leaves the last good HTML untouched."""


class UniqueSafeLoader(yaml.SafeLoader):
    """Safe YAML with explicit duplicate-key failures instead of silent overrides."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        keys = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise BuildError("Frontmatter keys must be text")
            if key in keys:
                raise BuildError(f"Duplicate frontmatter key {key!r}")
            keys.add(key)
        return super().construct_mapping(node, deep=deep)


def read_entry(path: Path) -> tuple[dict[str, str], str]:
    """Accept Obsidian-compatible YAML without constructing executable objects."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise BuildError(f"{path.name}: start with a --- frontmatter block")
    try:
        boundary = lines.index("---", 1)
    except ValueError as error:
        raise BuildError(f"{path.name}: frontmatter needs a closing ---") from error
    try:
        metadata = yaml.load("\n".join(lines[1:boundary]), Loader=UniqueSafeLoader)
    except (yaml.YAMLError, BuildError) as error:
        raise BuildError(f"{path.name}: invalid frontmatter: {error}") from error
    if not isinstance(metadata, dict):
        raise BuildError(f"{path.name}: frontmatter must contain named properties")
    unexpected = metadata.keys() - ALLOWED
    if unexpected:
        raise BuildError(f"{path.name}: unsupported metadata: {', '.join(sorted(unexpected))}")
    for key, value in metadata.items():
        if key == "date" and type(value) is date:
            value = value.isoformat()
        if key == "status_class" and value is None:
            value = ""
        if not isinstance(value, str) or any(ord(char) < 32 for char in value):
            raise BuildError(f"{path.name}: {key} must be a single-line string")
        if key in REQUIRED and not value.strip():
            raise BuildError(f"{path.name}: {key} cannot be empty")
        metadata[key] = value
    missing = REQUIRED - metadata.keys()
    if missing:
        raise BuildError(f"{path.name}: missing metadata: {', '.join(sorted(missing))}")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", metadata["id"]):
        raise BuildError(f"{path.name}: id must use lowercase letters, digits and hyphens")
    if metadata.get("status_class", "") not in {"", "history", "idea"}:
        raise BuildError(f"{path.name}: status_class must be empty, history or idea")
    body = "\n".join(lines[boundary + 1:]).strip()
    if not body:
        raise BuildError(f"{path.name}: entry body cannot be empty")
    return metadata, body


def render_markdown(body: str) -> BeautifulSoup:
    markdown = MarkdownIt("commonmark", {"html": True}).enable("table")
    validate_link = markdown.validateLink
    # Existing evidence includes explicit links to the owner's local archive.
    markdown.validateLink = lambda url: url.startswith("file:///") or validate_link(url)
    rendered = BeautifulSoup(markdown.render(body), "html.parser")
    for quote in list(rendered.find_all("blockquote")):
        paragraph = quote.find("p", recursive=False)
        first_text = paragraph.contents[0] if paragraph and paragraph.contents else None
        marker = re.match(r"^\[!note\]([+-]) (.+?)(?:\n|$)", str(first_text or ""))
        if marker and isinstance(first_text, NavigableString):
            details = rendered.new_tag("details")
            if marker[1] == "+":
                details["open"] = ""
            summary = rendered.new_tag("summary")
            summary.string = marker[2]
            details.append(summary)
            first_text.replace_with(str(first_text)[marker.end():])
            if not paragraph.get_text().strip() and not paragraph.find():
                paragraph.decompose()
            for child in list(quote.contents):
                details.append(child.extract())
            quote.replace_with(details)
        else:
            quote["class"] = ["quote"]
            paragraphs = quote.find_all("p", recursive=False)
            if len(paragraphs) == 1 and not quote.find(["ul", "ol", "blockquote"]):
                paragraphs[0].unwrap()
    return rendered


def readable_html(node: Tag, level: int = 4) -> str:
    """Two-space blocks and wrapped prose, preserving inline and literal HTML."""
    indent = "  " * level
    literal = {"pre", "script", "style", "textarea"}
    blocks = {"article", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol",
              "li", "details", "summary", "blockquote", "table", "thead", "tbody", "tr",
              "th", "td", "section", "aside"}
    if node.name in literal:
        return indent + str(node)
    opening = str(node).split(">", 1)[0] + ">"
    closing = f"</{node.name}>"
    if node.name in {"hr", "br", "img", "input"}:
        return indent + str(node)
    if not any(isinstance(child, Tag) and child.name in blocks for child in node.children):
        contents = re.sub(r"\s*\n\s*", " ", node.decode_contents()).strip()
        # Code spans are literal; do not wrap or normalize their internal spaces.
        if node.find("code"):
            return f"{indent}{opening}\n{indent}  {contents}\n{indent}{closing}"
        short = opening + contents + closing
        if len(indent + short) <= 100:
            return indent + short
        prose = textwrap.fill(contents, width=100, initial_indent=indent + "  ",
                              subsequent_indent=indent + "  ", break_long_words=False,
                              break_on_hyphens=False)
        return f"{indent}{opening}\n{prose}\n{indent}{closing}"
    children = []
    for child in node.children:
        if isinstance(child, Comment):
            children.append(indent + "  <!--" + str(child) + "-->")
        elif isinstance(child, Tag):
            children.append(readable_html(child, level + 1))
        elif str(child).strip():
            children.append(textwrap.fill(escape(str(child).strip(), quote=False), width=100,
                                          initial_indent=indent + "  ",
                                          subsequent_indent=indent + "  ",
                                          break_long_words=False, break_on_hyphens=False))
    return "\n".join([indent + opening, *children, indent + closing])


def render_entry(metadata: dict[str, str], body: str) -> str:
    rendered = render_markdown(body)
    article = rendered.new_tag("article", attrs={"class": "entry search-unit", "id": metadata["id"]})
    stamp = rendered.new_tag("div", attrs={"class": "stamp"})
    stamp.append(metadata["date"] + " ")
    badge = rendered.new_tag("span", attrs={"class": "badge" + (" " + metadata["status_class"] if metadata.get("status_class") else "")})
    badge.string = metadata["status"]
    stamp.append(badge)
    heading = rendered.new_tag("h2")
    heading.string = metadata["title"]
    article.append(stamp)
    article.append(heading)
    for child in list(rendered.contents):
        article.append(child.extract())
    return readable_html(article)


def build(entry_dir: Path, template_path: Path) -> tuple[str, dict[Path, bytes]]:
    files = sorted(path for path in entry_dir.glob("*.md") if not path.name.startswith("."))
    if not files:
        raise BuildError(f"No Markdown entries found in {entry_dir}")
    snapshot = {path: path.read_bytes() for path in [template_path, *files]}
    template = snapshot[template_path].decode("utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise BuildError("HTML template must contain exactly one DEV_LOG_ENTRIES placeholder")
    ids = {node["id"] for node in BeautifulSoup(template, "html.parser").select("[id]")}
    numbers = set()
    articles = []
    for path in files:
        filename = re.fullmatch(r"([0-9]{3})-[a-z0-9-]+\.md", path.name)
        if not filename or filename[1] == "000":
            raise BuildError(f"{path.name}: use a filename such as 048-short-name.md")
        if filename[1] in numbers:
            raise BuildError(f"{path.name}: duplicate entry number {filename[1]}")
        numbers.add(filename[1])
        metadata, body = read_entry(path)
        if metadata["id"] in ids:
            raise BuildError(f"{path.name}: duplicate id {metadata['id']!r}")
        entry = render_entry(metadata, body)
        for element in BeautifulSoup(entry, "html.parser").select("[id]"):
            if element["id"] in ids:
                raise BuildError(f"{path.name}: duplicate id {element['id']!r}")
            ids.add(element["id"])
        articles.append(entry)
    return template.replace(PLACEHOLDER, "\n\n".join(articles)), snapshot


def output_html(html: str, output: Path, source_docs: Path) -> bytes:
    """Keep copied local assets; point other vault links at existing project files."""
    if output.parent.resolve() != source_docs.resolve():
        def replace_link(match: re.Match) -> str:
            url = unescape(match["value"])
            parts = urlsplit(url)
            if parts.scheme or parts.netloc or not parts.path:
                return match[0]
            relative = unquote(parts.path)
            local = output.parent / relative
            if local.resolve() == output.resolve() or local.exists():
                return match[0]
            target = source_docs / relative
            if not target.exists():
                raise BuildError(f"Cannot resolve {url!r} for {output}")
            rewritten = target.resolve().as_uri()
            if parts.query:
                rewritten += "?" + parts.query
            if parts.fragment:
                rewritten += "#" + parts.fragment
            return match["name"] + "=" + match["quote"] + escape(rewritten, quote=True) + match["quote"]
        attribute = re.compile(r'(?P<name>\b(?:href|src))=(?P<quote>[\"\'])(?P<value>.*?)(?P=quote)', re.S)
        # Limit rewriting to HTML tags; prose and the retained search script stay intact.
        html = re.sub(r"<[a-zA-Z][^<>]*>", lambda tag: attribute.sub(replace_link, tag[0]), html)
    content = html.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    return f"<!-- Generated dev log; content-sha256: {digest} -->\n".encode() + content


def configuration(options: argparse.Namespace) -> tuple[Path, Path, Path, list[Path]]:
    path = options.config.resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BuildError(f"Invalid JSON configuration: {path}") from error
    if not isinstance(data, dict) or set(data) != {"entries", "template", "source_docs", "outputs"}:
        raise BuildError("Configuration needs entries, template, source_docs and outputs")
    if any(not isinstance(data[key], str) or not data[key] for key in ("entries", "template", "source_docs")):
        raise BuildError("Configuration paths must be nonempty strings")
    if not isinstance(data["outputs"], list) or not data["outputs"] or any(not isinstance(item, str) or not item for item in data["outputs"]):
        raise BuildError("Configuration outputs must be a nonempty list of paths")
    resolve = lambda value: (path.parent / value).resolve()
    entries = options.entries_dir.resolve() if options.entries_dir else resolve(data["entries"])
    template = options.template.resolve() if options.template else resolve(data["template"])
    outputs = [item.resolve() for item in options.output] if options.output else [resolve(item) for item in data["outputs"]]
    if len(set(outputs)) != len(outputs):
        raise BuildError("Output paths must be unique")
    if template in outputs or any(item.suffix.lower() != ".html" for item in outputs):
        raise BuildError("Outputs must be HTML files distinct from the template")
    return entries, template, resolve(data["source_docs"]), outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report stale HTML without writing files")
    parser.add_argument("--config", type=Path, default=CONFIG, help="Authoring/output path configuration")
    parser.add_argument("--entries-dir", type=Path, help="Read entries from a staging/test directory")
    parser.add_argument("--template", type=Path, help="Read an alternate HTML template")
    parser.add_argument("--output", type=Path, action="append", help="Write/check this output instead of configured outputs; repeatable")
    parser.add_argument("--adopt-existing-html", action="store_true",
                        help="Explicitly replace unsigned or manually edited HTML after preserving its changes")
    options = parser.parse_args()
    try:
        entry_dir, template, source_docs, outputs = configuration(options)
        originals = {output: output.read_bytes() if output.exists() else None for output in outputs}
        html, snapshot = build(entry_dir, template)
        expected = {output: output_html(html, output, source_docs) for output in outputs}
        changed = [output for output in outputs if originals[output] != expected[output]]
        if not changed:
            print("Dev log is up to date.")
            return 0
        if options.check:
            raise BuildError("Dev log is stale. Run: python tools/build_dev_log.py")
        for output in changed:
            original = originals[output]
            if original is not None and not options.adopt_existing_html:
                signature = SIGNATURE.match(original)
                if not signature or signature[1].decode() != hashlib.sha256(original[signature.end():]).hexdigest():
                    raise BuildError(f"{output}: generated HTML has manual or untracked changes. Preserve them in the entry files/template before using --adopt-existing-html.")
        if any(path.read_bytes() != data for path, data in snapshot.items()):
            raise BuildError("An authoring file changed during the build; retry with the latest content")
        current_files = {path for path in entry_dir.glob("*.md") if not path.name.startswith(".")}
        if current_files != set(snapshot) - {template}:
            raise BuildError("The entry list changed during the build; retry")
        for output in outputs:
            if (output.read_bytes() if output.exists() else None) != originals[output]:
                raise BuildError(f"{output}: HTML changed during the build; preserve those changes before retrying")
        temporary = {}
        try:
            for output in changed:
                with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".dev-log-", suffix=".tmp", delete=False) as file:
                    temporary[output] = Path(file.name)
                    file.write(expected[output])
            for output, path in temporary.items():
                os.replace(path, output)
        finally:
            for path in temporary.values():
                if path.exists():
                    path.unlink()
        print(f"Built {len(snapshot) - 1} entries into {len(changed)} HTML file(s).")
        return 0
    except (BuildError, OSError, UnicodeError) as error:
        print(f"Dev log build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
