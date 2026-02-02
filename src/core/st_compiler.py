"""IEC 61131-3 Structured Text compiler with control flow support."""
import re
from typing import List, Optional, Tuple, Any, Dict
from dataclasses import dataclass
from src.models.plc_models import (
    CompileResult, CompileError, PLCProgram, PLCVariable, 
    PLCDataType, VariableScope
)


@dataclass
class ASTNode:
    """Abstract Syntax Tree node."""
    node_type: str
    line: int
    children: List['ASTNode'] = None
    value: Any = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class STLexer:
    """Tokenizer for Structured Text."""
    
    KEYWORDS = {
        'PROGRAM', 'END_PROGRAM', 'VAR', 'END_VAR', 'VAR_INPUT', 'VAR_OUTPUT',
        'VAR_IN_OUT', 'IF', 'THEN', 'ELSE', 'ELSIF', 'END_IF', 'CASE', 'OF',
        'END_CASE', 'FOR', 'TO', 'BY', 'DO', 'END_FOR', 'WHILE', 'END_WHILE',
        'REPEAT', 'UNTIL', 'END_REPEAT', 'FUNCTION', 'END_FUNCTION',
        'FUNCTION_BLOCK', 'END_FUNCTION_BLOCK', 'RETURN', 'EXIT',
        'TRUE', 'FALSE', 'AND', 'OR', 'NOT', 'XOR', 'MOD', 'DIV'
    }
    
    DATA_TYPES = {
        'BOOL', 'BYTE', 'WORD', 'DWORD', 'LWORD',
        'SINT', 'INT', 'DINT', 'LINT',
        'USINT', 'UINT', 'UDINT', 'ULINT',
        'REAL', 'LREAL', 'TIME', 'DATE', 'STRING'
    }
    
    def tokenize(self, code: str) -> List[Tuple[str, str, int]]:
        """Tokenize ST code. Returns list of (token_type, value, line_number)."""
        tokens = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Remove comments
            if '(*' in line:
                line = line[:line.index('(*')]
            if '//' in line:
                line = line[:line.index('//')]
            
            # Enhanced regex pattern for floating point numbers
            pattern = r'(\d+\.\d+|\w+|:=|<=|>=|<>|[+\-*/()[\]:;,.<>=])'
            matches = re.findall(pattern, line)
            
            for match in matches:
                if match.upper() in self.KEYWORDS:
                    tokens.append(('KEYWORD', match.upper(), line_num))
                elif match.upper() in self.DATA_TYPES:
                    tokens.append(('TYPE', match.upper(), line_num))
                elif re.match(r'^\d+\.?\d*$', match):  # Integer or float
                    tokens.append(('NUMBER', match, line_num))
                elif match.isidentifier():
                    tokens.append(('IDENTIFIER', match, line_num))
                elif match in [':=', '<=', '>=', '<>']:
                    tokens.append(('OPERATOR', match, line_num))
                else:
                    tokens.append(('SYMBOL', match, line_num))
        
        return tokens


class STParser:
    """ST parser for variable declarations and control flow structures."""
    
    def __init__(self):
        self.lexer = STLexer()
        self.tokens: List[Tuple[str, str, int]] = []
        self.pos: int = 0
    
    def parse(self, code: str) -> Tuple[ASTNode, List[CompileError]]:
        """Parse ST code into AST."""
        self.tokens = self.lexer.tokenize(code)
        self.pos = 0
        errors = []
        
        try:
            ast = self._parse_program()
            return ast, errors
        except Exception as e:
            errors.append(CompileError(0, 0, f"Parse error: {str(e)}"))
            return ASTNode("PROGRAM", 0), errors
    
    def _current_token(self) -> Optional[Tuple[str, str, int]]:
        """Get current token."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None
    
    def _advance(self) -> None:
        """Move to next token."""
        self.pos += 1
    
    def _expect(self, expected_value: str) -> bool:
        """Check if current token matches expected value."""
        token = self._current_token()
        if token and token[1] == expected_value:
            self._advance()
            return True
        return False
    
    def _parse_program(self) -> ASTNode:
        """Parse entire program."""
        root = ASTNode("PROGRAM", 0)
        
        while self._current_token():
            token_type, value, line = self._current_token()
            
            if value == 'PROGRAM':
                self._advance()
                # Skip program name
                if self._current_token() and self._current_token()[0] == 'IDENTIFIER':
                    self._advance()
            elif value in ['VAR', 'VAR_INPUT', 'VAR_OUTPUT']:
                var_node = self._parse_var_block()
                root.children.append(var_node)
            elif value == 'END_PROGRAM':
                break
            else:
                stmt_node = self._parse_statement()
                if stmt_node:
                    root.children.append(stmt_node)
        
        return root
    
    def _parse_var_block(self) -> ASTNode:
        """Parse VAR block."""
        token = self._current_token()
        var_type = token[1]
        line = token[2]
        self._advance()
        
        node = ASTNode(var_type, line)
        
        # Parse until END_VAR
        while self._current_token():
            if self._current_token()[1] == 'END_VAR':
                self._advance()
                break
            self._advance()
        
        return node
    
    def _parse_statement(self) -> Optional[ASTNode]:
        """Parse a statement."""
        token = self._current_token()
        if not token:
            return None
        
        token_type, value, line = token
        
        if value == 'IF':
            return self._parse_if_statement()
        elif value == 'FOR':
            return self._parse_for_loop()
        elif value == 'WHILE':
            return self._parse_while_loop()
        elif value == 'REPEAT':
            return self._parse_repeat_loop()
        elif value == 'CASE':
            return self._parse_case_statement()
        elif token_type == 'IDENTIFIER':
            return self._parse_assignment()
        else:
            self._advance()
            return None
    
    def _parse_if_statement(self) -> ASTNode:
        """Parse IF...THEN...ELSE...END_IF."""
        line = self._current_token()[2]
        self._advance()  # Skip 'IF'
        
        node = ASTNode("IF", line)
        
        # Parse condition
        condition = self._parse_expression()
        node.children.append(condition)
        
        self._expect('THEN')
        
        # Parse THEN block
        then_block = ASTNode("THEN_BLOCK", line)
        while self._current_token() and self._current_token()[1] not in ['ELSE', 'ELSIF', 'END_IF']:
            stmt = self._parse_statement()
            if stmt:
                then_block.children.append(stmt)
        node.children.append(then_block)
        
        # Parse ELSIF blocks
        while self._current_token() and self._current_token()[1] == 'ELSIF':
            self._advance()
            elsif_condition = self._parse_expression()
            self._expect('THEN')
            elsif_block = ASTNode("ELSIF_BLOCK", line)
            elsif_block.children.append(elsif_condition)
            while self._current_token() and self._current_token()[1] not in ['ELSE', 'ELSIF', 'END_IF']:
                stmt = self._parse_statement()
                if stmt:
                    elsif_block.children.append(stmt)
            node.children.append(elsif_block)
        
        # Parse ELSE block
        if self._current_token() and self._current_token()[1] == 'ELSE':
            self._advance()
            else_block = ASTNode("ELSE_BLOCK", line)
            while self._current_token() and self._current_token()[1] != 'END_IF':
                stmt = self._parse_statement()
                if stmt:
                    else_block.children.append(stmt)
            node.children.append(else_block)
        
        self._expect('END_IF')
        self._expect(';')
        
        return node
    
    def _parse_for_loop(self) -> ASTNode:
        """Parse FOR...TO...DO...END_FOR."""
        line = self._current_token()[2]
        self._advance()  # Skip 'FOR'
        
        node = ASTNode("FOR", line)
        
        # Parse: counter := start TO end [BY step]
        counter_name = self._current_token()[1]
        node.value = {'counter': counter_name}
        self._advance()
        
        self._expect(':=')
        start_expr = self._parse_expression()
        node.children.append(start_expr)
        
        self._expect('TO')
        end_expr = self._parse_expression()
        node.children.append(end_expr)
        
        # Optional BY step
        if self._current_token() and self._current_token()[1] == 'BY':
            self._advance()
            step_expr = self._parse_expression()
            node.children.append(step_expr)
        else:
            # Default step = 1
            node.children.append(ASTNode("LITERAL", line, value=1))
        
        self._expect('DO')
        
        # Parse loop body
        body = ASTNode("LOOP_BODY", line)
        while self._current_token() and self._current_token()[1] != 'END_FOR':
            stmt = self._parse_statement()
            if stmt:
                body.children.append(stmt)
        node.children.append(body)
        
        self._expect('END_FOR')
        self._expect(';')
        
        return node
    
    def _parse_while_loop(self) -> ASTNode:
        """Parse WHILE...DO...END_WHILE."""
        line = self._current_token()[2]
        self._advance()  # Skip 'WHILE'
        
        node = ASTNode("WHILE", line)
        
        # Parse condition
        condition = self._parse_expression()
        node.children.append(condition)
        
        self._expect('DO')
        
        # Parse loop body
        body = ASTNode("LOOP_BODY", line)
        while self._current_token() and self._current_token()[1] != 'END_WHILE':
            stmt = self._parse_statement()
            if stmt:
                body.children.append(stmt)
        node.children.append(body)
        
        self._expect('END_WHILE')
        self._expect(';')
        
        return node
    
    def _parse_repeat_loop(self) -> ASTNode:
        """Parse REPEAT...UNTIL...END_REPEAT."""
        line = self._current_token()[2]
        self._advance()  # Skip 'REPEAT'
        
        node = ASTNode("REPEAT", line)
        
        # Parse loop body
        body = ASTNode("LOOP_BODY", line)
        while self._current_token() and self._current_token()[1] != 'UNTIL':
            stmt = self._parse_statement()
            if stmt:
                body.children.append(stmt)
        node.children.append(body)
        
        self._expect('UNTIL')
        
        # Parse condition
        condition = self._parse_expression()
        node.children.append(condition)
        
        self._expect('END_REPEAT')
        self._expect(';')
        
        return node
    
    def _parse_case_statement(self) -> ASTNode:
        """Parse CASE...OF...END_CASE."""
        line = self._current_token()[2]
        self._advance()  # Skip 'CASE'
        
        node = ASTNode("CASE", line)
        
        # Parse selector expression
        selector = self._parse_expression()
        node.children.append(selector)
        
        self._expect('OF')
        
        # Parse case branches
        while self._current_token() and self._current_token()[1] != 'END_CASE':
            token = self._current_token()
            if token[0] == 'NUMBER' or token[0] == 'IDENTIFIER':
                case_value = ASTNode("CASE_VALUE", token[2], value=token[1])
                self._advance()
                self._expect(':')
                
                case_body = ASTNode("CASE_BODY", token[2])
                case_body.children.append(case_value)
                
                # Parse statements until next case or END_CASE
                while self._current_token():
                    next_token = self._current_token()
                    if next_token[1] in ['END_CASE'] or (next_token[0] == 'NUMBER' and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1][1] == ':'):
                        break
                    stmt = self._parse_statement()
                    if stmt:
                        case_body.children.append(stmt)
                
                node.children.append(case_body)
            else:
                self._advance()
        
        self._expect('END_CASE')
        self._expect(';')
        
        return node
    
    def _parse_assignment(self) -> ASTNode:
        """Parse assignment statement."""
        line = self._current_token()[2]
        var_name = self._current_token()[1]
        self._advance()
        
        node = ASTNode("ASSIGNMENT", line, value={'variable': var_name})
        
        self._expect(':=')
        
        # Parse right-hand side expression
        expr = self._parse_expression()
        node.children.append(expr)
        
        self._expect(';')
        
        return node
    
    def _parse_expression(self) -> ASTNode:
        """Parse expression (simplified - just captures tokens until delimiter)."""
        line = self._current_token()[2] if self._current_token() else 0
        node = ASTNode("EXPRESSION", line)
        
        tokens = []
        while self._current_token():
            token = self._current_token()
            if token[1] in ['THEN', 'DO', 'TO', 'BY', 'UNTIL', 'OF', ';', ':']:
                break
            tokens.append(token[1])
            self._advance()
        
        node.value = ' '.join(tokens)
        return node
    
    def parse_variables(self, code: str) -> Tuple[VariableScope, VariableScope, VariableScope, List[CompileError]]:
        """Extract variable declarations from ST code.
        
        Returns: (input_vars, output_vars, local_vars, errors)
        """
        input_vars = VariableScope()
        output_vars = VariableScope()
        local_vars = VariableScope()
        errors = []
        
        tokens = self.lexer.tokenize(code)
        i = 0
        
        while i < len(tokens):
            token_type, value, line = tokens[i]
            
            # Look for VAR blocks
            if token_type == 'KEYWORD':
                if value == 'VAR_INPUT':
                    i, block_vars, block_errors = self._parse_var_block_simple(tokens, i + 1)
                    input_vars.variables.extend(block_vars)
                    errors.extend(block_errors)
                elif value == 'VAR_OUTPUT':
                    i, block_vars, block_errors = self._parse_var_block_simple(tokens, i + 1)
                    output_vars.variables.extend(block_vars)
                    errors.extend(block_errors)
                elif value == 'VAR':
                    i, block_vars, block_errors = self._parse_var_block_simple(tokens, i + 1)
                    local_vars.variables.extend(block_vars)
                    errors.extend(block_errors)
                else:
                    i += 1
            else:
                i += 1
        
        return input_vars, output_vars, local_vars, errors
    
    def _parse_var_block_simple(self, tokens: List[Tuple[str, str, int]], start: int) -> Tuple[int, List[PLCVariable], List[CompileError]]:
        """Parse a VAR...END_VAR block."""
        variables = []
        errors = []
        i = start
        
        while i < len(tokens):
            token_type, value, line = tokens[i]
            
            if token_type == 'KEYWORD' and value == 'END_VAR':
                return i + 1, variables, errors
            
            # Expect: identifier : type [ := initial_value ] ;
            if token_type == 'IDENTIFIER':
                var_name = value
                i += 1
                
                # Expect colon
                if i >= len(tokens) or tokens[i][1] != ':':
                    errors.append(CompileError(line, 0, f"Expected ':' after variable name '{var_name}'"))
                    i += 1
                    continue
                i += 1
                
                # Expect type
                if i >= len(tokens) or tokens[i][0] != 'TYPE':
                    errors.append(CompileError(line, 0, f"Expected type for variable '{var_name}'"))
                    i += 1
                    continue
                
                var_type_str = tokens[i][1]
                try:
                    var_type = PLCDataType[var_type_str]
                except KeyError:
                    errors.append(CompileError(line, 0, f"Unknown type '{var_type_str}'"))
                    var_type = PLCDataType.INT
                i += 1
                
                # Optional initial value
                initial_value = None
                if i < len(tokens) and tokens[i][1] == ':=':
                    i += 1
                    if i < len(tokens) and tokens[i][0] == 'NUMBER':
                        initial_value = self._convert_value(tokens[i][1], var_type)
                        i += 1
                
                # Expect semicolon
                if i >= len(tokens) or tokens[i][1] != ';':
                    errors.append(CompileError(line, 0, f"Expected ';' after variable declaration"))
                else:
                    i += 1
                
                variables.append(PLCVariable(
                    name=var_name,
                    data_type=var_type,
                    initial_value=initial_value
                ))
            else:
                i += 1
        
        return i, variables, errors
    
    def _convert_value(self, value_str: str, data_type: PLCDataType) -> Any:
        """Convert string value to appropriate Python type."""
        try:
            if data_type == PLCDataType.BOOL:
                return value_str.upper() in ['TRUE', '1']
            elif data_type in [PLCDataType.REAL, PLCDataType.LREAL]:
                return float(value_str)
            elif 'INT' in data_type.value:
                return int(value_str)
            else:
                return value_str
        except:
            return None


class STCompiler:
    """Structured Text compiler with control flow support."""
    
    def __init__(self):
        self.parser = STParser()
    
    def compile(self, program: PLCProgram) -> CompileResult:
        """Compile ST program with control flow and validation."""
        errors = []
        warnings = []
        
        # Parse variable declarations
        input_vars, output_vars, local_vars, parse_errors = self.parser.parse_variables(program.source_code)
        errors.extend(parse_errors)
        
        # Update program variable scopes
        program.input_variables = input_vars
        program.output_variables = output_vars
        program.local_variables = local_vars
        
        # Parse AST for control flow analysis
        ast, ast_errors = self.parser.parse(program.source_code)
        errors.extend(ast_errors)
        
        # Validate control flow structures
        self._validate_ast(ast, errors, warnings)
        
        # Basic syntax validation
        lines = program.source_code.split('\n')
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Check for common syntax errors
            if ':=' in line_stripped and ';' not in line_stripped and 'FOR' not in line_stripped:
                warnings.append(CompileError(
                    line_num, 0, 
                    "Assignment statement should end with ';'",
                    severity="WARNING"
                ))
            
            # Check balanced parentheses
            if line_stripped.count('(') != line_stripped.count(')'):
                errors.append(CompileError(
                    line_num, 0,
                    "Unbalanced parentheses"
                ))
        
        # Generate enhanced bytecode with AST metadata
        if not errors:
            bytecode_data = {
                'source': program.source_code,
                'ast': self._ast_to_dict(ast),
                'version': '2.0'
            }
            import json
            bytecode = json.dumps(bytecode_data).encode('utf-8')
        else:
            bytecode = None
        
        return CompileResult(
            success=len(errors) == 0,
            bytecode=bytecode,
            warnings=warnings,
            errors=errors
        )
    
    def _validate_ast(self, node: ASTNode, errors: List[CompileError], warnings: List[CompileError]) -> None:
        """Validate AST structure."""
        # Check for infinite loops without exit conditions
        if node.node_type == 'WHILE':
            if node.children and node.children[0].value == 'TRUE':
                warnings.append(CompileError(
                    node.line, 0,
                    "Potential infinite loop: WHILE TRUE without EXIT",
                    severity="WARNING"
                ))
        
        # Recursively validate children
        for child in node.children:
            self._validate_ast(child, errors, warnings)
    
    def _ast_to_dict(self, node: ASTNode) -> Dict:
        """Convert AST to dictionary for serialization."""
        return {
            'type': node.node_type,
            'line': node.line,
            'value': node.value,
            'children': [self._ast_to_dict(child) for child in node.children]
        }
