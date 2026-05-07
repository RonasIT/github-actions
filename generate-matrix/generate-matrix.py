#!/usr/bin/env python3
"""Generate CI matrix: minimum versions from composer.json and latest versions from public APIs."""

import json
import os
import re
import urllib.parse
import urllib.request


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


def fetch_php_versions(php_min):
    """Fetch all supported PHP major.minor versions >= php_min from php.net."""
    try:
        with urllib.request.urlopen("https://www.php.net/releases/?json", timeout=15) as response:
            payload = json.load(response)

        supported = payload["8"]["supported_versions"]
        return [v for v in supported if v >= php_min]
    except Exception:
        return [php_min]


def fetch_laravel_versions(laravel_min):
    """Fetch all stable Laravel major series from Packagist >= laravel_min major."""
    return fetch_composer_package_versions("laravel/framework", laravel_min)


def fetch_composer_package_versions(package_name, package_min):
    """Fetch all stable package major series from Packagist >= package_min major."""
    min_major = int(package_min.split(".")[0])

    try:
        package_path = urllib.parse.quote(package_name, safe="")
        with urllib.request.urlopen(f"https://repo.packagist.org/p2/{package_path}.json", timeout=20) as response:
            payload = json.load(response)

        min_major = int(package_min.split(".")[0])
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


def generate_matrix(php_versions, laravel_versions, additional_package_versions=None):
    """Generate cross-product matrix and exclude the latest combination for non-coverage job."""
    additional_package_versions = additional_package_versions or [""]

    matrix = {
        "php-version": php_versions,
        "laravel-version": laravel_versions,
        "additional-package-version": additional_package_versions,
    }

    if len(php_versions) * len(laravel_versions) * len(additional_package_versions) > 1:
        matrix["exclude"] = [
            {
                "php-version": php_versions[-1],
                "laravel-version": laravel_versions[-1],
                "additional-package-version": additional_package_versions[-1],
            }
        ]

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
    php_min, laravel_min, additional_package_min = parse_composer_json(additional_package)

    php_versions = fetch_php_versions(php_min)
    laravel_versions = fetch_laravel_versions(laravel_min)
    additional_package_versions = (
        fetch_composer_package_versions(additional_package, additional_package_min)
        if additional_package
        else [""]
    )

    matrix = generate_matrix(php_versions, laravel_versions, additional_package_versions)
    result = {
        "matrix": matrix,
        "php-latest": php_versions[-1],
        "laravel-latest": laravel_versions[-1],
        "additional-package-latest": additional_package_versions[-1],
    }

    write_github_outputs(result)
    print(json.dumps(result))
