PILOT_HELPER ?= helpers/shell/pilot.sh

.PHONY: help setup install build test compile check clean man

define run_pilot
	bash "$(PILOT_HELPER)" \
		--workspace "$(WORKSPACE)" \
		--project-name "$(PROJECT_NAME)" \
		--uv "$(UV)" \
		--python-bootstrap "$(PYTHON_BOOTSTRAP)" \
		--venv "$(VENV)" \
		--python "$(PYTHON)" \
		--agent "$(AGENT)" \
		--goal "$(1)" \
		--log-file "$(LOG_FILE)"
endef

help:
	@$(call run_pilot,help)

setup:
	@$(call run_pilot,setup)

install:
	@$(call run_pilot,install)

build:
	@$(call run_pilot,build)

test:
	@$(call run_pilot,test)

compile:
	@$(call run_pilot,compile)

check:
	@$(call run_pilot,check)

clean:
	@$(call run_pilot,clean)

man:
	@bash "$(PILOT_HELPER)" --workspace "$(WORKSPACE)" --man "$(TARGET)"
