.PHONY: help fmt publish clean
help:	## Show this help.
	grep '^[^#[:space:]\.].*:' Makefile

fmt:	## Auto fix and format code.
	uv run ruff check --fix .
	uv run ruff format .

publish: clean	## Publish to PyPI.
	uv build
	uv publish

clean:
	rm -fr dist
