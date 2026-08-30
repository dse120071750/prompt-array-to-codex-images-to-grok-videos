# Contributing

Contributions are welcome.

Before opening a pull request:

1. Install `requirements.txt` and run `npm install`.
2. Validate the flow with M8M Harness Builder 2.0.
3. Run `python scripts/run_tests.py`.
4. Confirm that no run folders, credentials, transcripts, generated images, or
   videos are staged.

Keep the workflow on `flowstep_flow_v4`. Changes to output ports or schemas are
breaking changes and should include updated tests and documentation.
