import re
from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict

ActionQualifier = Literal['N', 'S', 'R', 'L', 'D', 'P', 'P1', 'P0', 'DS', 'SL']

@dataclass
class SFCTransition:
    target: str
    condition: str
    priority: int
    full_text: str
    line_index: int
    block_end_index: int
    explicit_priority: bool = False

@dataclass
class SFCAction:
    qualifier: ActionQualifier
    text: str
    line_index: int
    time: Optional[str] = None

@dataclass
class SFCNode:
    id: str
    label: str
    type: Literal['init', 'step']
    value: Optional[int] = None
    actions: List[SFCAction] = field(default_factory=list)
    transitions: List[SFCTransition] = field(default_factory=list)
    step_start_line: int = -1
    step_end_line: int = -1

class SFCParser:
    """Parses IEC 61131-3 Structured Text to extract Sequential Function Chart (SFC) nodes."""
    
    @staticmethod
    def parse(code: str) -> List[SFCNode]:
        nodes: List[SFCNode] = []
        if not code:
            return nodes

        lines: List[str] = code.split('\n')
        state_names: Dict[str, str] = {}

        # 0. Detect which state variable name is used and initial-step heuristic
        initial_step_id: Optional[str] = None
        state_var_name = 'state'

        state_var_match = re.search(r'IF\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*STATE_\w+', code, re.IGNORECASE)
        if not state_var_match:
            state_var_match = re.search(r'([A-Za-z_][A-Za-z0-9_]*)\s*:=\s*STATE_\w+', code, re.IGNORECASE)
            
        if state_var_match:
            state_var_name = state_var_match.group(1)

        init_regex = re.compile(rf'IF\s+{state_var_name}\s*=\s*undefined\s+THEN\s+{state_var_name}\s*:=\s*(STATE_\w+)', re.IGNORECASE)
        init_match = init_regex.search(code)
        if init_match:
            initial_step_id = init_match.group(1)

        # 1. Find States Constants
        const_regex = re.compile(r'^\s*(STATE_\w+)\s*:\s*INT\s*:=\s*(\d+);')
        
        for line in lines:
            match = const_regex.match(line)
            if match:
                state_id = match.group(1)
                state_val_str = match.group(2)
                state_names[state_id] = state_val_str
                nodes.append(SFCNode(
                    id=state_id,
                    label=state_id.replace('STATE_', ''),
                    value=int(state_val_str),
                    type='init' if initial_step_id == state_id else 'step'
                ))

        if not initial_step_id:
            var_init_re = re.compile(rf'^\s*{state_var_name}\s*:\s*INT\s*:=\s*(\d+);', re.IGNORECASE | re.MULTILINE)
            var_init_match = var_init_re.search(code)
            if var_init_match:
                init_val = int(var_init_match.group(1))
                initial_node = next((n for n in nodes if n.value == init_val), None)
                if initial_node:
                    initial_node.type = 'init'
                    initial_step_id = initial_node.id

        if not nodes:
            return []

        # 2. Find Transitions & Actions Logic
        current_step: Optional[str] = None
        transition_priority_counter: int = 1
        if_depth: int = 0
        state_chain_depth: Optional[int] = None

        def close_current_step(end_line: int):
            nonlocal current_step, state_chain_depth
            if not current_step: return
            node = next((n for n in nodes if n.id == current_step), None)
            if node:
                node.step_end_line = max(node.step_start_line, end_line)
            current_step = None
            state_chain_depth = None

        i = 0
        while i < len(lines):
            line = lines[i]
            trimmed = line.strip()

            if not trimmed or trimmed == '(*' or trimmed == '*)':
                i += 1
                continue

            # Detect Step Block Start
            step_re = re.compile(rf'(?:IF|ELSIF)\s+{state_var_name}\s*=\s*(STATE_\w+)\s+THEN', re.IGNORECASE)
            step_match = step_re.match(trimmed)

            if step_match and current_step:
                close_current_step(i - 1)

            if step_match:
                current_step = step_match.group(1)
                transition_priority_counter = 1
                node = next((n for n in nodes if n.id == current_step), None)
                if node: node.step_start_line = i
                
                if state_chain_depth is None:
                    state_chain_depth = if_depth + (1 if trimmed.upper().startswith('IF ') else 0)  # type: ignore
                
                if trimmed.upper().startswith('IF '):
                    if_depth += 1  # type: ignore
                i += 1
                continue

            if current_step:
                node = next((n for n in nodes if n.id == current_step), None)
                if not node:
                    i += 1
                    continue

                # Inline transition
                inline_trans = re.match(rf'^(?:\(\*[\s\S]*?\*\)\s*)?IF\s+(.+)\s+THEN\s+{state_var_name}\s*:=\s*(STATE_\w+);\s*END_IF;', trimmed, re.IGNORECASE)
                if inline_trans and inline_trans.group(2) in state_names:
                    pri_match = re.search(r'\(\*\s*PRI(?:ORITY)?\s*:\s*(\d+)\s*\*\)', line, re.IGNORECASE)
                    if pri_match:
                        prio = int(pri_match.group(1))
                    else:
                        prio = int(transition_priority_counter)
                        transition_priority_counter = prio + 1  # type: ignore
                        
                    clean_cond = re.sub(r'\(\*.*?\*\)', '', inline_trans.group(1)).strip()
                    
                    t_prio: int = int(prio)
                    node.transitions.append(SFCTransition(
                        target=inline_trans.group(2),
                        condition=clean_cond,
                        priority=t_prio,
                        explicit_priority=bool(pri_match),
                        full_text=line,
                        line_index=i,
                        block_end_index=i
                    ))
                    i += 1
                    continue

                # Multiline transition
                trans_start_match = re.match(r'^IF\s+(.+)\s+THEN', trimmed, re.IGNORECASE)
                if trans_start_match:
                    target_state = ''
                    j = i
                    block_end = i
                    depth: int = 1
                    found_assign = False

                    while j < len(lines) - 1 and j < i + 20:
                        j += 1
                        next_trim: str = lines[j].strip()  # type: ignore
                        if re.match(r'^IF\s+', next_trim, re.IGNORECASE) and re.search(r'\bTHEN$', next_trim, re.IGNORECASE):
                            depth += 1
                        if re.match(r'^END_IF;$', next_trim, re.IGNORECASE):
                            depth -= 1

                        assign_match = re.search(rf'{state_var_name}\s*:=\s*(STATE_\w+)', next_trim, re.IGNORECASE)
                        if assign_match and depth >= 1:
                            found_assign = True
                            target_state = assign_match.group(1)

                        if depth == 0:
                            block_end = j
                            break

                    if found_assign and target_state in state_names:
                        block_lines = lines[i:block_end + 1]  # type: ignore
                        block_text: str = '\n'.join(block_lines)
                        pri_match = re.search(r'\(\*\s*PRI(?:ORITY)?\s*:\s*(\d+)\s*\*\)', block_text, re.IGNORECASE)
                        if pri_match:
                            prio = int(pri_match.group(1))
                        else:
                            prio = int(transition_priority_counter)
                            transition_priority_counter = prio + 1
                            
                        clean_cond = re.sub(r'\(\*.*?\*\)', '', trans_start_match.group(1)).strip()
                        
                        t_prio: int = int(prio)
                        node.transitions.append(SFCTransition(
                            target=target_state,
                            condition=clean_cond,
                            priority=t_prio,
                            explicit_priority=bool(pri_match),
                            full_text=block_text,
                            line_index=i,
                            block_end_index=block_end
                        ))
                        i = block_end
                        i += 1
                        continue

                # Direct assignment
                simple_assign = re.match(rf'^{state_var_name}\s*:=\s*(STATE_\w+)', trimmed, re.IGNORECASE)
                if simple_assign:
                    target = simple_assign.group(1)
                    if target in state_names:
                        prev = lines[i - 1].strip() if i > 0 else ''
                        block_text = f"{prev}\n{line}"
                        pri_match = re.search(r'\(\*\s*PRI(?:ORITY)?\s*:\s*(\d+)\s*\*\)', block_text, re.IGNORECASE)
                        if pri_match:
                            prio = int(pri_match.group(1))
                        else:
                            prio = int(transition_priority_counter)
                            transition_priority_counter = prio + 1  # type: ignore
                            
                        t_prio: int = int(prio)
                        node.transitions.append(SFCTransition(
                            target=target,
                            condition="TRUE",
                            priority=t_prio,
                            explicit_priority=bool(pri_match),
                            full_text=line,
                            line_index=i,
                            block_end_index=i
                        ))
                        i += 1
                        continue

                # Action parsing
                qual_regex = re.compile(r'^\(\*\s*Q:([A-Z0-9]+)(?:\s+T:([^ *]+))?\s*\*\)')
                is_qualifier_line = bool(qual_regex.match(trimmed))
                is_pure_comment = trimmed.startswith('(*') and not is_qualifier_line

                if (trimmed and not is_pure_comment and not trimmed.startswith('VAR') and
                    not trimmed.startswith('END_VAR') and 
                    not re.match(r'^(IF\b|ELSIF\b|ELSE\b|END_IF;?$|WHILE\b|END_WHILE;?$)', trimmed, re.IGNORECASE)):
                    
                    qualifier = 'N'
                    time = None
                    action_text = trimmed

                    qual_match = qual_regex.match(trimmed)
                    if qual_match:
                        qualifier = qual_match.group(1)
                        if qual_match.group(2):
                            time = qual_match.group(2)
                        action_text = qual_regex.sub('', trimmed).strip()

                    action_text = re.sub(r';$', '', action_text)
                    node.actions.append(SFCAction(qualifier=qualifier, text=action_text, line_index=i, time=time)) # type: ignore

            if re.match(r'^IF\b.*\bTHEN\s*$', trimmed, re.IGNORECASE):
                if_depth += 1
            if re.match(r'^END_IF;$', trimmed, re.IGNORECASE):
                if_depth = max(0, if_depth - 1)
                
                # Help Pyre2 infer string vs int
                _chain_depth = int(state_chain_depth) if state_chain_depth is not None else None  # type: ignore
                
                if current_step and _chain_depth is not None and if_depth < _chain_depth:
                    close_current_step(i - 1)
                    
            i += 1


        if current_step:
            close_current_step(len(lines) - 1)

        return nodes

    @staticmethod
    def generate_st(nodes: List[SFCNode], device_name: str = "Device") -> str:
        """
        Generates functional IEC 61131-3 Structured Text from a list of SFC nodes.
        Returns the full ST program code.
        """
        if not nodes:
            return ""

        lines = []
        lines.append(f"PROGRAM {device_name}_SFC")
        lines.append("VAR")
        
        # 1. State Constants
        valid_values: List[int] = [n.value for n in nodes if n.value is not None]  # type: ignore
        max_value: int = max(valid_values) if valid_values else -1  # type: ignore
        next_value: int = (max_value + 1) if max_value >= 0 else 0
        
        for node in nodes:
            if not node.id.startswith('STATE_'):
                node.id = f"STATE_{node.id}"
            
            if node.value is None:
                node.value = next_value
                next_value += 1  # type: ignore
                
            lines.append(f"    {node.id} : INT := {node.value};")
            
        lines.append("    state : INT;")
        lines.append("END_VAR")
        lines.append("")

        # 2. Initial state assignment logic
        init_node = next((n for n in nodes if n.type == 'init'), None)
        if init_node:
            lines.append(f"IF state = 0 THEN")
            lines.append(f"    state := {init_node.id};")
            lines.append(f"END_IF;")
            lines.append("")

        # 3. Transitions & Actions Logic
        for idx, node in enumerate(nodes):
            keyword = "IF" if idx == 0 else "ELSIF"
            lines.append(f"{keyword} state = {node.id} THEN")
            
            # Actions
            for action in node.actions:
                time_part = f" T:{action.time}" if action.time else ""
                lines.append(f"    (* Q:{action.qualifier}{time_part} *) {action.text};")
                
            if node.actions:
                lines.append("")
                
            # Transitions (sort by priority if explicit, otherwise order of appearance)
            sorted_trans = sorted(node.transitions, key=lambda t: t.priority)
            for t_idx, trans in enumerate(sorted_trans):
                t_keyword = "IF" if t_idx == 0 else "ELSIF"
                condition = trans.condition if trans.condition else "TRUE"
                
                # Optionally emit priority comment
                if trans.priority > 0 and trans.explicit_priority:
                     lines.append(f"    (* PRIORITY: {trans.priority} *)")
                     
                lines.append(f"    {t_keyword} {condition} THEN")
                lines.append(f"        state := {trans.target};")
                
            if sorted_trans:
                lines.append("    END_IF;")
                
            if not node.actions and not sorted_trans:
                lines.append("    ;")  # Empty statement block

        if nodes:
            lines.append("END_IF;")
            
        lines.append("")
        lines.append("END_PROGRAM")

        return "\n".join(lines)

