#!/usr/bin/env python3

import json
import os
import re
import urllib.request

from php_versions import PHP_VERSIONS


def parse_custom_exclude(raw_custom_exclude):
    """Parse custom exclude JSON from workflow input."""
    if not raw_custom_exclude or not raw_custom_exclude.strip():
        return []

    try:
        custom_exclude = json.loads(raw_custom_exclude)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid CUSTOM_EXCLUDE JSON: {error}") from error

    if not isinstance(custom_exclude, list):
        raise ValueError("CUSTOM_EXCLUDE must be a JSON array of exclude objects")

    for item in custom_exclude:
        if not isinstance(item, dict):
            raise ValueError("Each item in CUSTOM_EXCLUDE must be an object")

    return custom_exclude


def parse_composer_json(additional_package=""):
    """Extract minimal PHP, Laravel and optional package versions from composer.json requirements."""
    workspace = os.getenv("GITHUB_WORKSPACE", ".")
    composer_path = os.path.join(workspace, "composer.json")

    with open(composer_path, "r", encoding="utf-8") as file:
        composer = json.load(file)

    php_constraint = composer.get("require", {}).get("php", ">=8.0")
    laravel_constraint = composer.get("require", {}).get("laravel/framework", ">=10.0")

    php_min = extract_min_version(php_constraint, default="8.0")
    laravel_min = extract_min_version(laravel_constraint, default="10.0")
    additional_package_min = ""

    if additional_package:
        additional_package_constraint = composer.get("require", {})[additional_package]
        additional_package_min = extract_min_version(additional_package_constraint, default="0.0")

    return php_min, laravel_min, additional_package_min


def extract_min_version(requirement, default):
    """Extract minimal major.minor and normalize constraints like >=12 to 12.0."""
    match = re.search(r"(\d+)(?:\.(\d+))?", requirement)
    if not match:
        return default

    major = match.group(1)
    minor = match.group(2) or "0"
    return f"{major}.{minor}"


def parse_major_minor(version):
    """Convert version string into a comparable (major, minor) tuple."""
    match = re.match(r"^(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Invalid major.minor version: {version}")

    return int(match.group(1)), int(match.group(2))


def fetch_composer_package_versions(package_name, package_min):
    """Fetch all stable package major series from Packagist >= package_min major."""
    min_major = int(package_min.split(".")[0])

    try:
        with urllib.request.urlopen(f"https://repo.packagist.org/p2/{package_name}.json", timeout=20) as response:
            payload = json.load(response)

        latest_major = None

        for release in payload["packages"][package_name]:
            version = release.get("version", "")
            match = re.match(r"^v?(\d+)\.\d+\.\d+$", version)
            if match:
                latest_major = int(match.group(1))
                break

        if latest_major is None or latest_major < min_major:
            return [f"{min_major}.*"]

        return [f"{major}.*" for major in range(min_major, latest_major + 1)]
    except Exception:
        return [f"{min_major}.*"]


def merge_excludes(auto_exclude, custom_exclude):
    """Merge auto and custom excludes while removing duplicates."""
    merged = []
    seen = set()

    for item in auto_exclude + custom_exclude:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue

        seen.add(key)
        merged.append(item)

    return merged


def generate_matrix(php_versions, laravel_versions, additional_package_versions=None, custom_exclude=None):
    """Generate cross-product matrix and exclude the latest combination for non-coverage job."""
    additional_package_versions = additional_package_versions or [""]
    custom_exclude = custom_exclude or []

    matrix = {
        "php-version": php_versions,
        "laravel-version": laravel_versions,
        "additional-package-version": additional_package_versions,
    }

    auto_exclude = []

    if len(php_versions) * len(laravel_versions) * len(additional_package_versions) > 1:
        auto_exclude = [
            {
                "php-version": php_versions[-1],
                "laravel-version": laravel_versions[-1],
                "additional-package-version": additional_package_versions[-1],
            }
        ]

    excludes = merge_excludes(auto_exclude, custom_exclude)
    if excludes:
        matrix["exclude"] = excludes

    return matrix


def write_github_outputs(result):
    """Write GitHub Actions step outputs when GITHUB_OUTPUT is available."""
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return

    with open(github_output, "a", encoding="utf-8") as file:
        file.write(f"matrix={json.dumps(result['matrix'])}\n")
        file.write(f"php-latest={result['php-latest']}\n")
        file.write(f"laravel-latest={result['laravel-latest']}\n")
        file.write(f"additional-package-latest={result['additional-package-latest']}\n")


if __name__ == "__main__":
    additional_package = os.getenv("ADDITIONAL_PACKAGE", "").strip()
    custom_exclude = parse_custom_exclude(os.getenv("CUSTOM_EXCLUDE", ""))
    php_min, laravel_min, additional_package_min = parse_composer_json(additional_package)

    php_versions = [
        version
        for version in PHP_VERSIONS
        if parse_major_minor(version) >= parse_major_minor(php_min)
    ]
    if not php_versions:
        php_versions = [php_min]

    laravel_versions = fetch_composer_package_versions("laravel/framework", laravel_min)

    additional_package_versions = (
        fetch_composer_package_versions(additional_package, additional_package_min)
        if additional_package
        else [""]
    )

    matrix = generate_matrix(php_versions, laravel_versions, additional_package_versions, custom_exclude)
    result = {
        "matrix": matrix,
        "php-latest": php_versions[-1],
        "laravel-latest": laravel_versions[-1],
        "additional-package-latest": additional_package_versions[-1],
    }

    write_github_outputs(result)
    print(json.dumps(result))
