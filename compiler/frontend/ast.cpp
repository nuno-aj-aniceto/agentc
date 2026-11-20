#include "ast.hpp"
#include <iomanip>
#include <sstream>

namespace agentc {

std::string escapeJson(const std::string& str) {
    std::ostringstream ss;
    for (char c : str) {
        switch (c) {
            case '"': ss << "\\\""; break;
            case '\\': ss << "\\\\"; break;
            case '\b': ss << "\\b"; break;
            case '\f': ss << "\\f"; break;
            case '\n': ss << "\\n"; break;
            case '\r': ss << "\\r"; break;
            case '\t': ss << "\\t"; break;
            default:
                if ('\x00' <= c && c <= '\x1f') {
                    ss << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c);
                } else {
                    ss << c;
                }
        }
    }
    return ss.str();
}

std::string quoteAndEscape(const std::string& str) {
    std::ostringstream ss;
    ss << "\"";
    for (char c : str) {
        switch (c) {
            case '"': ss << "\\\""; break;
            case '\\': ss << "\\\\"; break;
            case '\n': ss << "\\n"; break;
            case '\r': ss << "\\r"; break;
            case '\t': ss << "\\t"; break;
            default: ss << c; break;
        }
    }
    ss << "\"";
    return ss.str();
}

std::string locJson(const SourceLocation& loc) {
    return "{\"line\":" + std::to_string(loc.line) + ",\"column\":" + std::to_string(loc.column) + "}";
}

static int getOpPrecedence(const std::string& op) {
    if (op == "implies") return 1;
    if (op == "or") return 2;
    if (op == "and") return 3;
    if (op == "not") return 4;
    if (op == "<" || op == "<=" || op == ">" || op == ">=" || op == "==" || op == "!=") return 5;
    if (op == "+" || op == "-") return 6;
    if (op == "*" || op == "/" || op == "%") return 7;
    return 99;
}

std::string Expr::toCanonicalString() const {
    switch (kind) {
        case Kind::Identifier:
            return value;
        case Kind::IntLiteral:
        case Kind::FloatLiteral:
        case Kind::BoolLiteral:
            return value;
        case Kind::StringLiteral:
            return quoteAndEscape(value);
        case Kind::UnaryOp: {
            if (args.empty()) return op;
            std::string sub = args[0]->toCanonicalString();
            if (args[0]->kind == Kind::BinaryOp) {
                sub = "(" + sub + ")";
            }
            if (op == "not") return "not " + sub;
            return op + sub;
        }
        case Kind::BinaryOp: {
            if (args.size() < 2) return value;
            int myPrec = getOpPrecedence(op);

            std::string leftStr = args[0]->toCanonicalString();
            if (args[0]->kind == Kind::BinaryOp && getOpPrecedence(args[0]->op) < myPrec) {
                leftStr = "(" + leftStr + ")";
            }

            std::string rightStr = args[1]->toCanonicalString();
            // Implication is right-associative; others left-associative
            if (args[1]->kind == Kind::BinaryOp) {
                int rPrec = getOpPrecedence(args[1]->op);
                if (rPrec < myPrec || (rPrec == myPrec && op != "implies")) {
                    rightStr = "(" + rightStr + ")";
                }
            }

            return leftStr + " " + op + " " + rightStr;
        }
        case Kind::MemberAccess: {
            if (args.empty()) return value;
            return args[0]->toCanonicalString() + "." + value;
        }
        case Kind::LiteralUnit:
            return value + unit;
        case Kind::Call: {
            if (args.empty()) return "()";
            std::string res = args[0]->toCanonicalString() + "(";
            for (size_t i = 1; i < args.size(); ++i) {
                if (i > 1) res += ", ";
                res += args[i]->toCanonicalString();
            }
            res += ")";
            return res;
        }
    }
    return value;
}

std::string Expr::toJson() const {
    std::ostringstream ss;
    ss << "{";
    ss << "\"kind\": \"";
    switch (kind) {
        case Kind::Identifier: ss << "ident"; break;
        case Kind::IntLiteral: ss << "int"; break;
        case Kind::FloatLiteral: ss << "float"; break;
        case Kind::StringLiteral: ss << "string"; break;
        case Kind::BoolLiteral: ss << "bool"; break;
        case Kind::UnaryOp: ss << "unary"; break;
        case Kind::BinaryOp: ss << "binary"; break;
        case Kind::MemberAccess: ss << "member"; break;
        case Kind::LiteralUnit: ss << "unit"; break;
        case Kind::Call: ss << "call"; break;
    }
    ss << "\"";
    if (!op.empty()) {
        ss << ", \"op\": \"" << escapeJson(op) << "\"";
    }
    if (!value.empty()) {
        ss << ", \"value\": \"" << escapeJson(value) << "\"";
    }
    if (!unit.empty()) {
        ss << ", \"unit\": \"" << escapeJson(unit) << "\"";
    }
    ss << ", \"loc\": " << locJson(loc);
    if (!args.empty()) {
        ss << ", \"args\": [";
        for (size_t i = 0; i < args.size(); ++i) {
            if (i > 0) ss << ", ";
            ss << args[i]->toJson();
        }
        ss << "]";
    }
    ss << "}";
    return ss.str();
}

std::string ModuleAST::toJson() const {
    std::ostringstream ss;
    ss << "{\n";
    ss << "  \"schema_version\": 2,\n";
    ss << "  \"module_name\": \"" << escapeJson(module_name) << "\",\n";
    
    // imports
    ss << "  \"imports\": [";
    for (size_t i = 0; i < imports.size(); ++i) {
        if (i > 0) ss << ", ";
        ss << "\"" << escapeJson(imports[i]) << "\"";
    }
    ss << "],\n";

    // targets
    ss << "  \"targets\": [\n";
    for (size_t i = 0; i < targets.size(); ++i) {
        const auto& t = targets[i];
        ss << "    {\n";
        ss << "      \"name\": \"" << escapeJson(t.target_name) << "\",\n";
        ss << "      \"loc\": " << locJson(t.loc) << ",\n";
        ss << "      \"options\": {";
        size_t opt_idx = 0;
        for (const auto& [k, v] : t.options) {
            if (opt_idx++ > 0) ss << ", ";
            ss << "\"" << escapeJson(k) << "\": \"" << escapeJson(v) << "\"";
        }
        ss << "}\n";
        ss << "    }" << (i + 1 < targets.size() ? "," : "") << "\n";
    }
    ss << "  ],\n";

    // artifacts (PRD / ADR / HLD / LLD)
    ss << "  \"artifacts\": [\n";
    for (size_t i = 0; i < artifacts.size(); ++i) {
        const auto& a = artifacts[i];
        ss << "    {\n";
        ss << "      \"type\": \"" << escapeJson(a.artifact_type) << "\",\n";
        ss << "      \"id\": \"" << escapeJson(a.identifier) << "\",\n";
        ss << "      \"loc\": " << locJson(a.loc) << ",\n";
        ss << "      \"metadata\": {";
        size_t m_idx = 0;
        for (const auto& [k, v] : a.metadata) {
            if (m_idx++ > 0) ss << ", ";
            ss << "\"" << escapeJson(k) << "\": \"" << escapeJson(v) << "\"";
        }
        ss << "},\n";
        ss << "      \"constraints\": [";
        for (size_t c_idx = 0; c_idx < a.constraints.size(); ++c_idx) {
            if (c_idx > 0) ss << ", ";
            ss << "\"" << escapeJson(a.constraints[c_idx]) << "\"";
        }
        ss << "]\n";
        ss << "    }" << (i + 1 < artifacts.size() ? "," : "") << "\n";
    }
    ss << "  ],\n";

    // contracts
    ss << "  \"contracts\": [\n";
    for (size_t i = 0; i < contracts.size(); ++i) {
        const auto& c = contracts[i];
        ss << "    {\n";
        ss << "      \"name\": \"" << escapeJson(c.name) << "\",\n";
        ss << "      \"loc\": " << locJson(c.loc) << ",\n";
        
        // traces
        ss << "      \"traces\": [";
        for (size_t ti = 0; ti < c.traces.size(); ++ti) {
            if (ti > 0) ss << ", ";
            ss << "\"" << escapeJson(c.traces[ti]) << "\"";
        }
        ss << "],\n";

        // state_machines
        ss << "      \"state_machines\": [\n";
        for (size_t smi = 0; smi < c.state_machines.size(); ++smi) {
            const auto& sm = c.state_machines[smi];
            ss << "        {\n";
            ss << "          \"name\": \"" << escapeJson(sm.name) << "\",\n";
            ss << "          \"initial_state\": \"" << escapeJson(sm.initial_state) << "\",\n";
            ss << "          \"loc\": " << locJson(sm.loc) << ",\n";
            ss << "          \"transitions\": [";
            for (size_t tri = 0; tri < sm.transitions.size(); ++tri) {
                if (tri > 0) ss << ", ";
                ss << "{\"from\": \"" << escapeJson(sm.transitions[tri].from_state)
                   << "\", \"to\": \"" << escapeJson(sm.transitions[tri].to_state)
                   << "\", \"loc\": " << locJson(sm.transitions[tri].loc) << "}";
            }
            ss << "]\n";
            ss << "        }" << (smi + 1 < c.state_machines.size() ? "," : "") << "\n";
        }
        ss << "      ],\n";

        // types
        ss << "      \"types\": [\n";
        for (size_t ti = 0; ti < c.types.size(); ++ti) {
            const auto& ty = c.types[ti];
            ss << "        {\n";
            ss << "          \"kind\": \"" << escapeJson(ty.kind) << "\",\n";
            ss << "          \"name\": \"" << escapeJson(ty.name) << "\",\n";
            ss << "          \"alias_target\": \"" << escapeJson(ty.alias_target) << "\",\n";
            ss << "          \"loc\": " << locJson(ty.loc) << ",\n";
            ss << "          \"fields\": [";
            for (size_t fi = 0; fi < ty.fields.size(); ++fi) {
                if (fi > 0) ss << ", ";
                ss << "{\"name\": \"" << escapeJson(ty.fields[fi].name) << "\", \"type\": \"" 
                   << escapeJson(ty.fields[fi].type) << "\", \"loc\": " << locJson(ty.fields[fi].loc) << "}";
            }
            ss << "],\n";
            ss << "          \"variants\": [";
            for (size_t vi = 0; vi < ty.enum_variants.size(); ++vi) {
                if (vi > 0) ss << ", ";
                ss << "\"" << escapeJson(ty.enum_variants[vi]) << "\"";
            }
            ss << "]\n";
            ss << "        }" << (ti + 1 < c.types.size() ? "," : "") << "\n";
        }
        ss << "      ],\n";

        // functions
        ss << "      \"functions\": [\n";
        for (size_t fi = 0; fi < c.functions.size(); ++fi) {
            const auto& fn = c.functions[fi];
            ss << "        {\n";
            ss << "          \"name\": \"" << escapeJson(fn.name) << "\",\n";
            ss << "          \"return_type\": \"" << escapeJson(fn.return_type) << "\",\n";
            ss << "          \"loc\": " << locJson(fn.loc) << ",\n";
            ss << "          \"parameters\": [";
            for (size_t pi = 0; pi < fn.parameters.size(); ++pi) {
                if (pi > 0) ss << ", ";
                ss << "{\"name\": \"" << escapeJson(fn.parameters[pi].name) << "\", \"type\": \"" 
                   << escapeJson(fn.parameters[pi].type) << "\", \"loc\": " << locJson(fn.parameters[pi].loc) << "}";
            }
            ss << "],\n";
            ss << "          \"preconditions\": [";
            for (size_t pi = 0; pi < fn.preconditions.size(); ++pi) {
                if (pi > 0) ss << ", ";
                ss << "\"" << escapeJson(fn.preconditions[pi]) << "\"";
            }
            ss << "],\n";
            ss << "          \"preconditions_ast\": [";
            for (size_t pi = 0; pi < fn.preconditions_ast.size(); ++pi) {
                if (pi > 0) ss << ", ";
                ss << fn.preconditions_ast[pi]->toJson();
            }
            ss << "],\n";
            ss << "          \"postconditions\": [";
            for (size_t pi = 0; pi < fn.postconditions.size(); ++pi) {
                if (pi > 0) ss << ", ";
                ss << "\"" << escapeJson(fn.postconditions[pi]) << "\"";
            }
            ss << "],\n";
            ss << "          \"postconditions_ast\": [";
            for (size_t pi = 0; pi < fn.postconditions_ast.size(); ++pi) {
                if (pi > 0) ss << ", ";
                ss << fn.postconditions_ast[pi]->toJson();
            }
            ss << "],\n";
            ss << "          \"traces\": [";
            for (size_t ti = 0; ti < fn.traces.size(); ++ti) {
                if (ti > 0) ss << ", ";
                ss << "\"" << escapeJson(fn.traces[ti]) << "\"";
            }
            ss << "],\n";
            if (fn.has_transition) {
                ss << "          \"transition\": {\"from\": \"" << escapeJson(fn.transition.from_state)
                   << "\", \"to\": \"" << escapeJson(fn.transition.to_state)
                   << "\", \"loc\": " << locJson(fn.transition.loc) << "}\n";
            } else {
                ss << "          \"transition\": null\n";
            }
            ss << "        }" << (fi + 1 < c.functions.size() ? "," : "") << "\n";
        }
        ss << "      ]\n";

        ss << "    }" << (i + 1 < contracts.size() ? "," : "") << "\n";
    }
    ss << "  ],\n";

    // agent implementations
    ss << "  \"agent_implementations\": [\n";
    for (size_t i = 0; i < agent_impls.size(); ++i) {
        const auto& a = agent_impls[i];
        ss << "    {\n";
        ss << "      \"contract_name\": \"" << escapeJson(a.contract_name) << "\",\n";
        ss << "      \"intent\": \"" << escapeJson(a.intent) << "\",\n";
        ss << "      \"loc\": " << locJson(a.loc) << ",\n";
        ss << "      \"invariants\": [";
        for (size_t inv_i = 0; inv_i < a.invariants.size(); ++inv_i) {
            if (inv_i > 0) ss << ", ";
            ss << "\"" << escapeJson(a.invariants[inv_i]) << "\"";
        }
        ss << "],\n";
        ss << "      \"harness_type\": \"" << escapeJson(a.harness_type) << "\",\n";
        ss << "      \"harness_options\": {";
        size_t h_idx = 0;
        for (const auto& [k, v] : a.harness_options) {
            if (h_idx++ > 0) ss << ", ";
            ss << "\"" << escapeJson(k) << "\": \"" << escapeJson(v) << "\"";
        }
        ss << "}\n";
        ss << "    }" << (i + 1 < agent_impls.size() ? "," : "") << "\n";
    }
    ss << "  ],\n";

    // lifecycles
    ss << "  \"lifecycles\": [\n";
    for (size_t i = 0; i < lifecycles.size(); ++i) {
        const auto& l = lifecycles[i];
        ss << "    {\n";
        ss << "      \"name\": \"" << escapeJson(l.name) << "\",\n";
        ss << "      \"loc\": " << locJson(l.loc) << ",\n";
        ss << "      \"verify\": [";
        for (size_t vi = 0; vi < l.verify_checks.size(); ++vi) {
            if (vi > 0) ss << ", ";
            ss << "\"" << escapeJson(l.verify_checks[vi]) << "\"";
        }
        ss << "],\n";
        ss << "      \"benchmarks\": {";
        size_t b_idx = 0;
        for (const auto& [k, v] : l.benchmarks) {
            if (b_idx++ > 0) ss << ", ";
            ss << "\"" << escapeJson(k) << "\": \"" << escapeJson(v) << "\"";
        }
        ss << "},\n";
        ss << "      \"package\": {\"type\": \"" << escapeJson(l.package_type) << "\", \"options\": {";
        size_t p_idx = 0;
        for (const auto& [k, v] : l.package_options) {
            if (p_idx++ > 0) ss << ", ";
            ss << "\"" << escapeJson(k) << "\": \"" << escapeJson(v) << "\"";
        }
        ss << "}},\n";
        ss << "      \"deploy\": {\"target\": \"" << escapeJson(l.deploy_target) << "\", \"options\": {";
        size_t d_idx = 0;
        for (const auto& [k, v] : l.deploy_options) {
            if (d_idx++ > 0) ss << ", ";
            ss << "\"" << escapeJson(k) << "\": \"" << escapeJson(v) << "\"";
        }
        ss << "}}\n";
        ss << "    }" << (i + 1 < lifecycles.size() ? "," : "") << "\n";
    }
    ss << "  ]\n";

    ss << "}\n";
    return ss.str();
}

} // namespace agentc
