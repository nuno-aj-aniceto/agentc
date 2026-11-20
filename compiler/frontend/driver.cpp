#include "ast.hpp"
#include "driver.hpp"
#include "parser.tab.hpp"

// Prototypes from generated flex scanner
int yylex_init_extra(agentc::Driver* user_defined, void** scanner);
int yylex_destroy(void* yyscanner);
typedef struct yy_buffer_state *YY_BUFFER_STATE;
YY_BUFFER_STATE yy_scan_string(const char *yy_str, void* yyscanner);
void yy_delete_buffer(YY_BUFFER_STATE b, void* yyscanner);
void yyset_in(FILE * _in_str, void* yyscanner);

namespace agentc {

void Driver::error(const SourceLocation& loc, const std::string& message) {
    has_error = true;
    if (error_messages.size() < 30) {
        std::string err = current_file + ":" + std::to_string(loc.line) + ":" + 
                          std::to_string(loc.column) + ": error: " + message;
        error_messages.push_back(err);
        std::cerr << err << std::endl;
    }
}

void Driver::error(const std::string& message) {
    error({current_line, current_column}, message);
}

void Driver::warning(const SourceLocation& loc, const std::string& message) {
    std::string warn = current_file + ":" + std::to_string(loc.line) + ":" + 
                       std::to_string(loc.column) + ": warning: " + message;
    warning_messages.push_back(warn);
    std::cerr << warn << std::endl;
}

int Driver::parse(const std::string& filename) {
    if (filename == "-") {
        std::string content((std::istreambuf_iterator<char>(std::cin)),
                            std::istreambuf_iterator<char>());
        return parseString(content, "<stdin>");
    }

    current_file = filename;
    current_line = 1;
    current_column = 1;
    has_error = false;
    error_messages.clear();
    warning_messages.clear();

    FILE* fp = fopen(filename.c_str(), "r");
    if (!fp) {
        error("Could not open file: " + filename);
        return 1;
    }

    if (yylex_init_extra(this, &scanner) != 0) {
        fclose(fp);
        error("Failed to initialize scanner");
        return 1;
    }

    yyset_in(fp, scanner);
    int res = yyparse(scanner, this);
    fclose(fp);
    yylex_destroy(scanner);
    scanner = nullptr;

    return (res == 0 && !has_error) ? 0 : 1;
}

int Driver::parseString(const std::string& input, const std::string& sourcename) {
    current_file = sourcename;
    current_line = 1;
    current_column = 1;
    has_error = false;
    error_messages.clear();
    warning_messages.clear();

    if (yylex_init_extra(this, &scanner) != 0) {
        error("Failed to initialize scanner");
        return 1;
    }

    YY_BUFFER_STATE buf = yy_scan_string(input.c_str(), scanner);
    int res = yyparse(scanner, this);
    yy_delete_buffer(buf, scanner);
    yylex_destroy(scanner);
    scanner = nullptr;

    return (res == 0 && !has_error) ? 0 : 1;
}

} // namespace agentc
