SHELL := /bin/bash

.DEFAULT_GOAL := help

PYTHON_BOOTSTRAP ?= python3
UV ?= uv
VENV ?= .specnative/.venv
PYTHON ?= $(VENV)/bin/python
AGENT ?= $(VENV)/bin/asn
BIN_DIR ?=
WORKSPACE ?= $(CURDIR)
PROJECT_NAME ?= specnative-agent-pilot
LOG_FILE ?= /var/log/$(PROJECT_NAME)/log-make-$(shell date -u +%Y%m%dT%H%M%SZ).log

include helpers/mk/pilot.mk
include helpers/mk/docs.mk
