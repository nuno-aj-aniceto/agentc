#!/usr/bin/env python3
"""
java_emitter.py
Generates Maven pom.xml and standalone Makefile for Java 21+ targets.
Incorporates artifact lineage metadata, CLI harnesses, and packaging rules.
"""

from typing import Dict, Any, List, Optional, Union

class JavaEmitter:
    @staticmethod
    def _normalize_contracts(contract_name_or_list: Union[str, List[str]]) -> List[str]:
        if isinstance(contract_name_or_list, list):
            return contract_name_or_list
        return [contract_name_or_list]

    @staticmethod
    def generate_pom(module_name: str, contracts: Union[str, List[str]], options: Dict[str, str],
                     artifacts: Optional[List[Dict[str, Any]]] = None) -> str:
        pkg = options.get("package", "com.agentlang.generated")
        jdk = options.get("jdk", "21")
        artifact_id = module_name.replace(".", "-").lower()

        lineage_comment = "<!-- [agentc] Lineage: "
        if artifacts:
            lineage_comment += ", ".join([f"{a.get('type','').upper()}:{a.get('id','')}" for a in artifacts])
        else:
            lineage_comment += "PRD:Default, ADR:Default"
        lineage_comment += " | Reasoning Engine: JEV + Drex -->"

        return f"""<?xml version="1.0" encoding="UTF-8"?>
{lineage_comment}
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>{pkg}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>{jdk}</maven.compiler.source>
        <maven.compiler.target>{jdk}</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <junit.version>5.10.2</junit.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>${{junit.version}}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.13.0</version>
                <configuration>
                    <release>{jdk}</release>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
            </plugin>
        </plugins>
    </build>
</project>
"""

    @staticmethod
    def generate_makefile(module_name: str, contracts: Union[str, List[str]], options: Dict[str, str],
                          artifacts: Optional[List[Dict[str, Any]]] = None) -> str:
        contract_list = JavaEmitter._normalize_contracts(contracts)
        pkg = options.get("package", "com.agentlang.generated")
        primary_contract = contract_list[0] if contract_list else "App"

        return f"""# [agentc] Standalone Java Makefile (Builds without Maven)
JAVAC ?= javac
JAR ?= jar
JAVA ?= java
TARGET_DIR := target/classes
TEST_CLASSES := target/test-classes
JAR_FILE := target/{module_name.replace('.', '-').lower()}-1.0.0.jar

.PHONY: all classes jar test clean

all: jar

classes:
	mkdir -p $(TARGET_DIR)
	find src/main/java -name "*.java" > target/sources.txt
	$(JAVAC) -d $(TARGET_DIR) @target/sources.txt

jar: classes
	$(JAR) --create --file $(JAR_FILE) --main-class {pkg}.{primary_contract}Cli -C $(TARGET_DIR) .

test: classes
	@if [ -d "src/test/java" ]; then \\
	  mkdir -p $(TEST_CLASSES); \\
	  find src/test/java -name "*.java" > target/test-sources.txt; \\
	  $(JAVAC) -cp $(TARGET_DIR) -d $(TEST_CLASSES) @target/test-sources.txt; \\
	fi
	$(JAVA) -cp $(TARGET_DIR) {pkg}.{primary_contract}Cli selftest

clean:
	rm -rf target/
"""
