# Makefile for plexdo (plexdo)
#
# Common targets:
#   make install              install the package and the bash completion
#   make uninstall            remove both again
#   make develop              editable install with the dev extras
#   make check                lint, build, and validate the distribution
#
# Useful variables:
#   PREFIX=/usr/local         install completion system-wide instead of per-user
#   PIP_FLAGS=--user          extra flags forwarded to pip install
#   COMPLETION_DIR=<path>     override the completion destination outright
#   DESTDIR=<path>            staging root, for distribution packaging

PYTHON        ?= python3
PIP           ?= $(PYTHON) -m pip
PIP_FLAGS     ?=
PACKAGE       := plexdo
MAN_PAGE        := man/plexdo.1
BASH_COMPLETION := completions/plexdo.bash
ZSH_COMPLETION  := completions/_plexdo
FISH_COMPLETION := completions/plexdo.fish
PS_COMPLETION   := completions/plexdo.ps1

# Per-user by default; PREFIX switches to system-wide locations.
XDG_DATA_HOME   ?= $(HOME)/.local/share
XDG_CONFIG_HOME ?= $(HOME)/.config
ifeq ($(strip $(PREFIX)),)
MAN_DIR             ?= $(XDG_DATA_HOME)/man
COMPLETION_DIR      ?= $(XDG_DATA_HOME)/bash-completion/completions
ZSH_COMPLETION_DIR  ?= $(XDG_DATA_HOME)/zsh/site-functions
FISH_COMPLETION_DIR ?= $(XDG_CONFIG_HOME)/fish/completions
PS_COMPLETION_DIR   ?= $(XDG_DATA_HOME)/powershell/Completions
else
MAN_DIR             ?= $(PREFIX)/share/man
COMPLETION_DIR      ?= $(PREFIX)/share/bash-completion/completions
ZSH_COMPLETION_DIR  ?= $(PREFIX)/share/zsh/site-functions
FISH_COMPLETION_DIR ?= $(PREFIX)/share/fish/vendor_completions.d
PS_COMPLETION_DIR   ?= $(PREFIX)/share/powershell/Completions
endif

MAN_TARGET  := $(DESTDIR)$(MAN_DIR)/man1/plexdo.1
BASH_TARGET := $(DESTDIR)$(COMPLETION_DIR)/plexdo
ZSH_TARGET  := $(DESTDIR)$(ZSH_COMPLETION_DIR)/_plexdo
FISH_TARGET := $(DESTDIR)$(FISH_COMPLETION_DIR)/plexdo.fish
PS_TARGET   := $(DESTDIR)$(PS_COMPLETION_DIR)/plexdo.ps1

.PHONY: help install uninstall reinstall develop install-completion \
        uninstall-completion install-completion-bash install-completion-zsh \
        install-completion-fish install-completion-powershell install-man \
        uninstall-man check-version \
        smoke check-assets test \
        build check lint dist-check clean distclean

# ---------------------------------------------------------------------------

help:
	@echo "plexdo - available targets:"
	@echo ""
	@echo "  install               pip install the package + install completion"
	@echo "  uninstall             pip uninstall the package + remove completion"
	@echo "  reinstall             uninstall then install"
	@echo "  develop               editable install with dev extras (.[dev])"
	@echo "  install-man           install the man page only"
	@echo "  install-completion    install completions for bash, zsh, and fish"
	@echo "  uninstall-completion  remove all installed completion scripts"
	@echo "  build                 build the sdist and wheel into dist/"
	@echo "  test                  run the test suite"
	@echo "  lint                  run pylint over src/plexdo"
	@echo "  dist-check            twine check the built artifacts"
	@echo "  check                 lint + build + dist-check"
	@echo "  clean                 remove build artifacts and caches"
	@echo "  distclean             clean, and remove dist/ as well"
	@echo ""
	@echo "  bash completion:      $(BASH_TARGET)"
	@echo "  zsh completion:       $(ZSH_TARGET)"
	@echo "  fish completion:      $(FISH_TARGET)"
	@echo "  pwsh completion:      $(PS_TARGET)"
	@echo "  man page:             $(MAN_TARGET)"
	@echo ""
	@echo "Set SHELLS to limit which are installed, e.g. SHELLS=\"bash zsh\""

# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

install: install-completion install-man
	$(PIP) install $(PIP_FLAGS) .
	@echo ""
	@echo "Installed. Try: plexdo --help"
	@echo "Then:          plexdo write-config-example && plexdo login"

develop: install-completion install-man
	$(PIP) install $(PIP_FLAGS) -e ".[dev]"

uninstall: uninstall-completion uninstall-man
	-$(PIP) uninstall -y $(PACKAGE)

reinstall:
	$(MAKE) uninstall
	$(MAKE) install

install-man: $(MAN_PAGE)
	@install -d "$(DESTDIR)$(MAN_DIR)/man1"
	@install -m 644 "$(MAN_PAGE)" "$(MAN_TARGET)"
	@echo "Installed man page       -> $(MAN_TARGET)"

uninstall-man:
	@if [ -f "$(MAN_TARGET)" ]; then \
		rm -f "$(MAN_TARGET)"; \
		echo "Removed $(MAN_TARGET)"; \
	else \
		echo "Not installed: $(MAN_TARGET)"; \
	fi

# Which shells to install completions for; override to limit.
# powershell is opt-in: SHELLS="bash zsh fish powershell"
SHELLS ?= bash zsh fish

install-completion: $(addprefix install-completion-,$(SHELLS))

install-completion-bash: $(BASH_COMPLETION)
	@install -d "$(DESTDIR)$(COMPLETION_DIR)"
	@install -m 644 "$(BASH_COMPLETION)" "$(BASH_TARGET)"
	@echo "Installed bash completion -> $(BASH_TARGET)"

install-completion-zsh: $(ZSH_COMPLETION)
	@install -d "$(DESTDIR)$(ZSH_COMPLETION_DIR)"
	@install -m 644 "$(ZSH_COMPLETION)" "$(ZSH_TARGET)"
	@echo "Installed zsh completion  -> $(ZSH_TARGET)"
	@echo "  (ensure $(ZSH_COMPLETION_DIR) is in \$$fpath, then run: compinit)"

install-completion-fish: $(FISH_COMPLETION)
	@install -d "$(DESTDIR)$(FISH_COMPLETION_DIR)"
	@install -m 644 "$(FISH_COMPLETION)" "$(FISH_TARGET)"
	@echo "Installed fish completion -> $(FISH_TARGET)"

# PowerShell has no drop-in completion directory, so the file is installed and
# the user dot-sources it from their profile.
install-completion-powershell: $(PS_COMPLETION)
	@install -d "$(DESTDIR)$(PS_COMPLETION_DIR)"
	@install -m 644 "$(PS_COMPLETION)" "$(PS_TARGET)"
	@echo "Installed pwsh completion -> $(PS_TARGET)"
	@echo "  (add to your profile:  . $(PS_TARGET) )"

# Only ever removes the exact files this Makefile installs; never a directory.
uninstall-completion:
	@for target in "$(BASH_TARGET)" "$(ZSH_TARGET)" "$(FISH_TARGET)" "$(PS_TARGET)"; do \
		if [ -f "$$target" ]; then \
			rm -f "$$target"; \
			echo "Removed $$target"; \
		else \
			echo "Not installed: $$target"; \
		fi; \
	done

# ---------------------------------------------------------------------------
# Build / quality
# ---------------------------------------------------------------------------

build: clean
	$(PYTHON) -m build

lint:
	$(PYTHON) -m pylint src/$(PACKAGE)

dist-check:
	$(PYTHON) -m twine check dist/*

# The version appears in three places; drift is silent otherwise.
check-version:
	@v=$$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/$(PACKAGE)/__init__.py); \
	p=$$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1); \
	m=$$(sed -n 's/^\.TH .* "plexdo \([^"]*\)".*/\1/p' $(MAN_PAGE)); \
	if [ "$$v" = "$$p" ] && [ "$$v" = "$$m" ]; then \
		echo "version $$v consistent across __init__.py, pyproject.toml, and the man page"; \
	else \
		echo "version mismatch: __init__=$$v pyproject=$$p man=$$m" >&2; exit 1; \
	fi

# Import the package and build the full parser. pylint cannot catch a module
# that is valid Python but has lost its register()/COMMANDS tail, which is
# exactly the kind of edit that silently breaks every command.
smoke:
	@PYTHONPATH=src $(PYTHON) -c "\
from plexdo.cli import build_parser; \
from plexdo.commands import build_registry, MODULES; \
build_parser(); \
h, n = build_registry(); \
missing = [m.__name__ for m in MODULES if not hasattr(m, 'register') or not getattr(m, 'COMMANDS', None)]; \
assert not missing, 'modules missing register()/COMMANDS: %s' % missing; \
assert len(h) >= 25, 'only %d commands registered' % len(h); \
print('smoke: %d commands across %d modules' % (len(h), len(MODULES)))"

# The completions and man page are mirrored into the package as data files;
# editing the source copy and forgetting the mirror ships a stale asset in the
# wheel. Source is also required to be plain ASCII.
check-assets:
	@fail=0; \
	for f in plexdo.bash _plexdo plexdo.fish plexdo.ps1; do \
		cmp -s "completions/$$f" "src/$(PACKAGE)/data/$$f" || { \
			echo "stale mirror: src/$(PACKAGE)/data/$$f differs from completions/$$f" >&2; fail=1; }; \
	done; \
	cmp -s "$(MAN_PAGE)" "src/$(PACKAGE)/data/plexdo.1" || { \
		echo "stale mirror: src/$(PACKAGE)/data/plexdo.1 differs from $(MAN_PAGE)" >&2; fail=1; }; \
	for f in $$(find src completions man -type f ! -path "*egg-info*" ! -name "*.pyc") \
		         Makefile pyproject.toml; do \
		if LC_ALL=C grep -qP "[^\x00-\x7F]" "$$f" 2>/dev/null; then \
			echo "non-ASCII characters in $$f" >&2; fail=1; \
		fi; \
	done; \
	[ $$fail -eq 0 ] && echo "assets: mirrors in sync, source is plain ASCII"

test:
	@PYTHONPATH=src $(PYTHON) -m pytest

check: check-version check-assets smoke test lint build dist-check
	@echo ""
	@echo "All checks passed."

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean:
	rm -rf build/ src/*.egg-info/ .pytest_cache/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete

distclean: clean
	rm -rf dist/
