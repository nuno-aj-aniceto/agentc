#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <sstream>

namespace agentc {

struct SourceLocation {
    int line = 1;
    int column = 1;
};

// Typed Expression AST Node for Pre/Post conditions
struct Expr {
    enum class Kind {
        Identifier,
        IntLiteral,
        FloatLiteral,
        StringLiteral,
        BoolLiteral,
        LiteralUnit,
        UnaryOp,
        BinaryOp,
        MemberAccess,
        Call
    };

    Kind kind = Kind::Identifier;
    std::string op;
    std::string value;
    std::string unit; // e.g. "ms", "s", "MB", "GB"
    std::vector<std::shared_ptr<Expr>> args;
    SourceLocation loc;

    std::string toCanonicalString() const;
    std::string toJson() const;
};

using ExprPtr = std::shared_ptr<Expr>;

struct Condition {
    std::string text;
    ExprPtr expr;
    SourceLocation loc;
};

// Represents a state transition in a state machine: FromState -> ToState
struct TransitionDef {
    std::string from_state;
    std::string to_state;
    SourceLocation loc;
};

// State Machine declaration inside a contract
struct StateMachineAST {
    std::string name;
    std::string initial_state;
    std::vector<TransitionDef> transitions;
    SourceLocation loc;
};

// Represents a parameter or struct field: name : type
struct Field {
    std::string name;
    std::string type;
    SourceLocation loc;
};

// Function contract: fn name(params...) -> return_type { pre: ...; post: ...; }
struct FunctionDecl {
    std::string name;
    std::vector<Field> parameters;
    std::string return_type;
    std::vector<std::string> preconditions;
    std::vector<std::string> postconditions;
    std::vector<ExprPtr> preconditions_ast;
    std::vector<ExprPtr> postconditions_ast;
    std::vector<std::string> traces;
    bool has_transition = false;
    TransitionDef transition;
    SourceLocation loc;
};

// Type definition: type Name = Base; or struct Name { fields... }; or enum Name { values... };
struct TypeDecl {
    std::string kind; // "alias", "struct", "enum"
    std::string name;
    std::string alias_target;
    std::vector<Field> fields;
    std::vector<std::string> enum_variants;
    SourceLocation loc;
};

// Contract declaration
struct ContractDecl {
    std::string name;
    std::vector<TypeDecl> types;
    std::vector<FunctionDecl> functions;
    std::vector<std::string> traces;
    std::vector<StateMachineAST> state_machines;
    SourceLocation loc;
};

// Target toolchain directive: target cpp { toolchain: cmake; standard: "c++20"; ... }
struct TargetDecl {
    std::string target_name; // "cpp", "java", etc.
    std::map<std::string, std::string> options;
    SourceLocation loc;
};

// Agent implementation node: agent implementation for ContractName { intent: "..."; invariants: [...]; harness: tdd; }
struct AgentImplDecl {
    std::string contract_name;
    std::string intent;
    std::vector<std::string> invariants;
    std::string harness_type;
    std::map<std::string, std::string> harness_options;
    SourceLocation loc;
};

// Lifecycle / SDLC configuration node
struct LifecycleDecl {
    std::string name;
    std::vector<std::string> verify_checks;
    std::map<std::string, std::string> benchmarks;
    std::string package_type;
    std::map<std::string, std::string> package_options;
    std::string deploy_target;
    std::map<std::string, std::string> deploy_options;
    SourceLocation loc;
};

// Software engineering artifact lineage node (PRD, ADR, HLD, LLD)
struct ArtifactLineageDecl {
    std::string artifact_type; // "prd", "adr", "hld", "lld"
    std::string identifier;    // e.g. "PRD-SEC-001"
    std::map<std::string, std::string> metadata;
    std::vector<std::string> constraints;
    SourceLocation loc;
};

// Root AST Node for a compilation unit (.afl / .agent)
struct ModuleAST {
    std::string module_name;
    std::vector<std::string> imports;
    std::vector<TargetDecl> targets;
    std::vector<ArtifactLineageDecl> artifacts;
    std::vector<ContractDecl> contracts;
    std::vector<AgentImplDecl> agent_impls;
    std::vector<LifecycleDecl> lifecycles;

    std::string toJson() const;
};

// Helpers
std::string escapeJson(const std::string& str);
std::string quoteAndEscape(const std::string& str);
std::string locJson(const SourceLocation& loc);

} // namespace agentc
