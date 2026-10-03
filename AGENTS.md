# Pointer development

- The user requested `DEV` as the development branch. Make and push subsequent changes to `DEV`; do not merge into `main` or create release tags without a request to publish.
- Run `python -m unittest discover -s tests` and packaged `--diagnose` before claiming a Windows build is ready.
- Preserve the original cursor backup. Reapplying or upgrading must not delete and recreate an unchanged startup entry.
- Keep private machine data in ignored `.local/`; generated CUR/ANI theme assets belong in `assets/cursors/`.
