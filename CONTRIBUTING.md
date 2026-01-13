# Contributing to LitScout

Thank you for your interest in contributing to LitScout!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/LitScout.git`
3. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
4. Install dev dependencies: `pip install -e ".[dev]"`

## Development Workflow

1. Create a branch for your feature: `git checkout -b feature/my-feature`
2. Make your changes
3. Run tests: `pytest`
4. Commit with a clear message
5. Push and open a Pull Request

## Code Style

- Use Python 3.10+ features
- Follow PEP 8
- Keep functions small and focused
- Add docstrings for public functions

## Testing

Run tests with:
```bash
pytest
pytest --cov=litscout  # with coverage
```

## Adding New Sources

To add a new literature source:

1. Create `litscout/sources/your_source.py`
2. Implement a `fetch_your_source(query, topic, since, max_results)` function
3. Add it to `litscout/sources/__init__.py`
4. Add the source name to `VALID_SOURCES` in `litscout/config.py`
5. Add to `SOURCE_FETCHERS` in `litscout/__main__.py`

## Reporting Issues

Please include:
- Python version
- LitScout version (`litscout --version`)
- Steps to reproduce
- Expected vs actual behavior

## Questions?

Open an issue with the "question" label.
