from enum import Enum
from typing import Optional

class NodeType(Enum):
    Root = 0
    Char = 1
    Group = 2
    CharacterSet = 3
    Range = 4
    Any = 5
    UNKNOWN = -1

class ExprNode:
    type:   NodeType
    value: Optional[str]
    params: dict[str, any]
    children: list[list['ExprNode']]

    def __init__(self, type: NodeType = None, value: Optional[str] = None):
        self.type = type
        self.value = value
        self.children = []
        self.params = {}



PARAM_ONE_OR_ZERO = '?'
PARAM_ONE_OR_MORE = '+'
PARAM_ANY_OR_MORE = '*'
PARAM_RANGE_START = 'start'
PARAM_RANGE_END   = 'end'

QUANTIFIES = ['?', '+', '*']
SPECIAL_CHARS = ['(', ')', '[', '|', '?', '+' , '*']

class RegularCompiler:
    ast: ExprNode
    expr_str: str
    _position: int

    def __init__(self, expr_str: str):
        self.expr_str = expr_str
        self._position = 0
        self.ast = self._parse(NodeType.Root)
        self.ast.type = NodeType.Root


    def _eat(self, char: Optional[str] = None) -> bool:
        if self._position >= len(self.expr_str):
            return False

        if char is None:
            self._position = self._position + 1
            return True

        for i in range(len(char)):
            if self.expr_str[self._position + i] != char[i]:
                return False
        self._position = self._position + 1
        return True


    def _peak(self, offset: int = 0) -> Optional[str]:
        if self._position + offset >= len(self.expr_str):
            return None
        return self.expr_str[self._position + offset]

    def _done(self):
        return self._position >= len(self.expr_str)

    def _parse(self, curr_type: NodeType = None) -> ExprNode:
        if curr_type == NodeType.Root or curr_type == NodeType.Group:
            return self._parseGroup(is_root=curr_type == NodeType.Root)
        elif curr_type == NodeType.CharacterSet:
            return self._parseSet()
        elif curr_type == NodeType.Char:
            return self._parseChar()
        elif curr_type == NodeType.Any:
            return self._parseAny()
        elif curr_type == NodeType.Range:
            return self._parseRange()
        else:
            raise Exception('Unknown node type')

    def _assignQuantifier(self, node: ExprNode):
        if self._eat(PARAM_ONE_OR_ZERO):
            node.params['quantifier'] = PARAM_ONE_OR_ZERO
        elif self._eat(PARAM_ONE_OR_MORE):
            node.params['quantifier'] = PARAM_ONE_OR_MORE
        elif self._eat(PARAM_ANY_OR_MORE):
            node.params['quantifier'] = PARAM_ANY_OR_MORE

    def _parseGroup(self, is_root: bool = False) -> ExprNode:
        curr_node = ExprNode()
        curr_node.type = NodeType.Group
        curr_node.children.append([])
        curr_or = 0
        while not self._done():
            if self._eat('('): # being of a group
                node = self._parse(NodeType.Group)
                curr_node.children[curr_or].append(node)
                if not self._eat(')'):
                    raise Exception(f'Expected ")" at position {self._position}')
                self._assignQuantifier(node)

            elif self._peak() == ')': # end of group
                if is_root:
                    raise Exception(f'Unexpected "{self._peak()}" at position {self._position}')
                break

            elif self._eat('['): # Characters set
                node = self._parse(NodeType.CharacterSet)
                curr_node.children[curr_or].append(node)
                if not self._eat(']'):
                    raise Exception(f'Expected "]" at position {self._position}')
                self._assignQuantifier(node)

            elif self._peak() == '\\': # match next char
                self._eat()
                node = self._parse(NodeType.Char)
                curr_node.children[curr_or].append(node)
                self._assignQuantifier(node)

            elif self._peak() == '.': # match any char
                node = self._parse(NodeType.Any)
                curr_node.children[curr_or].append(node)
                self._assignQuantifier(node)

            elif self._peak() == '|': # logical or
                self._eat('|')
                curr_node.children.append([])
                curr_or = curr_or + 1

            elif self._peak() not in SPECIAL_CHARS: # normal char
                node = self._parse(NodeType.Char)
                curr_node.children[curr_or].append(node)
                self._assignQuantifier(node)
            else:
                raise Exception(f'Unexpected "{self._peak()}" at position {self._position}')

        return curr_node

    def _parseChar(self) -> ExprNode:
        top = self._peak()
        self._eat(top)
        node = ExprNode()
        node.type = NodeType.Char
        node.value = top
        return node

    def _parseAny(self):
        # same as in _parseChar, I wanted a special function so that I can set
        # node.value = None (or rather, not set it), so that I can be able to
        # identify normal "." char from a "wildcard"
        self._eat('.')
        node = ExprNode()
        node.type = NodeType.Any
        return node

    def _parseSet(self):
        # a set node is just a group node, but we add elements vertically instead of
        # adding them horizontally, also, it can only contain to subtypes: char and range
        curr_node = ExprNode()
        curr_node.type = NodeType.CharacterSet
        next_escape = False
        while not self._done():
            if self._peak() is None:
                raise Exception(f'Unexpected end of expression at position {self._position}')

            if self._peak() == '\\':
                self._eat(None)
                next_escape = True
                continue

            if next_escape:
                next_escape = False
                node = self._parse(NodeType.Range)
                if node is not None:
                    curr_node.children.append([node])
                else:
                    node = self._parse(NodeType.Char)
                    if node is None:
                        raise Exception(f'Unexpected "{self._peak()}" at position {self._position}')
                    curr_node.children.append([node])
            else:
                if self._peak() == ']':
                    break
                node = self._parse(NodeType.Range)
                if node is not None:
                    curr_node.children.append([node])
                else:
                    node = self._parse(NodeType.Char)
                    if node is None:
                        raise Exception(f'Unexpected "{self._peak()}" at position {self._position}')
                    curr_node.children.append([node])
        return curr_node

    def _parseRange(self):
        curr_node = ExprNode()
        curr_node.type = NodeType.Range
        if self._peak(1) == '-' and self._peak(2) is not None:
            start = self._peak(0)
            end = self._peak(2)
            self._eat(None); self._eat(None); self._eat(None)
            start = ord(start)
            end = ord(end)
            if start > end:
                raise Exception(f'Expected start > end at position {self._position}')
            curr_node.params[PARAM_RANGE_START] = start
            curr_node.params[PARAM_RANGE_END] = end
        else:
            return None
        return curr_node




if __name__ == "__main__":
    test = "a|b|c|d"
    re = RegularCompiler(test)
    print("ok")