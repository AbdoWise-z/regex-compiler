import json
import graphviz
from NFA import NFA

class State:
    def __init__(self, state_id: str, is_final: bool = False):
        self.id : str = state_id
        self.is_final : bool = is_final
        self.transitions : dict[str, set[State]] = {} 

    def add_transition(self, action: str, state):
        if action not in self.transitions:
            self.transitions[action] = set()
        self.transitions[action].add(state)

class DFA_State:
    def __init__(self, nfa_states : set[State], is_final: bool = False):
        self.states : set[State] = nfa_states
        self.id : str = self.set_to_string()
        self.is_final : bool = is_final
        
    def set_to_string(self): # for printing and hashing
        """Build the name of this DFA state by concatenating names of included NFA states"""
        ids = {s.id for s in self.states}
        return " ".join(map(str, ids))
    
    def __hash__(self):
        return hash(self.id)  # Ensures identical DFA states are treated as the same key

    def __eq__(self, other):
        return isinstance(other, DFA_State) and self.id == other.id

class DFA:

    def __init__(self, json_file_path : str, minimized : bool):
        self.nfa : NFA = NFA()
        self.states : set[DFA_State] = set()
        self.start_state : DFA_State = None
        self.final_states : set[DFA_State] = set()
        self.actions : list[str] = []
        self.transitions : list[tuple[DFA_State, DFA_State, str]] = []   # set[(source_state, target_state, action)]
        self.__build(json_file_path, minimized)

    def __epsilon_closure(self, state : State) -> set[State]:
        """Find all states reachable from the given state via epsilon transitions"""
        all_states : set[State] = {state}
        stack : list[State] = [state]

        while stack:
            state = stack.pop()
            state = self.nfa.states[int(state.id[1:])]
            for action, targets in state.transitions.items():
                for target in targets:
                    if target not in all_states and action == "ε":
                        all_states.add(target)
                        stack.append(target)
        return all_states
    
    def __get_reachable_states(self, dfa_state : DFA_State, action : str) -> set[State]:
        """Find all reachable states from the given state given an action"""
        reachable_states : set[State] = set()

        # for each NFA state in current DFA state
        for nfa_state in dfa_state.states:
            curr_reachable_states : set[State] = None
            if action in nfa_state.transitions:
                curr_reachable_states = nfa_state.transitions[action]
                
                # for each state that can be reached from curr reaches states
                next_reachable_states : set[State] = set()
                for next_state in curr_reachable_states:
                    next_reachable_states |= self.__epsilon_closure(next_state) # append sets of states
                curr_reachable_states |= next_reachable_states # append sets of states

                reachable_states |= curr_reachable_states # append sets of states

        return reachable_states

    def __load_NFA_json(self, file_path):
        """Construct NFA states and transitions"""
        ### i assume here that states in json file are increasingly sorted ###
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Assign start state of NFA
        self.nfa.start_state = State(data["startingState"], False)

        # Creating NFA states
        for state_name, state_data in data.items():
            if state_name == "startingState":
                continue
            is_final = state_data["isTerminatingState"]
            current_state = State(state_name, is_final)
            self.nfa.states.append(current_state)
            if is_final:
                self.nfa.final_state = current_state # Assign final state of NFA
        
        # Adding NFA transitions
        for state_name, state_data in data.items():
            if state_name == "startingState":
                continue
            current_state : State = self.nfa.states[int(state_name[1:])]
            for action, targets in state_data.items():
                if action == "isTerminatingState":
                    continue
                if isinstance(targets, list):
                    for target in targets:
                        current_state.add_transition(action, self.nfa.states[int(target[1:])])
                else:
                    current_state.add_transition(action, self.nfa.states[int(targets[1:])])
                # Add actions
                if action != "ε": 
                    self.actions.append(action)

        # # debugging
        # for state in self.nfa.states:
        #     print("Curr State: ", state.id)
        #     for a, tgt_states in state.transitions.items():
        #         print("Action: ", a)
        #         for t in tgt_states:
        #             print("Target State: ", t.id)
        
    def __construct_DFA(self, json_file_path):

        self.__load_NFA_json(json_file_path)

        # Get start state of DFA
        self.start_state = DFA_State(self.__epsilon_closure(self.nfa.start_state))
        self.states.add(self.start_state)

        stack : list[DFA_State] = [self.start_state]
        # while there are DFA states
        while stack:
            curr_dfa_state = stack.pop()
            # for every action possible check if we can create a new DFA state
            for action in self.actions:
                new_dfa_state = DFA_State(self.__get_reachable_states(curr_dfa_state, action))

                if len(new_dfa_state.states) == 0: continue # empty state

                # create the new state if it is really "new" :v
                if not any(new_dfa_state.id == s.id for s in self.states):
                    self.states.add(new_dfa_state)
                    stack.append(new_dfa_state)
                    # check if it is a terminating state
                    if self.nfa.final_state in new_dfa_state.states:
                        self.final_states.add(new_dfa_state)

                # add transition between current state and new state (new state can be the current state)
                if (curr_dfa_state, new_dfa_state, action) not in self.transitions:
                    self.transitions.append((curr_dfa_state, new_dfa_state, action))

    def __create_transition_table(self) -> dict[DFA_State, dict[str, DFA_State]]:
        """Creates a transition table for every DFA state with every action possible"""
        transition_table : dict[DFA_State, dict[str, DFA_State]] = {}
        for (src_state, target_state, action) in self.transitions:
            if src_state not in transition_table:
                transition_table[src_state] = {}
            transition_table[src_state][action] = target_state

        # Add states that doesn't have actions 
        # as we handle actions that doesn't transition the state as actions that transit the state to a 'None' state
        for state in self.states:
            if state not in transition_table:
                transition_table[state] = {}

        return transition_table
    
    def __split_states(self, transition_table : dict[DFA_State, dict[str, DFA_State]]):
        state_to_group : dict[DFA_State, int] = {} # map every state to its group
        group_to_state : dict[int, set[DFA_State]] = {0 : set(), 1 : set()} # map every group to its states

        # Create first two groups (accepting, non accepting)
        for state in self.states:
            if state in self.final_states:  # accepting group
                state_to_group[state] = 1
                group_to_state[1].add(state)
            else:                           # non-accepting group
                state_to_group[state] = 0 
                group_to_state[0].add(state)

        num_of_groups = 2 # current number of groups
        non_accepting_group = group_to_state[0].copy()
        accepting_group = group_to_state[1].copy()
        # Stack to process every existing group
        stack : list[set[DFA_State]] = [non_accepting_group, accepting_group]
        # Split groups until no change
        while stack:
            # Process current group
            curr_states = stack.pop()
            # Get current representative of this group (first one or anyone, doesn't matter)
            curr_representative = list(curr_states)[0]
            new_states : set[DFA_State] = set() # set of states that should be splitted to another group
            # For each action possible    
            for action in self.actions:
                # Get what group representative goes to and check if all other states are the same
                curr_target = transition_table[curr_representative].get(action, None)
                target_group = None
                if curr_target:
                    target_group = state_to_group[curr_target]
                # For every state in the current group check if they should be splitted
                for state in curr_states:
                    target_state = transition_table[state].get(action, None)
                    group = state_to_group[state]
                    # if current action transits both the representative and the current state to 'None' state, then no split required
                    if (curr_target == None or target_state == None) and target_state == curr_target:
                        continue
                    # states goes to different groups, Split them to a new group and update group/state maps
                    if target_state == None or state_to_group[target_state] != target_group:
                        # Add this state to a new group
                        new_states.add(state)
                        # Update its group id
                        state_to_group[state] = num_of_groups
                        # Remove it from the current group
                        group_to_state[group].remove(state)
                        # Add it to its new group
                        if num_of_groups not in group_to_state:
                            group_to_state[num_of_groups] = set()
                        group_to_state[num_of_groups].add(state)

            # Remove states that should be splitted from current group
            curr_states = set([s for s in curr_states if s not in new_states])
            # If we made a split add new group and modified curr group to the stack to process them again
            if len(new_states) > 0: 
                stack.append(curr_states)
                stack.append(new_states)
                num_of_groups += 1 # we have one more group

        return state_to_group, group_to_state

    def __group_to_state(self, group : set[DFA_State]):
        """Convert a group (set of DFA states) to a single DFA state 
            by just concatenating the ids of all NFA states in every DFA state in the group
        """
        all_nfa_states = set()
        is_final = False
        is_start = False
        for dfa_state in group:
            if dfa_state == self.start_state:
                is_start = True

            if dfa_state in self.final_states:
                is_final = True

            all_nfa_states |= dfa_state.states

        new_dfa_state = DFA_State(all_nfa_states, is_final)

        if is_start:
            self.start_state = new_dfa_state

        return new_dfa_state      

    def __update_transitions(self, state_to_group : dict[DFA_State, int], group_to_state : dict[int, set[DFA_State]], transition_table : dict[DFA_State, dict[str, DFA_State]]):
        # Clear the DFA to create the new 'minimizaed' states
        self.states = set()
        # List of new transitions between new 'minimized' states
        new_transitions : list[tuple[DFA_State, DFA_State, str]] = []
        # Process old transitions and map every old DFA state to its group then create a new DFA state for the whole group
        # For every old transition
        for (src_state, target_state, action) in self.transitions:
            # Get source state group and convert it to a DFA state
            src_group = state_to_group[src_state]
            src = group_to_state[src_group]
            src = self.__group_to_state(src)

            # Get target state group and convert it to a DFA state
            target_group = state_to_group[target_state]
            target = group_to_state[target_group]
            target = self.__group_to_state(target)

            # Add new states to the DFA
            self.states.add(src)
            self.states.add(target)

            # Add final states
            if src.is_final: 
                self.final_states.add(src)

            # Add start state
            if target.is_final: 
                self.final_states.add(target)
            # Add the new transition (source group, target group, action)
            if (src, target, action) not in new_transitions:
                new_transitions.append((src, target, action))
                
        # Update transitions
        self.transitions = new_transitions

    def __min_to_json(self, file_path):
        """Convert the DFA to a JSON representation"""
        result = {}

        # Add starting state
        if self.start_state:
            result["startingState"] = self.start_state.id

        # Process transitions
        for (src_state, target_state, action) in self.transitions:
            if src_state.id not in result:
                result[src_state.id] = {}
                result[src_state.id]["isTerminatingState"] = src_state.is_final
            result[src_state.id][action] = target_state.id
                    
        # Save to a json file
        with open(file_path, 'w') as f:
            json.dump(result, f, indent=2)

    def __minimize_DFA(self):
        transition_table = self.__create_transition_table()
        state_to_group, group_to_state = self.__split_states(transition_table)
        self.__update_transitions(state_to_group, group_to_state, transition_table)
        self.__min_to_json("min_DFA.json")
            
    def __to_dot(self, regex_str = None):
        """Convert the DFA to a Graphviz DOT representation for visualization"""
        dot = graphviz.Digraph(comment='DFA')

        # Set graph to display horizontally
        dot.attr(rankdir='LR')
        
        # Add all states
        for state in self.states:
            if state in self.final_states:
                dot.node(state.id, shape='doublecircle', style='filled', fillcolor='lightgray')
            elif state == self.start_state:
                dot.node(state.id, shape='circle', style='filled', fillcolor='lightblue')
            else:
                dot.node(state.id, shape='circle')

        # Add start indicator
        if self.start_state:
            dot.node('start', '', shape='point')
            dot.edge('start', self.start_state.id)

        # Add all transitions
        for src_state, target_state, action in self.transitions:
            dot.edge(src_state.id,
                        target_state.id,
                        label=action,
                        color='green',
            )

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
    
    def __build(self, json_file_path : str, minimized : bool):
        self.__construct_DFA(json_file_path)
        if minimized:
            self.__minimize_DFA()

    def render_to_file(self, filename='dfa', format='png', regex_str=None):
            """Render the DFA to a file"""
            dot = self.__to_dot(regex_str)
            dot.render(filename, format=format, cleanup=True)
            return dot

if __name__ == "__main__":
    # Example usage
    regex_str = "[bc]*(cd)+"

    dfa = DFA(json_file_path= "nfa.json", minimized= False)
    min_dfa = DFA(json_file_path="nfa.json", minimized= True)
    
    # Visualize the DFA
    try:
        dot = dfa.render_to_file('dfa_visualization', regex_str=regex_str, format='svg')
        print("DFA visualization saved as 'dfa_visualization.svg'")
        dot = min_dfa.render_to_file('min_dfa_visualization', regex_str=regex_str, format='svg')
        print("DFA visualization saved as 'min_dfa_visualization.svg'")
    except Exception as e:
        print(f"Could not create visualization: {e}")
        


