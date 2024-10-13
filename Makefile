run := poetry run

.PHONY: test
test:
	$(run) pytest tests/ $(ARGS)

.PHONY: test-coverage
test-coverage:
	$(run) pytest tests/ --cov-report term-missing --cov=podme_api $(ARGS)

.PHONY: coverage
coverage:
	$(run) coverage html

.PHONY: format
format:
	$(run) ruff format podme_api

.PHONY: format-check
format-check:
	$(run) ruff --check podme_api

.PHONY: docs
docs:
	cd docs && make html

.PHONY: setup
setup:
	poetry install

.PHONY: update
update:
	poetry update

.PHONY: repl
repl:
	$(run) python
