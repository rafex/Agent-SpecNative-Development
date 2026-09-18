SHELL := /bin/bash

.DEFAULT_GOAL := help

PYTHON_BOOTSTRAP ?= python3
VENV ?= .specnative/.venv
PYTHON ?= $(VENV)/bin/python
AGENT ?= $(VENV)/bin/specnative-agent
WORKSPACE ?= $(CURDIR)
PROJECT_NAME ?= specnative-agent-pilot
LOG_FILE ?= /var/log/$(PROJECT_NAME)/log-make-$(shell date -u +%Y%m%dT%H%M%SZ).log

include helpers/mk/pilot.mk
