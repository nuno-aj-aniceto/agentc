#include <iostream>
#include <fstream>
#include <string>
#include "ast.hpp"
#include "driver.hpp"

void printUsage(const char* prog) {
    std::cout << "AgentLang Native Parser (agentc-parser) v1.0.0\n"
              << "Usage: " << prog << " [options] <source_file>\n\n"
              << "Options:\n"
              << "  -o <file>       Write JSON AST output to specified file\n"
              << "  --check         Perform syntax check only (exit 0 on success)\n"
              << "  -v, --version   Display version\n"
              << "  -h, --help      Display this help message\n";
}

int main(int argc, char** argv) {
    std::string input_file = "";
    std::string output_file = "";
    bool check_only = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            printUsage(argv[0]);
            return 0;
        } else if (arg == "-v" || arg == "--version") {
            std::cout << "agentc-parser v1.0.0 (Bison 3.8 / Flex 2.6 / C++20)\n";
            return 0;
        } else if (arg == "--check") {
            check_only = true;
        } else if (arg == "-o" && i + 1 < argc) {
            output_file = argv[++i];
        } else if (arg == "-" || arg[0] != '-') {
            input_file = arg;
        }
    }

    if (input_file.empty()) {
        std::cerr << "Error: No input file specified.\n";
        printUsage(argv[0]);
        return 1;
    }

    agentc::Driver driver;
    int res = driver.parse(input_file);
    if (res != 0) {
        std::cerr << "Compilation failed with " << driver.error_messages.size() << " syntax error(s).\n";
        return 1;
    }

    if (check_only) {
        std::cout << "Syntax check passed for " << input_file << ".\n";
        return 0;
    }

    std::string json_output = driver.ast.toJson();
    if (!output_file.empty()) {
        std::ofstream out(output_file);
        if (!out.is_open()) {
            std::cerr << "Error: Could not open output file: " << output_file << "\n";
            return 1;
        }
        out << json_output;
        out.close();
    } else {
        std::cout << json_output;
    }

    return 0;
}
