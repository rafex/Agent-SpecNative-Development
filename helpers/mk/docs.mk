DOCS_HELPER ?= helpers/shell/docs.sh

.PHONY: docs serve

docs:
	bash "$(DOCS_HELPER)" --workspace "$(WORKSPACE)" --goal build --log-file "$(LOG_FILE)"

serve:
	bash "$(DOCS_HELPER)" --workspace "$(WORKSPACE)" --goal serve --log-file "$(LOG_FILE)"
