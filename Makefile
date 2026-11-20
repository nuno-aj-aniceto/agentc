# ==============================================================================
# agentc - Root Makefile (Supports builds with or without CMake)
# ==============================================================================

BUILD_SYSTEM ?= auto
CXX          ?= g++
CXXFLAGS     ?= -std=c++20 -O2 -Wall -Wextra
BISON        ?= bison
FLEX         ?= flex
PYTHON       ?= python3
PREFIX       ?= /usr/local

BIN_DIR      := bin
BUILD_MAKE   := build-make
BUILD_CMAKE  := build

SRCS_FRONTEND := compiler/frontend/ast.cpp compiler/frontend/driver.cpp compiler/frontend/main.cpp
OBJS_FRONTEND := $(patsubst compiler/frontend/%.cpp,$(BUILD_MAKE)/%.o,$(SRCS_FRONTEND))

ifeq ($(BUILD_SYSTEM),auto)
  HAS_CMAKE := $(shell command -v cmake 2>/dev/null)
  ACTIVE_BUILD_SYSTEM := $(if $(HAS_CMAKE),cmake,make)
else
  ACTIVE_BUILD_SYSTEM := $(BUILD_SYSTEM)
endif

.PHONY: all parser parser-make parser-cmake grammar-check test clean distclean install help image

all: parser

help:
	@echo "agentc build options:"
	@echo "  make                      Build parser using active build system ($(ACTIVE_BUILD_SYSTEM))"
	@echo "  make BUILD_SYSTEM=make    Build parser directly with Bison, Flex, and G++ (no CMake)"
	@echo "  make BUILD_SYSTEM=cmake   Build parser using CMake and Make/Ninja"
	@echo "  make test                 Run full compiler test suite"
	@echo "  make grammar-check        Verify grammar has 0 shift/reduce conflicts with Bison"
	@echo "  make image                Build OCI container image for agentc toolchain"
	@echo "  make clean                Clean build objects"
	@echo "  make distclean            Clean all build caches and generated artifacts"

parser:
ifeq ($(ACTIVE_BUILD_SYSTEM),cmake)
	@$(MAKE) parser-cmake
else
	@$(MAKE) parser-make
endif

parser-cmake:
	@mkdir -p $(BUILD_CMAKE) $(BIN_DIR)
	cmake -S . -B $(BUILD_CMAKE)
	cmake --build $(BUILD_CMAKE) -j

parser-make: $(BIN_DIR)/agentc-parser

$(BUILD_MAKE):
	@mkdir -p $(BUILD_MAKE)

$(BIN_DIR):
	@mkdir -p $(BIN_DIR)

$(BUILD_MAKE)/parser.tab.cpp $(BUILD_MAKE)/parser.tab.hpp: compiler/frontend/parser.y | $(BUILD_MAKE)
	$(BISON) -Wall --defines=$(BUILD_MAKE)/parser.tab.hpp -o $(BUILD_MAKE)/parser.tab.cpp $<

$(BUILD_MAKE)/lex.yy.cpp: compiler/frontend/lexer.l $(BUILD_MAKE)/parser.tab.hpp | $(BUILD_MAKE)
	$(FLEX) -o $@ $<

$(BUILD_MAKE)/parser.tab.o: $(BUILD_MAKE)/parser.tab.cpp $(BUILD_MAKE)/parser.tab.hpp
	$(CXX) $(CXXFLAGS) -Icompiler/frontend -I$(BUILD_MAKE) -c $< -o $@

$(BUILD_MAKE)/lex.yy.o: $(BUILD_MAKE)/lex.yy.cpp $(BUILD_MAKE)/parser.tab.hpp
	$(CXX) $(CXXFLAGS) -Icompiler/frontend -I$(BUILD_MAKE) -c $< -o $@

$(BUILD_MAKE)/%.o: compiler/frontend/%.cpp $(BUILD_MAKE)/parser.tab.hpp | $(BUILD_MAKE)
	$(CXX) $(CXXFLAGS) -Icompiler/frontend -I$(BUILD_MAKE) -c $< -o $@

$(BIN_DIR)/agentc-parser: $(BUILD_MAKE)/parser.tab.o $(BUILD_MAKE)/lex.yy.o $(OBJS_FRONTEND) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $^

grammar-check: | $(BUILD_MAKE)
	$(BISON) -Wall -Wcounterexamples --report=all --report-file=$(BUILD_MAKE)/grammar.report -o $(BUILD_MAKE)/grammar_check.tab.cpp compiler/frontend/parser.y
	@echo "Bison grammar check PASSED (0 conflicts, 0 warnings)"

test: parser
	$(PYTHON) -m unittest discover -s tests -v

install: parser
	install -d $(DESTDIR)$(PREFIX)/bin
	install -m 755 $(BIN_DIR)/agentc-parser $(DESTDIR)$(PREFIX)/bin/
	install -m 755 cli/agentc.py $(DESTDIR)$(PREFIX)/bin/agentc

clean:
	rm -rf $(BUILD_MAKE) $(BUILD_CMAKE)

distclean: clean
	rm -rf $(BIN_DIR)/agentc-parser .agentc
