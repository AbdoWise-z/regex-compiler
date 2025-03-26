from RegexCompiler import RegexCompiler, ExprNode, NodeType
import graphviz


class State:
    def __init__(self, state_id: int, is_final: bool = False):
        self.id = state_id
        self.is_final = is_final
        self.transitions = {}  # char -> Set[State]
        self.epsilon_transitions = set()  # Set[State]

    def add_transition(self, char: str, state):
        if char not in self.transitions:
            self.transitions[char] = set()
        self.transitions[char].add(state)

    def add_epsilon_transition(self, state):
        self.epsilon_transitions.add(state)


class NFA:
    def __init__(self, node: ExprNode = None):
        self.states = []
        self.start_state = None
        self.final_state = None
        self.next_state_id = 0
        self.final_states = set()  # Track all final states

        if node is not None:
            self._build_nfa(node)

    def create_state(self, is_final: bool = False) -> State:
        state = State(self.next_state_id, is_final)
        self.next_state_id += 1
        self.states.append(state)
        if is_final:
            self.final_states.add(state)
            self.final_state = state
        return state

    def set_start_state(self, state: State):
        self.start_state = state

    def add_final_state(self, state: State):
        state.is_final = True
        self.final_states.add(state)
        self.final_state = state

    def _build_nfa(self, node):
        if node.type == NodeType.Char:
            self._build_basic_node_char(node)
        elif node.type == NodeType.Any:
            self._build_basic_node_any(node)
        elif node.type == NodeType.CharacterSet:
            self._build_basic_node_set(node)
        elif node.type == NodeType.Range:
            self._build_basic_node_range(node)
        elif node.type == NodeType.Root or node.type == NodeType.Group:
            self._build_basic_node_group(node)

        # Apply quantifiers if present
        if 'quantifier' in node.params:
            self._apply_quantifier(node.params['quantifier'])

    def _build_basic_node_char(self, node):
        start = self.create_state()
        end = self.create_state(is_final=True)

        # to be able to distinguish between a '.' and a '\.'
        if node.value == '.':
            # "\\\\" instead of "\\" because the graphics library also tries to escape chars
            start.add_transition('\\\\.', end)
        else:
            start.add_transition(node.value, end)

        self.start_state = start
        self.final_state = end

    def _build_basic_node_any(self, node):
        start = self.create_state()
        end = self.create_state(is_final=True)

        # '.' matches any character
        start.add_transition('.', end)

        self.start_state = start
        self.final_state = end

    def _build_basic_node_range(self, node):
        start = self.create_state()
        end = self.create_state(is_final=True)

        # Add transitions for all characters in the range
        range_start = node.params['start']
        range_end = node.params['end']

        # for char_code in range(range_start, range_end + 1):
        #     start.add_transition(chr(char_code), end)

        start.add_transition(f"{chr(range_start)} - {chr(range_end)}", end)

        self.start_state = start
        self.final_state = end

    def _build_basic_node_set(self, node):
        # start = self.create_state()
        # end = self.create_state(is_final=True)
        #
        # # Process all children in the character set
        # # Not sure how to handle ranges here, so just adding a transition for the range itself
        # # also, I'm not sure how to connect elements of character set, so I'll assume they OR-gated instead of
        # # creating NFA for each then connecting them with epsilon transitions
        # for alternative in node.children:
        #     for child in alternative:
        #         if child.type == NodeType.Char:
        #             start.add_transition(child.value, end)
        #         elif child.type == NodeType.Range:
        #             range_start = child.params['start']
        #             range_end = child.params['end']
        #             # for char_code in range(range_start, range_end + 1):
        #             #     start.add_transition(chr(char_code), end)
        #             start.add_transition(f"{chr(range_start)} -> {chr(range_end)}", end)
        #
        # self.start_state = start
        # self.final_state = end
        # # the code above isn't wrong, but it will make the output not identical to the one
        # # in the lecture (will be more optimized heh, which certain "some people" won't like)
        # # so let's just embrace recursion and call it a day :)
        self._build_alternation(node.children)

    def _build_basic_node_group(self, node):
        if not node.children or not node.children[0]:
            # Empty group, create epsilon transition
            start = self.create_state()
            end = self.create_state(is_final=True)
            start.add_epsilon_transition(end)
            self.start_state = start
            self.final_state = end
            return

        # Handle alternation (|)
        if len(node.children) > 1:
            self._build_alternation(node.children)
        else:
            self._build_concatenation(node.children[0])

    def _build_concatenation(self, nodes):
        if not nodes:
            # Empty concatenation, create epsilon transition
            start = self.create_state()
            end = self.create_state(is_final=True)
            start.add_epsilon_transition(end)
            self.start_state = start
            self.final_state = end
            return

        # Build NFA for first node
        sub_nfas = []
        for node in nodes:
            sub_nfa = NFA(node)
            sub_nfas.append(sub_nfa)

        # Connect all sub-NFAs
        if not sub_nfas:
            return

        # Get all states from sub-NFAs
        all_states = []
        for sub_nfa in sub_nfas:
            all_states.extend(sub_nfa.states)

        # Update state IDs to avoid conflicts
        state_map = {}
        for state in all_states:
            new_state = State(self.next_state_id, state.is_final)
            self.next_state_id += 1
            state_map[state] = new_state
            self.states.append(new_state)

        # Copy transitions
        for old_state in all_states:
            new_state = state_map[old_state]

            # Copy char transitions
            for char, targets in old_state.transitions.items():
                for target in targets:
                    if target in state_map:
                        new_state.add_transition(char, state_map[target])

            # Copy epsilon transitions
            for target in old_state.epsilon_transitions:
                if target in state_map:
                    new_state.add_epsilon_transition(state_map[target])

        # Connect the sub-NFAs
        self.start_state = state_map[sub_nfas[0].start_state]

        for i in range(len(sub_nfas) - 1):
            old_final = sub_nfas[i].final_state
            old_next_start = sub_nfas[i + 1].start_state

            state_map[old_final].is_final = False
            state_map[old_final].add_epsilon_transition(state_map[old_next_start])

        self.final_state = state_map[sub_nfas[-1].final_state]
        self.final_states = {state_map[state] for state in state_map if state.is_final}

    def _build_alternation(self, alternatives):
        # Create start and end states
        start = self.create_state()
        end = self.create_state(is_final=True)

        # Build an NFA for each alternative
        for alternative in alternatives:
            if not alternative:
                # Empty alternative, add epsilon transition
                start.add_epsilon_transition(end)
                continue

            # Build a sub-NFA for this alternative
            sub_nfa = NFA()
            sub_nfa._build_concatenation(alternative)

            if not sub_nfa.start_state:
                continue

            # Create a mapping for states to avoid ID conflicts
            state_map = {}
            for state in sub_nfa.states:
                new_state = self.create_state(state.is_final)
                state_map[state] = new_state

            # Copy transitions
            for old_state in sub_nfa.states:
                new_state = state_map[old_state]

                # Copy char transitions
                for char, targets in old_state.transitions.items():
                    for target in targets:
                        if target in state_map:
                            new_state.add_transition(char, state_map[target])

                # Copy epsilon transitions
                for target in old_state.epsilon_transitions:
                    if target in state_map:
                        new_state.add_epsilon_transition(state_map[target])

            # Connect start to sub-NFA's start
            start.add_epsilon_transition(state_map[sub_nfa.start_state])

            # Connect sub-NFA's final states to end
            for old_state in sub_nfa.states:
                if old_state.is_final:
                    state_map[old_state].is_final = False
                    state_map[old_state].add_epsilon_transition(end)

        self.start_state = start
        self.final_state = end

    def _apply_quantifier(self, quantifier):
        if not self.start_state or not self.final_state:
            return

        # Save original start and final states
        original_start = self.start_state
        original_final = self.final_state

        # Create new start and final states
        new_start = self.create_state()
        new_final = self.create_state(is_final=True)

        # Remove final state flag from original final state
        original_final.is_final = False

        if quantifier == '?':  # Zero or one occurrence
            # Connect new_start to original_start and new_final
            new_start.add_epsilon_transition(original_start)
            new_start.add_epsilon_transition(new_final)

            # Connect original_final to new_final
            original_final.add_epsilon_transition(new_final)

        elif quantifier == '*':  # Zero or more occurrences
            # Connect new_start to original_start and new_final
            new_start.add_epsilon_transition(original_start)
            new_start.add_epsilon_transition(new_final)

            # Connect original_final to original_start and new_final
            original_final.add_epsilon_transition(new_start)
            original_final.add_epsilon_transition(new_final)

        elif quantifier == '+':  # One or more occurrences
            # Connect new_start to original_start
            new_start.add_epsilon_transition(original_start)

            # Connect original_final to original_start and new_final
            original_final.add_epsilon_transition(original_start)
            original_final.add_epsilon_transition(new_final)

        self.start_state = new_start
        self.final_state = new_final
        self.final_states = {state for state in self.states if state.is_final}

    def to_dot(self, regex_str=None):
        """Convert the NFA to a Graphviz DOT representation for visualization"""
        dot = graphviz.Digraph(comment='NFA')

        # Set graph to display horizontally
        dot.attr(rankdir='LR')
        # dot.attr(dpi="300")
        # dot.attr(ratio="1")
        # dot.attr(size="10,10", dpi="300")

        # Add start indicator
        if self.start_state:
            dot.node('start', '', shape='point')
            dot.edge('start', f"S{self.start_state.id}")

        # Add all states
        for state in self.states:
            node_id = f"S{state.id}"
            if state.is_final:
                dot.node(node_id, f"S{state.id}", shape='doublecircle', style='filled', fillcolor='lightgray')
            elif state == self.start_state:
                dot.node(node_id, f"S{state.id}", shape='circle', style='filled', fillcolor='lightblue')
            else:
                dot.node(node_id, f"S{state.id}", shape='circle')


        # Add all transitions
        for state in self.states:
            src_id = f"S{state.id}"

            # Add normal transitions
            for char, targets in state.transitions.items():
                for target in targets:
                    dot.edge(src_id,
                             f"S{target.id}",
                             label=char,
                             color='green',
                    )

            # Add epsilon transitions
            for target in state.epsilon_transitions:
                dot.edge(src_id, f"S{target.id}", label='ε', color='saddlebrown', fontcolor='saddlebrown')

        # Add the regex string at the bottom if provided
        if regex_str:
            escp = ""
            for char in regex_str:
                if char == '\\':
                    escp = escp + char * 2
                else:
                    escp = escp + char
            dot.attr(label=f"Regular Expression: {escp}")
            dot.attr(labelloc='b')  # Place label at bottom

        return dot

    def render_to_file(self, filename='nfa', format='png', regex_str=None):
        """Render the NFA to a file"""
        dot = self.to_dot(regex_str)
        dot.render(filename, format=format, cleanup=True)
        return dot

    def match(self, input_string):
        """Match input string against the NFA"""
        if not self.start_state:
            return False

        # Find all possible states reachable from start state via epsilon transitions
        current_states = self._epsilon_closure({self.start_state})

        # Process each character
        for char in input_string:
            next_states = set()

            # For each current state, find all next states via char transitions
            for state in current_states:
                for transition_char , targets in state.transitions.items():
                    # Handle '.' as wildcard and ranges, this is probably the ugliest way to do it, but it works :)
                    split = str(transition_char).split(" - ")
                    if (
                        transition_char == '.' or
                        transition_char == char or
                        (char == '.' and transition_char == '\\\\.') or
                        (len(split) == 2 and ord(split[0]) <= ord(char) <= ord(split[1]))
                    ):
                        next_states.update(targets)

            # Find epsilon closures for all next states
            current_states = self._epsilon_closure(next_states)

            # If we have no states left, matching fails
            if not current_states:
                return False

        # Check if any current state is a final state
        return any(state.is_final for state in current_states)

    def _epsilon_closure(self, states):
        """Find all states reachable from the given states via epsilon transitions"""
        all_states = set(states)
        stack = list(states)

        while stack:
            state = stack.pop()
            for target in state.epsilon_transitions:
                if target not in all_states:
                    all_states.add(target)
                    stack.append(target)

        return all_states

    def to_json(self):
        """Convert the NFA to a JSON representation"""
        result = {}

        # Add starting state
        if self.start_state:
            result["startingState"] = f"S{self.start_state.id}"

        # Add all states
        for state in self.states:
            state_id = f"S{state.id}"
            state_data = {
                "isTerminatingState": state.is_final
            }

            # Add regular transitions
            for char, targets in state.transitions.items():
                if len(targets) == 1:
                    target = next(iter(targets))
                    state_data[char] = f"S{target.id}"
                else:
                    state_data[char] = []
                    for target in targets:
                        state_data[char].append(f"S{target.id}")

                        # Add epsilon transitions
            for target in state.epsilon_transitions:
                # Use 'ε' as the key for epsilon transitions
                if 'ε' not in state_data:
                    state_data['ε'] = []
                state_data['ε'].append(f"S{target.id}")

            result[state_id] = state_data

        return result

    def save_json(self, filename='nfa.json'):
        """Save the NFA as a JSON file"""
        import json
        with open(filename, 'w') as f:
            json.dump(self.to_json(), f, indent=2)
        return filename


def regex_to_nfa(regex_str: str):
    """Convert a regular expression string to an NFA"""
    regex = RegexCompiler(regex_str)
    return NFA(regex.ast)


def match(regex_str: str, test_str: str):
    """Test if a string matches a regular expression"""
    nfa = regex_to_nfa(regex_str)
    return nfa.match(test_str)


if __name__ == "__main__":
    # Example usage
    regex_str = "[bc]*(cd)+"
    test_str = "abcdych"

    nfa = regex_to_nfa(regex_str)
    result = nfa.match(test_str)

    print(f"Regex: {regex_str}")
    print(f"Test string: {test_str}")
    print(f"Match result: {result}")

    # Visualize the NFA
    try:
        dot = nfa.render_to_file('nfa_visualization', regex_str=regex_str, format='svg')
        nfa.save_json()
        print("NFA visualization saved as 'nfa_visualization.svg'")
    except Exception as e:
        print(f"Could not create visualization: {e}")