cmake_minimum_required(VERSION 3.20)
project(AgentLangCompiler VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(BISON REQUIRED)
find_package(FLEX REQUIRED)

# Set build output directory for executables
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin)

# Generate Parser and Lexer
BISON_TARGET(AgentcParser
    ${CMAKE_CURRENT_SOURCE_DIR}/compiler/frontend/parser.y
    ${CMAKE_CURRENT_BINARY_DIR}/parser.tab.cpp
    DEFINES_FILE ${CMAKE_CURRENT_BINARY_DIR}/parser.tab.hpp
    COMPILE_FLAGS "-Wall"
)

FLEX_TARGET(AgentcLexer
    ${CMAKE_CURRENT_SOURCE_DIR}/compiler/frontend/lexer.l
    ${CMAKE_CURRENT_BINARY_DIR}/lex.yy.cpp
)

ADD_FLEX_BISON_DEPENDENCY(AgentcLexer AgentcParser)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/compiler/frontend
    ${CMAKE_CURRENT_BINARY_DIR}
)

add_executable(agentc-parser
    ${BISON_AgentcParser_OUTPUTS}
    ${FLEX_AgentcLexer_OUTPUTS}
    compiler/frontend/ast.cpp
    compiler/frontend/driver.cpp
    compiler/frontend/main.cpp
)

install(TARGETS agentc-parser DESTINATION bin)
