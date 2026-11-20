%{
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include "ast.hpp"
#include "driver.hpp"
#include "parser.tab.hpp"

#define YY_USER_ACTION \
    yylloc->first_line = yyextra->current_line; \
    yylloc->first_column = yyextra->current_column; \
    yyextra->current_column += yyleng; \
    yylloc->last_line = yyextra->current_line; \
    yylloc->last_column = yyextra->current_column;

static std::string unescape_string(const char* text, int len) {
    std::string res;
    // Strip outer quotes
    int start = (len >= 6 && text[0] == '"' && text[1] == '"' && text[2] == '"') ? 3 : 1;
    int end = (len >= 6 && text[0] == '"' && text[1] == '"' && text[2] == '"') ? len - 3 : len - 1;
    
    for (int i = start; i < end; ++i) {
        if (text[i] == '\\' && i + 1 < end) {
            char next = text[++i];
            switch (next) {
                case 'n': res += '\n'; break;
                case 't': res += '\t'; break;
                case 'r': res += '\r'; break;
                case '"': res += '"'; break;
                case '\\': res += '\\'; break;
                default: res += next; break;
            }
        } else {
            res += text[i];
        }
    }
    return res;
}

%}

%option noyywrap nounput noinput batch reentrant
%option bison-bridge bison-locations
%option extra-type="agentc::Driver*"

%x COMMENT_BLOCK

%%

[ \t\r]+            { /* skip whitespace */ }
\n                  { yyextra->current_line++; yyextra->current_column = 1; }

"//"[^\n]*          { /* single line comment */ }
"#"[^\n]*           { /* hash comment */ }

"/*"                { BEGIN(COMMENT_BLOCK); }
<COMMENT_BLOCK>"*/" { BEGIN(INITIAL); }
<COMMENT_BLOCK>\n   { yyextra->current_line++; yyextra->current_column = 1; }
<COMMENT_BLOCK><<EOF>> {
    yyextra->error({yyextra->current_line, yyextra->current_column}, "Unterminated comment block /* at EOF");
    return 0;
}
<COMMENT_BLOCK>.    { /* skip comment chars */ }

"module"            { return MODULE; }
"import"            { return IMPORT; }
"target"            { return TARGET; }
"contract"          { return CONTRACT; }
"agent"             { return AGENT; }
"implementation"    { return IMPLEMENTATION; }
"for"               { return FOR; }
"intent"            { return INTENT; }
"invariants"        { return INVARIANTS; }
"harness"           { return HARNESS; }
"lifecycle"         { return LIFECYCLE; }
"verify"            { return VERIFY; }
"benchmark"         { return BENCHMARK; }
"package"           { return PACKAGE; }
"deploy"            { return DEPLOY; }
"artifact"          { return ARTIFACT; }
"prd"               { return PRD; }
"adr"               { return ADR; }
"hld"               { return HLD; }
"lld"               { return LLD; }
"constraints"       { return CONSTRAINTS; }

"type"              { return TYPE; }
"struct"            { return STRUCT; }
"enum"              { return ENUM; }
"fn"                { return FN; }
"pre"               { return PRE; }
"post"              { return POST; }
"traces"            { return TRACES; }
"state"             { return STATE; }
"machine"           { return MACHINE; }
"initial"           { return INITIAL_KW; }
"transitions"       { return TRANSITIONS; }
"transition"        { return TRANSITION; }
"old"               { return OLD; }

"and"               { return AND; }
"or"                { return OR; }
"not"               { return NOT; }
"implies"           { return IMPLIES; }

"true"              { return TRUE_KW; }
"false"             { return FALSE_KW; }

"->"                { return ARROW; }
"::"                { return DOUBLE_COLON; }
"<="                { return LE; }
">="                { return GE; }
"=="                { return EQ; }
"!="                { return NE; }

"{"                 { return '{'; }
"}"                 { return '}'; }
"("                 { return '('; }
")"                 { return ')'; }
"["                 { return '['; }
"]"                 { return ']'; }
";"                 { return ';'; }
":"                 { return ':'; }
","                 { return ','; }
"."                 { return '.'; }
"="                 { return '='; }
"<"                 { return '<'; }
">"                 { return '>'; }
"+"                 { return '+'; }
"-"                 { return '-'; }
"*"                 { return '*'; }
"/"                 { return '/'; }
"%"                 { return '%'; }

\"\"\"([^\"\\]|\\.|(\"[^\"])|(\"\"[^\"]))*\"\"\" {
    yylval->sval = new std::string(unescape_string(yytext, yyleng));
    // update line count for multi-line string
    for (int i = 0; i < yyleng; ++i) {
        if (yytext[i] == '\n') {
            yyextra->current_line++;
            yyextra->current_column = 1;
        }
    }
    yylloc->last_line = yyextra->current_line;
    yylloc->last_column = yyextra->current_column;
    return STRING_LITERAL;
}

\"([^\"\\\n]|\\.)*\" {
    yylval->sval = new std::string(unescape_string(yytext, yyleng));
    return STRING_LITERAL;
}

[0-9]+(\.[0-9]+)?[a-zA-Z_]+ {
    std::string text(yytext);
    size_t pos = 0;
    while (pos < text.size() && (std::isdigit(text[pos]) || text[pos] == '.')) {
        pos++;
    }
    std::string suffix = text.substr(pos);
    if (suffix == "ns" || suffix == "us" || suffix == "ms" || suffix == "s" || suffix == "m" || suffix == "h") {
        yylval->sval = new std::string(text);
        return TIME_LITERAL;
    } else if (suffix == "B" || suffix == "KB" || suffix == "MB" || suffix == "GB" || suffix == "TB") {
        yylval->sval = new std::string(text);
        return BYTES_LITERAL;
    } else {
        std::string err = "Invalid dimensioned literal suffix: '" + suffix + "'";
        yyextra->error({yyextra->current_line, yyextra->current_column}, err);
        yylval->sval = new std::string(text);
        return NUMBER_LITERAL;
    }
}

[0-9]+(\.[0-9]+)?%? {
    yylval->sval = new std::string(yytext);
    return NUMBER_LITERAL;
}

[a-zA-Z_][a-zA-Z0-9_]* {
    yylval->sval = new std::string(yytext);
    return IDENTIFIER;
}

. {
    std::string err = "Unexpected character: '";
    err += yytext;
    err += "'";
    yyextra->error({yyextra->current_line, yyextra->current_column}, err);
}

%%
