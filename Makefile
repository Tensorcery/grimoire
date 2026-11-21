# What CI and a laptop run, under the same names: a change passes CI exactly
# when these pass here.

.DEFAULT_GOAL := help
.PHONY: help install lint test commits

UV := env -u VIRTUAL_ENV uv run

# A roast run keeps a whole copy of its target under .roast/: not ours to lint.
SCRIPTS = $(shell find . -name '*.sh' -not -path './.venv/*' -not -path '*/.roast/*')
WORKFLOWS = $(wildcard .github/workflows/*.yml)

help:     ## list the targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST)

install:  ## the tools and the git hooks: once after a clone
	uv sync
	$(UV) pre-commit install

lint:     ## the static checks: the CI lint job
	$(UV) yamllint --strict .
# shellcheck and actionlint fail on an empty list: each runs once it has a file.
ifneq ($(SCRIPTS),)
	$(UV) shellcheck --external-sources $(SCRIPTS)
endif
ifneq ($(WORKFLOWS),)
	$(UV) actionlint $(WORKFLOWS)
endif
# zizmor's online audits ask GitHub. The token is gh's own, fetched by the
# shell for zizmor alone and never printed.
	@echo '$(UV) zizmor .'
	@GH_TOKEN="$${GH_TOKEN:-$$(gh auth token 2> /dev/null)}" $(UV) zizmor .
# Not from inside a hook: pre-commit is what is running this.
ifndef PRE_COMMIT
	$(UV) pre-commit run --all-files --show-diff-on-failure
endif

test:     ## the plugins' own tests
	python3 plugins/roast/tests/test_roast.py

# RANGE is a git revision range; by default, what main does not have yet.
RANGE ?= origin/main..HEAD
commits:  ## the commit messages of RANGE, judged by cz.toml
	$(UV) cz check --rev-range '$(RANGE)'
