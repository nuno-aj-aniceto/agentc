#pragma once

#include "ast.hpp"
#include <string>
#include <vector>
#include <iostream>

namespace agentc {

class Driver {
public:
    Driver() = default;

    int parse(const std::string& filename);
    int parseString(const std::string& input, const std::string& sourcename = "stdin");

    void error(const SourceLocation& loc, const std::string& message);
    void error(const std::string& message);
    void warning(const SourceLocation& loc, const std::string& message);

    ModuleAST ast;
    bool has_error = false;
    std::vector<std::string> error_messages;
    std::vector<std::string> warning_messages;
    std::string current_file = "stdin";
    int current_line = 1;
    int current_column = 1;

    void* scanner = nullptr;
};

} // namespace agentc
