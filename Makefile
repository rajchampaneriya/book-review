ENGINE ?= $(shell command -v docker >/dev/null 2>&1 && echo docker || echo podman)
STACK ?= python
VARIANT ?= naive
FAULT ?= 0.05
RUN ?= 1
MINUTES ?= 5

.PHONY: doctor up down deploy unit arch contract bdd exp3 exp3-all summary chart observe-up observe-load mesh-up

doctor:
	bash infra/scripts/doctor.sh

up:
	bash infra/scripts/up.sh

observe-up:
	bash infra/scripts/observe-up.sh

# Every running stack unless STACK is set on the command line or in the
# environment; the default STACK=python above does not narrow it.
observe-load:
	STACK=$(if $(filter-out file,$(origin STACK)),$(STACK),) \
	MINUTES=$(MINUTES) .venv/bin/python -m harness.observe_load

mesh-up:
	bash infra/scripts/mesh-up.sh

down:
	bash infra/scripts/down.sh

deploy:
	bash infra/scripts/deploy.sh $(STACK)

unit:
	cd stacks/$(STACK) && $(ENGINE) build --target unit .

arch:
	python3 tools/arch/check_hexagonal.py $(STACK)
	cd stacks/$(STACK) && $(ENGINE) build --target arch .

contract:
	STACK=$(STACK) .venv/bin/python -m pytest -c contracts/pytest.ini contracts/tests

bdd:
	python3 tools/arch/check_hexagonal.py bdd
	.venv/bin/python -m pytest -p no:cacheprovider -q -W ignore::pytest.PytestUnknownMarkWarning bdd/steps

exp3:
	STACK=$(STACK) VARIANT=$(VARIANT) FAULT=$(FAULT) RUN=$(RUN) .venv/bin/python -m harness.exp3_run

exp3-all:
	.venv/bin/python -m harness.exp3_matrix

summary:
	.venv/bin/python -m harness.exp3_summary

chart:
	.venv/bin/python figures/exp3_duplicates.py
