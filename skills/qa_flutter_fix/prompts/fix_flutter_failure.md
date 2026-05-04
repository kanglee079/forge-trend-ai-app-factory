Fix this Flutter failure without destructive commands.

Failure:
{{qa_error}}

Rules:
- Change the smallest necessary set of files.
- Preserve app-specific content and tests.
- Do not remove features just to pass tests.
- Rerun analyze, tests, and debug APK after the fix when possible.
