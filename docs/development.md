# Development

If you want to develop on this action, you'll probably want to use a virtual environment. Feel free to arrange that in any way you want, but it could be as simple as running

```python
python3 -m venv .venv
```

Don't forget to activate the virtual environment next:

```bash
source .venv/bin/activate
```

To install the dependencies to work on the project, you can use `pip`:

```bash
pip install '.[dev]'
```

To run the test suite run:

```bash
pytest
```

## Test

Besides the test suite we run with `pytest` (see above) we run a more extensive set as part of quality control. See the run steps that are defined in
[this GitHub Workflow](../.github/workflows/python.yml) for details.
