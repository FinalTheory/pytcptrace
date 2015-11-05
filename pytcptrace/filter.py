import ply.lex as lex
import ply.yacc as yacc
from pygraphviz import AGraph
from random import random

__author__ = 'huangyan13@baidu.com'


def AST_DFS(node, g):
    if not node:
        node_name = str(random())[2:]
        g.add_node(node_name)
        g.get_node(node_name).attr['label'] = 'None'
        return node_name
    node_name = str(id(node))
    g.add_node(node_name)
    if node.is_leaf():
        g.get_node(node_name).attr['label'] = node.obj_name
    else:
        g.get_node(node_name).attr['label'] = node.operator
        g.add_edge(node_name, AST_DFS(node.left_expr, g))
        g.add_edge(node_name, AST_DFS(node.right_expr, g))
    return node_name


class ASTNode:
    def __init__(self, left_expr, operator, right_expr):
        self.left_expr = left_expr
        self.right_expr = right_expr
        self.operator = operator

    def get_operator(self):
        return self.operator

    def get_left(self):
        return self.left_expr

    def get_right(self):
        return self.right_expr

    def is_leaf(self):
        return False

    def show(self, filename='AST.png'):
        g = AGraph()
        g.graph_attr['label'] = 'AST'
        AST_DFS(self, g)
        g.layout(prog='dot')
        g.draw(filename)


class ASTLeaf:
    def __init__(self, obj_name):
        self.obj_name = obj_name

    def get_obj(self):
        return self.obj_name

    def is_leaf(self):
        return True

    def show(self, filename='AST.png'):
        g = AGraph()
        g.graph_attr['label'] = 'AST'
        AST_DFS(self, g)
        g.layout(prog='dot')
        g.draw(filename)

tokens = (
    'NAME',
    'OBJECT',
    'IPADDR',
    'NUMBER',
    'AND',
    'OR',
    'EQ',
    'NEQ',
    'GT',
    'LT',
)

literals = ['!', '(', ')', '>', '<']


# Tokens

t_NAME = r'[a-zA-Z0-9_]+'
t_OBJECT = t_NAME + r'(\.' + t_NAME + ')*'
t_ignore = " \t"
t_GT = r'>='
t_LT = r'<='
t_EQ = r'=='
t_NEQ = r'!='
t_AND = r'&&'
t_OR = r'\|\|'


def t_IPADDR(t):
    r'\d+\.\d+\.\d+\.\d+'
    for val in map(int, t.value.split('.')):
        if val > 255:
            raise ValueError("IP address out of range")
    return t


def t_NUMBER(t):
    r'\d+(\.\d*)?'
    if t.value.find('.') != -1:
        t.value = float(t.value)
    else:
        t.value = int(t.value)
    return t


def t_error(t):
    t.lexer.skip(1)
    raise RuntimeError("Illegal character '%s'" % t.value[0])


# Build the lexer
lex.lex()

# Parsing rules

precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('nonassoc', 'EQ', 'NEQ', 'GT', 'LT', '>', '<'),
    ('right', '!'),
)


def p_expression_obj(p):
    '''expression : OBJECT
                  | NUMBER
                  | IPADDR'''
    p[0] = ASTLeaf(p[1])


def p_expression_par(p):
    '''expression : '(' expression ')' '''
    p[0] = p[2]


def p_expression_operator(p):
    '''expression : expression AND expression
                  | expression OR expression
                  | expression EQ expression
                  | expression NEQ expression
                  | expression GT expression
                  | expression LT expression
                  | expression '>' expression
                  | expression '<' expression
                  | '!' expression'''
    if p[1] == '!':
        p[0] = ASTNode(None, p[1], p[2])
    else:
        p[0] = ASTNode(p[1], p[2], p[3])


def p_error(p):
    if p:
        raise RuntimeError("Syntax error at '%s'" % p.value)
    else:
        raise RuntimeError("Syntax error at EOF")


yacc.yacc()


def generate_filter(filter_expr):
    if not filter_expr:
        return None
    ast = yacc.parse(filter_expr)
    ast.show()
    return lambda conn: ast_eval(ast, conn)


def ast_eval(ast, connection):
    if ast.is_leaf():
        # string type data, might be:
        # 1. connection property
        # 2. ip address
        if isinstance(ast.obj_name, str):
            fields = ast.obj_name.split('.')
            if fields[0] == 'tcp':
                val = connection
                for field in fields[1:]:
                    val = val[field]
                return val[0] if isinstance(val, list) else val
            else:
                return ast.obj_name
        else:
            return ast.obj_name
    else:
        if ast.left_expr is None:
            return not ast_eval(ast.right_expr, connection)
        else:
            if ast.operator == '==':
                return ast_eval(ast.left_expr, connection) == ast_eval(ast.right_expr, connection)
            elif ast.operator == '!=':
                return ast_eval(ast.left_expr, connection) != ast_eval(ast.right_expr, connection)
            elif ast.operator == '>=':
                return ast_eval(ast.left_expr, connection) >= ast_eval(ast.right_expr, connection)
            elif ast.operator == '<=':
                return ast_eval(ast.left_expr, connection) <= ast_eval(ast.right_expr, connection)
            elif ast.operator == '>':
                return ast_eval(ast.left_expr, connection) > ast_eval(ast.right_expr, connection)
            elif ast.operator == '<':
                return ast_eval(ast.left_expr, connection) < ast_eval(ast.right_expr, connection)
            elif ast.operator == '&&':
                return ast_eval(ast.left_expr, connection) and ast_eval(ast.right_expr, connection)
            elif ast.operator == '||':
                return ast_eval(ast.left_expr, connection) or ast_eval(ast.right_expr, connection)
            else:
                raise RuntimeError("Unknown operator %s" % ast.operator)


if __name__ == '__main__':
    pcap_file = '/Users/baidu/Library/Caches/clion11/cmake/generated/b28c2630/b28c2630/Release/demo/test/data.pcap'
    from pytcptrace import TcpTrace
    fid = TcpTrace().open(pcap_file)
    generate_filter('tcp.data < 123')
