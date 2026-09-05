# Testing Guide

To run tests:
1. Ensure the Python environment is set up.
2. Run `pytest` from the root directory.

The test suite mocks out the MT5 terminal requirement so it can be run on CI/CD pipelines without a broker connection.
