"""
vcpkg-to-apt: generate a Dockerfile that installs, via apt, the equivalents
of the dependencies declared in a vcpkg.json manifest — so you don't have
to rebuild everything through vcpkg on every Docker build.

Usage:
    python generate.py --input vcpkg.json --output Dockerfile [--binary-name my_app]
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = Path(__file__).resolve().parent


def load_mappings(mapping_path: Path) -> dict:
    with open(mapping_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def load_vcpkg_dependencies(vcpkg_json_path: Path) -> list[str]:
    with open(vcpkg_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    deps = data.get("dependencies", [])
    normalized = []
    for dep in deps:
        # Dependencies can be plain strings or objects like
        # {"name": "curl", "features": [...]}
        if isinstance(dep, str):
            normalized.append(dep)
        elif isinstance(dep, dict) and "name" in dep:
            normalized.append(dep["name"])
        else:
            print(f"Skipping dependency with unrecognized format: {dep}", file=sys.stderr)
    return normalized


def resolve_apt_packages(vcpkg_deps: list[str], mappings: dict) -> tuple[list[str], list[str]]:
    """Returns (apt_packages, unmapped_ports)."""
    apt_packages = []
    unmapped = []
    port_map = mappings.get("mappings", {})

    for dep in vcpkg_deps:
        entry = port_map.get(dep)
        if entry is None:
            unmapped.append(dep)
            continue
        apt_packages.extend(entry.get("apt", []))

    # De-duplicate while preserving order
    seen = set()
    deduped = []
    for pkg in apt_packages:
        if pkg not in seen:
            seen.add(pkg)
            deduped.append(pkg)

    return deduped, unmapped


def generate_dockerfile(
    base_packages: list[str],
    apt_packages: list[str],
    source_file: str,
    binary_name: str,
    output_path: Path,
    template_dir: Path,
):
    env = Environment(loader=FileSystemLoader(str(template_dir)), keep_trailing_newline=True)
    template = env.get_template("Dockerfile.j2")
    rendered = template.render(
        base_packages=base_packages,
        apt_packages=apt_packages,
        source_file=source_file,
        binary_name=binary_name,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)


def main():
    parser = argparse.ArgumentParser(
        description="Generate an apt-based Dockerfile from a vcpkg.json manifest"
    )
    parser.add_argument("--input", required=True, help="Path to vcpkg.json")
    parser.add_argument("--output", default="Dockerfile", help="Path of the generated Dockerfile")
    parser.add_argument(
        "--mapping",
        default=str(SCRIPT_DIR / "mappings.yaml"),
        help="Path to the mappings.yaml file",
    )
    parser.add_argument(
        "--template-dir",
        default=str(SCRIPT_DIR / "templates"),
        help="Directory containing Dockerfile.j2",
    )
    parser.add_argument(
        "--binary-name",
        default="app",
        help="Name of the final binary (used in the Dockerfile's CMD)",
    )
    args = parser.parse_args()

    vcpkg_json_path = Path(args.input)
    mapping_path = Path(args.mapping)
    output_path = Path(args.output)
    template_dir = Path(args.template_dir)

    if not vcpkg_json_path.exists():
        print(f"File not found: {vcpkg_json_path}", file=sys.stderr)
        sys.exit(1)

    mappings = load_mappings(mapping_path)
    vcpkg_deps = load_vcpkg_dependencies(vcpkg_json_path)

    print(f"Dependencies found in {vcpkg_json_path.name}: {', '.join(vcpkg_deps)}")

    apt_packages, unmapped = resolve_apt_packages(vcpkg_deps, mappings)

    if unmapped:
        print(
            f"\n{len(unmapped)} port(s) have no known apt mapping — "
            f"add them manually to {mapping_path.name}:",
            file=sys.stderr,
        )
        for port in unmapped:
            print(f"   - {port}", file=sys.stderr)
        print()

    base_packages = mappings.get("base_packages", [])

    generate_dockerfile(
        base_packages=base_packages,
        apt_packages=apt_packages,
        source_file=str(vcpkg_json_path),
        binary_name=args.binary_name,
        output_path=output_path,
        template_dir=template_dir,
    )

    print(f"Dockerfile generated: {output_path}")
    print(f"   apt packages added: {', '.join(apt_packages) if apt_packages else '(none)'}")


if __name__ == "__main__":
    main()
