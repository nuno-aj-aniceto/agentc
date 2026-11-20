%code requires {
#include <string>
#include <vector>
#include <map>
#include <utility>
#include <memory>

#include "ast.hpp"

#ifndef YY_TYPEDEF_YY_SCANNER_T
#define YY_TYPEDEF_YY_SCANNER_T
typedef void* yyscan_t;
#endif

namespace agentc {
    class Driver;
    struct FnContract {
        std::vector<Condition> preconditions;
        std::vector<Condition> postconditions;
        std::vector<std::string> traces;
        bool has_transition = false;
        TransitionDef transition;
    };
    struct ExprNode {
        std::string text;
        std::shared_ptr<Expr> expr;
    };
}
}

%code {
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>

#include "driver.hpp"

int yylex(YYSTYPE* yylval_param, YYLTYPE* yylloc_param, yyscan_t yyscanner);
void yyerror(YYLTYPE* loc, yyscan_t scanner, agentc::Driver* driver, const char* msg);
}

%define api.pure full
%locations
%define parse.error detailed
%lex-param   { yyscan_t scanner }
%parse-param { yyscan_t scanner } { agentc::Driver* driver }

%union {
    std::string* sval;
    std::vector<std::string>* svec;
    std::map<std::string, std::string>* smap;
    std::pair<std::string, std::string>* spair;
    agentc::Field* field;
    std::vector<agentc::Field>* field_vec;
    agentc::FunctionDecl* func_decl;
    agentc::TypeDecl* type_decl;
    agentc::FnContract* fn_contract;
    agentc::ExprNode* expr_node;
    std::vector<agentc::ExprPtr>* expr_vec;
    agentc::StateMachineAST* state_machine;
    agentc::TransitionDef* transition_def;
    std::vector<agentc::TransitionDef>* transition_vec;
}

%destructor { delete $$; } <sval>
%destructor { delete $$; } <svec>
%destructor { delete $$; } <smap>
%destructor { delete $$; } <spair>
%destructor { delete $$; } <field>
%destructor { delete $$; } <field_vec>
%destructor { delete $$; } <func_decl>
%destructor { delete $$; } <type_decl>
%destructor { delete $$; } <fn_contract>
%destructor { delete $$; } <expr_node>
%destructor { delete $$; } <expr_vec>
%destructor { delete $$; } <state_machine>
%destructor { delete $$; } <transition_def>
%destructor { delete $$; } <transition_vec>

/* Keywords */
%token MODULE IMPORT TARGET CONTRACT AGENT IMPLEMENTATION FOR
%token INTENT INVARIANTS HARNESS LIFECYCLE VERIFY BENCHMARK PACKAGE DEPLOY
%token ARTIFACT PRD ADR HLD LLD CONSTRAINTS
%token TYPE STRUCT ENUM FN PRE POST
%token TRACES STATE MACHINE INITIAL_KW TRANSITIONS TRANSITION OLD
%token AND OR NOT IMPLIES
%token TRUE_KW FALSE_KW

/* Delimiters & Operators */
%token ARROW DOUBLE_COLON LE GE EQ NE

/* Tokens with values */
%token <sval> IDENTIFIER STRING_LITERAL NUMBER_LITERAL TIME_LITERAL BYTES_LITERAL

/* Non-terminal types */
%type <sval> qualified_id type_ref type_ref_list option_value any_identifier artifact_kind trace_item trace_ident trace_part
%type <svec> string_list identifier_list trace_list trace_items trace_item_list
%type <smap> key_value_block
%type <spair> key_value_entry
%type <field> struct_field param
%type <field_vec> struct_fields param_list params
%type <type_decl> type_decl
%type <func_decl> fn_decl
%type <fn_contract> fn_body fn_clauses
%type <svec> enum_variants enum_variant_list
%type <expr_node> expr_atom expr primary_expr condition_expr
%type <expr_vec> call_args
%type <state_machine> state_machine_decl state_machine_body
%type <transition_def> transition_entry
%type <transition_vec> transition_list transition_items

/* Precedence rules */
%right IMPLIES
%left OR
%left AND
%precedence NOT
%nonassoc '<' '>' LE GE EQ NE
%left '+' '-'
%left '*' '/' '%'
%precedence UMINUS

%start program

%%

program:
    module_decl declarations
    ;

module_decl:
    MODULE qualified_id ';' {
        driver->ast.module_name = *$2;
        delete $2;
    }
    ;

declarations:
    %empty
    | declarations declaration
    ;

declaration:
    import_decl
    | target_decl
    | artifact_decl
    | contract_decl
    | agent_impl_decl
    | lifecycle_decl
    | error ';' { yyerrok; }
    | error '}' { yyerrok; }
    ;

/* Import declarations */
import_decl:
    IMPORT qualified_id ';' {
        driver->ast.imports.push_back(*$2);
        delete $2;
    }
    ;

/* Target declaration */
target_decl:
    TARGET IDENTIFIER '{' {
        agentc::TargetDecl t;
        t.target_name = *$2;
        t.loc = {@1.first_line, @1.first_column};
        driver->ast.targets.push_back(t);
        delete $2;
        $2 = nullptr;
    } target_body '}'
    ;

target_body:
    %empty
    | target_body target_option
    ;

target_option:
    any_identifier ':' option_value ';' {
        if (!driver->ast.targets.empty()) {
            auto& opts = driver->ast.targets.back().options;
            if (opts.count(*$1)) {
                driver->warning({@1.first_line, @1.first_column}, "Duplicate target option '" + *$1 + "' (overwriting previous value)");
            }
            opts[*$1] = *$3;
        }
        delete $1; delete $3;
    }
    ;

/* Artifact declaration (PRD / ADR / HLD / LLD) */
artifact_decl:
    ARTIFACT artifact_kind STRING_LITERAL '{' {
        agentc::ArtifactLineageDecl a;
        a.artifact_type = *$2;
        a.identifier = *$3;
        a.loc = {@1.first_line, @1.first_column};
        driver->ast.artifacts.push_back(a);
        delete $2; $2 = nullptr;
        delete $3; $3 = nullptr;
    } artifact_body '}'
    ;

artifact_kind:
    PRD { $$ = new std::string("prd"); }
    | ADR { $$ = new std::string("adr"); }
    | HLD { $$ = new std::string("hld"); }
    | LLD { $$ = new std::string("lld"); }
    | IDENTIFIER { $$ = $1; }
    ;

artifact_body:
    %empty
    | artifact_body artifact_member
    ;

artifact_member:
    any_identifier ':' option_value ';' {
        if (!driver->ast.artifacts.empty()) {
            auto& meta = driver->ast.artifacts.back().metadata;
            if (meta.count(*$1)) {
                driver->warning({@1.first_line, @1.first_column}, "Duplicate artifact metadata '" + *$1 + "' (overwriting previous value)");
            }
            meta[*$1] = *$3;
        }
        delete $1; delete $3;
    }
    | CONSTRAINTS ':' '[' string_list ']' ';' {
        if (!driver->ast.artifacts.empty() && $4) {
            driver->ast.artifacts.back().constraints = *$4;
            delete $4;
        }
    }
    ;

option_value:
    STRING_LITERAL { $$ = $1; }
    | any_identifier { $$ = $1; }
    | NUMBER_LITERAL { $$ = $1; }
    | TIME_LITERAL { $$ = $1; }
    | BYTES_LITERAL { $$ = $1; }
    | TRUE_KW { $$ = new std::string("true"); }
    | FALSE_KW { $$ = new std::string("false"); }
    ;

/* Contract declaration */
contract_decl:
    CONTRACT IDENTIFIER '{' {
        agentc::ContractDecl c;
        c.name = *$2;
        c.loc = {@1.first_line, @1.first_column};
        driver->ast.contracts.push_back(c);
        delete $2;
        $2 = nullptr;
    } contract_body '}'
    ;

contract_body:
    %empty
    | contract_body contract_member
    ;

contract_member:
    type_decl {
        if (!driver->ast.contracts.empty()) {
            driver->ast.contracts.back().types.push_back(*$1);
        }
        delete $1;
    }
    | fn_decl {
        if (!driver->ast.contracts.empty()) {
            driver->ast.contracts.back().functions.push_back(*$1);
        }
        delete $1;
    }
    | state_machine_decl {
        if (!driver->ast.contracts.empty() && $1) {
            driver->ast.contracts.back().state_machines.push_back(*$1);
        }
        delete $1;
    }
    | TRACES ':' trace_list ';' {
        if (!driver->ast.contracts.empty() && $3) {
            for (const auto& tr : *$3) {
                driver->ast.contracts.back().traces.push_back(tr);
            }
            delete $3;
        }
    }
    | error ';' { yyerrok; }
    | error '}' { yyerrok; }
    ;

trace_list:
    '[' trace_items ']' { $$ = $2; }
    ;

trace_items:
    %empty { $$ = new std::vector<std::string>(); }
    | trace_item_list { $$ = $1; }
    ;

trace_item_list:
    trace_item {
        $$ = new std::vector<std::string>{*$1};
        delete $1;
    }
    | trace_item_list ',' trace_item {
        $$ = $1;
        $$->push_back(*$3);
        delete $3;
    }
    | trace_item_list ',' {
        $$ = $1;
    }
    ;

trace_item:
    STRING_LITERAL { $$ = $1; }
    | trace_ident { $$ = $1; }
    ;

trace_ident:
    trace_part { $$ = $1; }
    | trace_ident '.' trace_part {
        $$ = new std::string(*$1 + "." + *$3);
        delete $1; delete $3;
    }
    | trace_ident '-' trace_part {
        $$ = new std::string(*$1 + "-" + *$3);
        delete $1; delete $3;
    }
    ;

trace_part:
    any_identifier { $$ = $1; }
    | NUMBER_LITERAL { $$ = $1; }
    ;

state_machine_decl:
    STATE MACHINE IDENTIFIER '{' state_machine_body '}' optional_semicolon {
        $$ = $5;
        $$->name = *$3;
        $$->loc = {@1.first_line, @1.first_column};
        delete $3;
    }
    | STATE IDENTIFIER '{' state_machine_body '}' optional_semicolon {
        $$ = $4;
        $$->name = *$2;
        $$->loc = {@1.first_line, @1.first_column};
        delete $2;
    }
    ;

state_machine_body:
    %empty {
        $$ = new agentc::StateMachineAST();
    }
    | state_machine_body INITIAL_KW ':' any_identifier ';' {
        $$ = $1;
        $$->initial_state = *$4;
        delete $4;
    }
    | state_machine_body TRANSITIONS ':' '[' transition_list ']' ';' {
        $$ = $1;
        if ($5) {
            for (const auto& t : *$5) {
                $$->transitions.push_back(t);
            }
            delete $5;
        }
    }
    | state_machine_body error ';' {
        $$ = $1;
        yyerrok;
    }
    ;

transition_list:
    %empty { $$ = new std::vector<agentc::TransitionDef>(); }
    | transition_items { $$ = $1; }
    ;

transition_items:
    transition_entry {
        $$ = new std::vector<agentc::TransitionDef>{*$1};
        delete $1;
    }
    | transition_items ',' transition_entry {
        $$ = $1;
        $$->push_back(*$3);
        delete $3;
    }
    | transition_items ',' {
        $$ = $1;
    }
    ;

transition_entry:
    any_identifier ARROW any_identifier {
        $$ = new agentc::TransitionDef{*$1, *$3, {@1.first_line, @1.first_column}};
        delete $1; delete $3;
    }
    ;

/* Type declarations */
type_decl:
    TYPE IDENTIFIER '=' type_ref ';' {
        $$ = new agentc::TypeDecl();
        $$->kind = "alias";
        $$->name = *$2;
        $$->alias_target = *$4;
        $$->loc = {@1.first_line, @1.first_column};
        delete $2; delete $4;
    }
    | STRUCT IDENTIFIER '{' struct_fields '}' optional_semicolon {
        $$ = new agentc::TypeDecl();
        $$->kind = "struct";
        $$->name = *$2;
        $$->loc = {@1.first_line, @1.first_column};
        if ($4) {
            $$->fields = *$4;
            delete $4;
        }
        delete $2;
    }
    | ENUM IDENTIFIER '{' enum_variants '}' optional_semicolon {
        $$ = new agentc::TypeDecl();
        $$->kind = "enum";
        $$->name = *$2;
        $$->loc = {@1.first_line, @1.first_column};
        if ($4) {
            $$->enum_variants = *$4;
            delete $4;
        }
        delete $2;
    }
    ;

optional_semicolon:
    %empty
    | ';'
    ;

struct_fields:
    %empty { $$ = new std::vector<agentc::Field>(); }
    | struct_fields struct_field {
        $$ = $1;
        if ($2) {
            $$->push_back(*$2);
            delete $2;
        }
    }
    ;

struct_field:
    any_identifier ':' type_ref ';' {
        $$ = new agentc::Field{*$1, *$3, {@1.first_line, @1.first_column}};
        delete $1; delete $3;
    }
    | any_identifier ':' type_ref ',' {
        $$ = new agentc::Field{*$1, *$3, {@1.first_line, @1.first_column}};
        delete $1; delete $3;
    }
    ;

enum_variants:
    %empty { $$ = new std::vector<std::string>(); }
    | enum_variant_list { $$ = $1; }
    ;

enum_variant_list:
    IDENTIFIER {
        $$ = new std::vector<std::string>{*$1};
        delete $1;
    }
    | enum_variant_list ',' IDENTIFIER {
        $$ = $1;
        $$->push_back(*$3);
        delete $3;
    }
    | enum_variant_list ',' {
        $$ = $1;
    }
    ;

/* Function declarations */
fn_decl:
    FN IDENTIFIER '(' param_list ')' ARROW type_ref fn_body {
        $$ = new agentc::FunctionDecl();
        $$->name = *$2;
        $$->return_type = *$7;
        $$->loc = {@1.first_line, @1.first_column};
        if ($4) {
            $$->parameters = *$4;
            delete $4;
        }
        if ($8) {
            $$->traces = $8->traces;
            $$->has_transition = $8->has_transition;
            $$->transition = $8->transition;
            for (const auto& cond : $8->preconditions) {
                $$->preconditions.push_back(cond.text);
                $$->preconditions_ast.push_back(cond.expr);
            }
            for (const auto& cond : $8->postconditions) {
                $$->postconditions.push_back(cond.text);
                $$->postconditions_ast.push_back(cond.expr);
            }
            delete $8;
        }
        delete $2; delete $7;
    }
    | FN IDENTIFIER '(' param_list ')' fn_body {
        $$ = new agentc::FunctionDecl();
        $$->name = *$2;
        $$->return_type = "void";
        $$->loc = {@1.first_line, @1.first_column};
        if ($4) {
            $$->parameters = *$4;
            delete $4;
        }
        if ($6) {
            $$->traces = $6->traces;
            $$->has_transition = $6->has_transition;
            $$->transition = $6->transition;
            for (const auto& cond : $6->preconditions) {
                $$->preconditions.push_back(cond.text);
                $$->preconditions_ast.push_back(cond.expr);
            }
            for (const auto& cond : $6->postconditions) {
                $$->postconditions.push_back(cond.text);
                $$->postconditions_ast.push_back(cond.expr);
            }
            delete $6;
        }
        delete $2;
    }
    ;

param_list:
    %empty { $$ = new std::vector<agentc::Field>(); }
    | params { $$ = $1; }
    ;

params:
    param {
        $$ = new std::vector<agentc::Field>{*$1};
        delete $1;
    }
    | params ',' param {
        $$ = $1;
        $$->push_back(*$3);
        delete $3;
    }
    ;

param:
    any_identifier ':' type_ref {
        $$ = new agentc::Field{*$1, *$3, {@1.first_line, @1.first_column}};
        delete $1; delete $3;
    }
    ;

fn_body:
    ';' {
        $$ = new agentc::FnContract();
    }
    | '{' fn_clauses '}' {
        $$ = $2;
    }
    ;

fn_clauses:
    %empty {
        $$ = new agentc::FnContract();
    }
    | fn_clauses PRE ':' condition_expr ';' {
        $$ = $1;
        $$->preconditions.push_back(agentc::Condition{$4->text, $4->expr, {@2.first_line, @2.first_column}});
        delete $4;
    }
    | fn_clauses POST ':' condition_expr ';' {
        $$ = $1;
        $$->postconditions.push_back(agentc::Condition{$4->text, $4->expr, {@2.first_line, @2.first_column}});
        delete $4;
    }
    | fn_clauses TRACES ':' trace_list ';' {
        $$ = $1;
        if ($4) {
            for (const auto& tr : *$4) {
                $$->traces.push_back(tr);
            }
            delete $4;
        }
    }
    | fn_clauses TRANSITION ':' any_identifier ARROW any_identifier ';' {
        $$ = $1;
        $$->has_transition = true;
        $$->transition = agentc::TransitionDef{*$4, *$6, {@2.first_line, @2.first_column}};
        delete $4; delete $6;
    }
    | fn_clauses error ';' {
        $$ = $1;
        yyerrok;
    }
    ;

condition_expr:
    expr { $$ = $1; }
    ;

expr:
    primary_expr { $$ = $1; }
    | expr AND expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "and";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr OR expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "or";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr IMPLIES expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "implies";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | NOT expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::UnaryOp;
        e->op = "not";
        e->args.push_back($2->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $2;
    }
    | '-' expr %prec UMINUS {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::UnaryOp;
        e->op = "-";
        e->args.push_back($2->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $2;
    }
    | expr '<' expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "<";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr '>' expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = ">";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr LE expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "<=";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr GE expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = ">=";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr EQ expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "==";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr NE expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "!=";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr '+' expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "+";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr '-' expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "-";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr '*' expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "*";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr '/' expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "/";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | expr '%' expr {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BinaryOp;
        e->op = "%";
        e->args.push_back($1->expr);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | '(' expr ')' {
        $$ = $2;
    }
    ;

primary_expr:
    expr_atom { $$ = $1; }
    | primary_expr '.' any_identifier {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::MemberAccess;
        e->op = ".";
        e->value = *$3;
        e->args.push_back($1->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1; delete $3;
    }
    | primary_expr '(' ')' {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::Call;
        e->args.push_back($1->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1;
    }
    | primary_expr '(' call_args ')' {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::Call;
        e->args.push_back($1->expr);
        if ($3) {
            for (auto& a : *$3) {
                e->args.push_back(a);
            }
            delete $3;
        }
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1;
    }
    ;

expr_atom:
    IDENTIFIER {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::Identifier;
        e->value = *$1;
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1;
    }
    | OLD '(' expr ')' {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::Call;
        e->value = "old";
        auto callee = std::make_shared<agentc::Expr>();
        callee->kind = agentc::Expr::Kind::Identifier;
        callee->value = "old";
        callee->loc = {@1.first_line, @1.first_column};
        e->args.push_back(callee);
        e->args.push_back($3->expr);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $3;
    }
    | TIME_LITERAL {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::LiteralUnit;
        std::string raw = *$1;
        size_t pos = 0;
        while (pos < raw.size() && (std::isdigit(raw[pos]) || raw[pos] == '.')) {
            pos++;
        }
        e->value = raw.substr(0, pos);
        e->unit = raw.substr(pos);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{raw, e};
        delete $1;
    }
    | BYTES_LITERAL {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::LiteralUnit;
        std::string raw = *$1;
        size_t pos = 0;
        while (pos < raw.size() && (std::isdigit(raw[pos]) || raw[pos] == '.')) {
            pos++;
        }
        e->value = raw.substr(0, pos);
        e->unit = raw.substr(pos);
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{raw, e};
        delete $1;
    }
    | NUMBER_LITERAL {
        auto e = std::make_shared<agentc::Expr>();
        if ($1->find('.') != std::string::npos) {
            e->kind = agentc::Expr::Kind::FloatLiteral;
        } else {
            e->kind = agentc::Expr::Kind::IntLiteral;
        }
        e->value = *$1;
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1;
    }
    | STRING_LITERAL {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::StringLiteral;
        e->value = *$1;
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{e->toCanonicalString(), e};
        delete $1;
    }
    | TRUE_KW {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BoolLiteral;
        e->value = "true";
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{"true", e};
    }
    | FALSE_KW {
        auto e = std::make_shared<agentc::Expr>();
        e->kind = agentc::Expr::Kind::BoolLiteral;
        e->value = "false";
        e->loc = {@1.first_line, @1.first_column};
        $$ = new agentc::ExprNode{"false", e};
    }
    ;

call_args:
    expr {
        $$ = new std::vector<agentc::ExprPtr>{$1->expr};
        delete $1;
    }
    | call_args ',' expr {
        $$ = $1;
        $$->push_back($3->expr);
        delete $3;
    }
    ;

/* Agent implementation declaration */
agent_impl_decl:
    AGENT IMPLEMENTATION FOR qualified_id '{' {
        agentc::AgentImplDecl a;
        a.contract_name = *$4;
        a.loc = {@1.first_line, @1.first_column};
        driver->ast.agent_impls.push_back(a);
        delete $4;
    } agent_body '}'
    ;

agent_body:
    %empty
    | agent_body agent_member
    ;

agent_member:
    INTENT ':' STRING_LITERAL ';' {
        if (!driver->ast.agent_impls.empty()) {
            driver->ast.agent_impls.back().intent = *$3;
        }
        delete $3;
    }
    | INVARIANTS ':' '[' string_list ']' ';' {
        if (!driver->ast.agent_impls.empty() && $4) {
            driver->ast.agent_impls.back().invariants = *$4;
            delete $4;
        }
    }
    | HARNESS ':' IDENTIFIER ';' {
        if (!driver->ast.agent_impls.empty()) {
            driver->ast.agent_impls.back().harness_type = *$3;
        }
        delete $3;
    }
    | HARNESS ':' IDENTIFIER '{' key_value_block '}' optional_semicolon {
        if (!driver->ast.agent_impls.empty()) {
            driver->ast.agent_impls.back().harness_type = *$3;
            if ($5) {
                driver->ast.agent_impls.back().harness_options = *$5;
                delete $5;
            }
        }
        delete $3;
    }
    ;

string_list:
    %empty { $$ = new std::vector<std::string>(); }
    | STRING_LITERAL {
        $$ = new std::vector<std::string>{*$1};
        delete $1;
    }
    | string_list ',' STRING_LITERAL {
        $$ = $1;
        $$->push_back(*$3);
        delete $3;
    }
    | string_list ',' {
        $$ = $1;
    }
    ;

/* Lifecycle declaration */
lifecycle_decl:
    LIFECYCLE IDENTIFIER '{' {
        agentc::LifecycleDecl l;
        l.name = *$2;
        l.loc = {@1.first_line, @1.first_column};
        driver->ast.lifecycles.push_back(l);
        delete $2;
    } lifecycle_body '}'
    ;

lifecycle_body:
    %empty
    | lifecycle_body lifecycle_member
    ;

lifecycle_member:
    VERIFY ':' '[' identifier_list ']' ';' {
        if (!driver->ast.lifecycles.empty() && $4) {
            driver->ast.lifecycles.back().verify_checks = *$4;
            delete $4;
        }
    }
    | BENCHMARK ':' '{' key_value_block '}' optional_semicolon {
        if (!driver->ast.lifecycles.empty() && $4) {
            driver->ast.lifecycles.back().benchmarks = *$4;
            delete $4;
        }
    }
    | PACKAGE ':' IDENTIFIER '{' key_value_block '}' optional_semicolon {
        if (!driver->ast.lifecycles.empty()) {
            driver->ast.lifecycles.back().package_type = *$3;
            if ($5) {
                driver->ast.lifecycles.back().package_options = *$5;
                delete $5;
            }
        }
        delete $3;
    }
    | DEPLOY ':' IDENTIFIER '{' key_value_block '}' optional_semicolon {
        if (!driver->ast.lifecycles.empty()) {
            driver->ast.lifecycles.back().deploy_target = *$3;
            if ($5) {
                driver->ast.lifecycles.back().deploy_options = *$5;
                delete $5;
            }
        }
        delete $3;
    }
    ;

identifier_list:
    %empty { $$ = new std::vector<std::string>(); }
    | IDENTIFIER {
        $$ = new std::vector<std::string>{*$1};
        delete $1;
    }
    | identifier_list ',' IDENTIFIER {
        $$ = $1;
        $$->push_back(*$3);
        delete $3;
    }
    | identifier_list ',' {
        $$ = $1;
    }
    ;

key_value_block:
    %empty { $$ = new std::map<std::string, std::string>(); }
    | key_value_block key_value_entry {
        $$ = $1;
        if ($2) {
            (*$$)[$2->first] = $2->second;
            delete $2;
        }
    }
    ;

key_value_entry:
    any_identifier ':' option_value ';' {
        $$ = new std::pair<std::string, std::string>(*$1, *$3);
        delete $1; delete $3;
    }
    ;

any_identifier:
    IDENTIFIER
    | PACKAGE { $$ = new std::string("package"); }
    | DEPLOY { $$ = new std::string("deploy"); }
    | VERIFY { $$ = new std::string("verify"); }
    | BENCHMARK { $$ = new std::string("benchmark"); }
    | HARNESS { $$ = new std::string("harness"); }
    | TARGET { $$ = new std::string("target"); }
    | MODULE { $$ = new std::string("module"); }
    | TYPE { $$ = new std::string("type"); }
    | ARTIFACT { $$ = new std::string("artifact"); }
    | PRD { $$ = new std::string("prd"); }
    | ADR { $$ = new std::string("adr"); }
    | HLD { $$ = new std::string("hld"); }
    | LLD { $$ = new std::string("lld"); }
    | STATE { $$ = new std::string("state"); }
    | MACHINE { $$ = new std::string("machine"); }
    | INITIAL_KW { $$ = new std::string("initial"); }
    | TRANSITIONS { $$ = new std::string("transitions"); }
    | TRANSITION { $$ = new std::string("transition"); }
    | TRACES { $$ = new std::string("traces"); }
    | OLD { $$ = new std::string("old"); }
    ;

/* Helper rules */
qualified_id:
    IDENTIFIER { $$ = $1; }
    | qualified_id '.' IDENTIFIER {
        $$ = new std::string(*$1 + "." + *$3);
        delete $1; delete $3;
    }
    | qualified_id DOUBLE_COLON IDENTIFIER {
        $$ = new std::string(*$1 + "::" + *$3);
        delete $1; delete $3;
    }
    ;

type_ref:
    qualified_id { $$ = $1; }
    | qualified_id '<' type_ref_list '>' {
        $$ = new std::string(*$1 + "<" + *$3 + ">");
        delete $1; delete $3;
    }
    ;

type_ref_list:
    type_ref { $$ = $1; }
    | type_ref_list ',' type_ref {
        $$ = new std::string(*$1 + ", " + *$3);
        delete $1; delete $3;
    }
    ;

%%

void yyerror(YYLTYPE* loc, yyscan_t scanner, agentc::Driver* driver, const char* msg) {
    (void)scanner;
    driver->error({loc->first_line, loc->first_column}, msg);
}
