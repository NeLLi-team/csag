# Release process

Tag only a committed working tree on which every local check has passed.

## Local checks

1. Confirm that the working tree is clean. The command prints nothing when it
   is:

    ```bash
    git status --porcelain --untracked-files=all
    ```

2. Run the local checks:

    ```bash
    uv sync --extra local-pdf
    uv build
    uv run python scripts/check_release_metadata.py
    uv run python scripts/generate_schema_artifacts.py
    uv run python scripts/check_schema_artifacts.py
    uv run python scripts/check_controlled_vocabularies.py
    uv run python scripts/check_cli_docs.py
    uv run python scripts/check_ocr_api_job_contract.py
    uv run python scripts/check_validation_profile_reports.py
    uv run python scripts/verify_prior_art_manifest.py examples/prior-art/candidate_manifest.json
    uv run csag quickstart --output-dir /tmp/csag-quickstart
    uv run csag check-examples --examples-dir examples \
      --report-out /tmp/check-examples.json \
      --coverage-out /tmp/check-examples.coverage.json
    uv run python scripts/collect_example_metrics.py --examples-dir examples --report-out examples/coverage_metrics.json
    uv run python scripts/check_example_metrics.py
    uv run python scripts/check_benchmark_report.py
    ```

    `scripts/check_release_metadata.py` confirms that `pyproject.toml`,
    `CITATION.cff`, `.zenodo.json`, the validator, the scaffold, the
    extraction skill, and the schema `skills/csag-extraction/assets/csag.yaml`
    carry the same version, that `README.md` and `CHANGELOG.md` mention it,
    and whether an archive DOI is recorded. A DOI is optional.

3. Check the OCR (optical character recognition) conversion path if you have
   access to an OCR service. `csag doctor` reports whether the PDF is
   readable, an API key is set, and the service answers; with `--strict` it
   exits non-zero unless all three hold. The OCR API reads its key from
   `OCR_API_KEY` or `NELLI_API_KEY`; the NeLLi service at
   https://api.newlineages.com/ocr accepts `NELLI_API_KEY`.

    ```bash
    uv run csag doctor --pdf examples/jamy2026/s41467-025-67401-4.pdf --strict
    ```

## Tag and release

1. Commit the release changes. Review the list of modified files, then stage
   and commit them:

    ```bash
    git status --short
    git add -u
    git commit -m "chore(release): v1.0.0"
    ```

2. Create an annotated tag on the release commit and push it with `main`:

    ```bash
    git tag -a v1.0.0 -m "CSAG v1.0.0"
    git push origin main v1.0.0
    ```

3. Create the GitHub release from the tag and upload the built distribution
   files:

    ```bash
    uv build
    gh release create v1.0.0 --verify-tag --title "CSAG v1.0.0" \
      --notes "See CHANGELOG.md for the release notes."
    gh release upload v1.0.0 \
      dist/csag-1.0.0.tar.gz \
      dist/csag-1.0.0-py3-none-any.whl \
      --clobber
    ```

    Confirm that the release lists both `csag-1.0.0.tar.gz` and
    `csag-1.0.0-py3-none-any.whl`.

## Archive

If you archive the release through Zenodo or an equivalent service, record
the assigned DOI in the release metadata and in the GitHub release notes, then
rerun the metadata check:

```bash
uv run python scripts/record_archive_doi.py \
  10.5281/zenodo.<record> \
  --update-github-release
uv run python scripts/check_release_metadata.py
```

The script replaces `pending-zenodo-doi` in `CITATION.cff` and
`.zenodo.json`.
