import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BADGES_DIR = ROOT / ".github" / "badges"


def get_coverage_percent(xml_path: Path) -> int | None:
    """Extract coverage percentage from a coverage.xml file."""
    if not xml_path.exists():
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    line_rate = float(root.attrib.get("line-rate", 0))
    return round(line_rate * 100)


def badge_color(percent: int) -> str:
    """Return badge color based on coverage percentage."""
    if percent >= 90:
        return "#4c1"  # bright green
    if percent >= 75:
        return "#a3c51c"  # yellow-green
    if percent >= 60:
        return "#dfb317"  # yellow
    if percent >= 40:
        return "#fe7d37"  # orange
    return "#e05d44"  # red


def generate_combined_svg(results: dict[str, int]) -> str:
    """Generate a single badge with per-service colored segments."""
    label = "coverage"
    label_width = len(label) * 6.5 + 10

    # Build segments with individual colors
    segments = []
    for name, pct in results.items():
        text = f"{name} {pct}%"
        width = len(text) * 6.5 + 12
        segments.append({"text": text, "width": width, "color": badge_color(pct)})

    value_width = sum(s["width"] for s in segments)
    total_width = label_width + value_width

    # Build colored rectangles and text elements
    rects = ""
    texts = ""
    x = label_width
    for s in segments:
        rects += f'    <rect x="{x}" width="{s["width"]}" height="20" fill="{s["color"]}"/>\n'
        cx = x + s["width"] / 2
        texts += f'    <text x="{cx}" y="15" fill="#010101" fill-opacity=".3">{s["text"]}</text>\n'
        texts += f'    <text x="{cx}" y="14">{s["text"]}</text>\n'
        x += s["width"]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <rect width="{label_width}" height="20" fill="#555"/>
{rects}    <rect width="{total_width}" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width / 2}" y="14">{label}</text>
{texts}  </g>
</svg>"""


def main() -> None:
    BADGES_DIR.mkdir(exist_ok=True)

    services = {
        "backend": ROOT / "backend" / "coverage.xml",
        "scraper": ROOT / "scraper" / "coverage.xml",
        "bot": ROOT / "bot" / "coverage.xml",
    }

    results: dict[str, int] = {}
    for name, xml_path in services.items():
        percent = get_coverage_percent(xml_path)
        if percent is None:
            print(f"  {name}: no coverage.xml found, skipping")
            continue
        results[name] = percent
        print(f"  {name}: {percent}%")

    if results:
        svg = generate_combined_svg(results)
        badge_path = BADGES_DIR / "coverage.svg"
        badge_path.write_text(svg)
        print(f"  -> {badge_path}")

    # Clean up intermediate coverage artifacts
    for xml_path in services.values():
        for artifact in [xml_path, xml_path.with_name(".coverage")]:
            artifact.unlink(missing_ok=True)

    # Remove old per-service badges
    for name in services:
        old_badge = BADGES_DIR / f"coverage-{name}.svg"
        if old_badge.exists():
            old_badge.unlink()
            print(f"  removed old {old_badge.name}")


if __name__ == "__main__":
    main()
