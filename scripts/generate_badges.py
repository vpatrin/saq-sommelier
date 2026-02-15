"""Generate coverage badge SVGs from coverage XML reports.

Usage: python scripts/generate_badges.py

Reads coverage XML files from each service and generates SVG badges
in the badges/ directory. No external dependencies required.
"""

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


def generate_svg(label: str, percent: int) -> str:
    """Generate a shields.io-style SVG badge."""
    color = badge_color(percent)
    value = f"{percent}%"
    # Approximate text widths (shields.io style)
    label_width = len(label) * 6.5 + 10
    value_width = len(value) * 7.5 + 10
    total_width = label_width + value_width

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
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#b)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width / 2}" y="14">{label}</text>
    <text x="{label_width + value_width / 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width / 2}" y="14">{value}</text>
  </g>
</svg>"""


def main() -> None:
    BADGES_DIR.mkdir(exist_ok=True)

    services = {
        "backend": ROOT / "backend" / "coverage.xml",
        "scraper": ROOT / "scraper" / "coverage.xml",
    }

    for name, xml_path in services.items():
        percent = get_coverage_percent(xml_path)
        if percent is None:
            print(f"  {name}: no coverage.xml found, skipping")
            continue
        svg = generate_svg(f"{name} coverage", percent)
        badge_path = BADGES_DIR / f"coverage-{name}.svg"
        badge_path.write_text(svg)
        print(f"  {name}: {percent}% -> {badge_path}")

    # Clean up intermediate coverage artifacts (badges are the final output)
    for xml_path in services.values():
        for artifact in [xml_path, xml_path.with_name(".coverage")]:
            artifact.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
