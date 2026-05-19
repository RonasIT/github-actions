# ronasit/github-actions

Reusable GitHub workflow for PHP Laravel projects.

## Reusable tests workflow

Use `ronasit/github-actions/.github/workflows/tests.yml@main` from your project workflow.

### Default mode (without database)

```yaml
name: CI

on:
  push:
    branches: ["master"]
  pull_request:
    branches: ["master"]

jobs:
  tests:
    uses: ronasit/github-actions/.github/workflows/tests.yml@main
```

### Database mode (with PostgreSQL)

```yaml
jobs:
  tests:
    uses: ronasit/github-actions/.github/workflows/tests.yml@main
    with:
      use-database: true
```

In database mode the reusable workflow enables PostgreSQL service and DB variables internally.

### Additional composer package in matrix (optional)

You can add one more composer package axis to the matrix, for example `phpunit/phpunit`.
The workflow reads the package constraint from your `composer.json` `require` section,
detects the latest stable major series from Packagist, and runs the matrix across that range.

```yaml
jobs:
  tests:
    uses: ronasit/github-actions/.github/workflows/tests.yml@main
    with:
      additional-package: phpunit/phpunit
```

For `phpunit/phpunit: >=11.0`, the generated matrix will include package versions like `11.*`, `12.*`, `13.*`, etc.

### Custom matrix excludes (optional)

You can add extra exclusions on top of the built-in latest versions exclusion by passing `custom-exclude` as a JSON array.

```yaml
jobs:
  tests:
    uses: ronasit/github-actions/.github/workflows/tests.yml@main
    with:
      additional-package: phpunit/phpunit
      custom-exclude: '[{"php-version":"8.3","additional-package-version":"13.*"},{"laravel-version":"11.*","additional-package-version":"13.*"}]'
```

`custom-exclude` is merged with auto-exclude and duplicate exclude objects are removed.

### Custom PHPUnit commands (optional)

You can override test commands with:

- `phpunit-command`
- `phpunit-coverage-command`

```yaml
jobs:
  tests:
    uses: ronasit/github-actions/.github/workflows/tests.yml@main
    with:
      phpunit-command: vendor/bin/phpunit
      phpunit-coverage-command: vendor/bin/phpunit --coverage-clover build/logs/clover.xml
```
