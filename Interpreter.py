import requests
import sys
import time
from RT_result import *
from Tokens import *
from Lexer import *
from Parser import *
from Errors import *
class CustomListEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, List) or isinstance(obj, Dict):
            return obj.elements
        elif isinstance(obj, String) or isinstance(obj, Number):
            return obj.value
        return super().default(obj)
# Wait for all threads to complete
if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))
ser = ""
connected = False
# INTERPRETER

class Interpreter:
    def visit(self, node, context):
        method_name = f'visit_{type(node).__name__}'
        method = getattr(self, method_name, self.no_visit_method)
        return method(node, context)

    def no_visit_method(self, node, context):
        raise Exception(f'No visit_{type(node).__name__} method defined')

    ###################################

    def visit_NumberNode(self, node, context):
        return RTResult().success(
            Number(node.tok.value).set_context(context).set_pos(node.pos_start, node.pos_end)
        )

    def visit_StringNode(self, node, context):
        return RTResult().success(
            String(node.tok.value).set_context(context).set_pos(node.pos_start, node.pos_end)
        )

    def visit_ListNode(self, node, context):
        res = RTResult()
        elements = []

        for element_node in node.element_nodes:
            elements.append(res.register(self.visit(element_node, context)))
            if res.should_return(): return res

        return res.success(
            List(elements).set_context(context).set_pos(node.pos_start, node.pos_end)
        )

    def visit_VarAccessNode(self, node, context):
        res = RTResult()
        var_name = node.var_name_tok.value
        value = context.symbol_table.get(var_name)

        if not value:
            return res.failure(RTError(
                node.pos_start, node.pos_end,
                f"'{var_name}' is not defined",
                context
            ))

        value = value.copy().set_pos(node.pos_start, node.pos_end).set_context(context)
        return res.success(value)

    def visit_VarAssignNode(self, node, context):
        res = RTResult()
        var_name = node.var_name_tok.value
        value = res.register(self.visit(node.value_node, context))
        if res.should_return(): return res

        context.symbol_table.set(var_name, value)
        return res.success(value)

    def visit_BinOpNode(self, node, context):
        global error, result
        res = RTResult()
        left = res.register(self.visit(node.left_node, context))
        if res.should_return(): return res
        right = res.register(self.visit(node.right_node, context))
        if res.should_return(): return res

        if node.op_tok.type == TT_PLUS:
            result, error = left.added_to(right)
        elif node.op_tok.type == TT_MINUS:
            result, error = left.subbed_by(right)
        elif node.op_tok.type == TT_MUL:
            result, error = left.multed_by(right)
        elif node.op_tok.type == TT_DIV:
            result, error = left.dived_by(right)
        elif node.op_tok.type == TT_POW:
            result, error = left.powed_by(right)
        elif node.op_tok.type == TT_EE:
            result, error = left.get_comparison_eq(right)
        elif node.op_tok.type == TT_NE:
            result, error = left.get_comparison_ne(right)
        elif node.op_tok.type == TT_LT:
            result, error = left.get_comparison_lt(right)
        elif node.op_tok.type == TT_GT:
            result, error = left.get_comparison_gt(right)
        elif node.op_tok.type == TT_LTE:
            result, error = left.get_comparison_lte(right)
        elif node.op_tok.type == TT_GTE:
            result, error = left.get_comparison_gte(right)
        elif node.op_tok.matches(TT_KEYWORD, 'and'):
            result, error = left.anded_by(right)
        elif node.op_tok.matches(TT_KEYWORD, 'or'):
            result, error = left.ored_by(right)

        if error:
            return res.failure(error)
        else:
            return res.success(result.set_pos(node.pos_start, node.pos_end))

    def visit_UnaryOpNode(self, node, context):
        res = RTResult()
        number = res.register(self.visit(node.node, context))
        if res.should_return(): return res

        error = None

        if node.op_tok.type == TT_MINUS:
            number, error = number.multed_by(Number(-1))
        elif node.op_tok.matches(TT_KEYWORD, 'not'):
            number, error = number.notted()

        if error:
            return res.failure(error)
        else:
            return res.success(number.set_pos(node.pos_start, node.pos_end))

    def visit_IfNode(self, node, context):
        res = RTResult()

        for condition, expr, should_return_null in node.cases:
            condition_value = res.register(self.visit(condition, context))
            if res.should_return(): return res

            if condition_value.is_true():
                expr_value = res.register(self.visit(expr, context))
                if res.should_return(): return res
                return res.success(Number.null if should_return_null else expr_value)

        if node.else_case:
            expr, should_return_null = node.else_case
            expr_value = res.register(self.visit(expr, context))
            if res.should_return():
                return res
            return res.success(Number.null if should_return_null else expr_value)

        return res.success(Number.null)

    def visit_DictNode(self, node, context):
        res = RTResult()
        elements = {}

        for key_node, value_node in node.key_value_pairs:
            key = res.register(self.visit(key_node, context))
            if res.should_return(): return res

            value = res.register(self.visit(value_node, context))
            if res.should_return(): return res

            elements[key.value] = value

        return res.success(Dict(elements))
    def visit_ForNode(self, node, context):
        res = RTResult()
        elements = []

        start_value = res.register(self.visit(node.start_value_node, context))
        if res.should_return(): return res

        end_value = res.register(self.visit(node.end_value_node, context))
        if res.should_return(): return res

        if node.step_value_node:
            step_value = res.register(self.visit(node.step_value_node, context))
            if res.should_return(): return res
        else:
            step_value = Number(1)

        i = start_value.value

        if step_value.value >= 0:
            condition = lambda: i < end_value.value
        else:
            condition = lambda: i > end_value.value

        while condition():
            context.symbol_table.set(node.var_name_tok.value, Number(i))
            i += step_value.value

            value = res.register(self.visit(node.body_node, context))
            if res.should_return() and res.loop_should_continue == False and res.loop_should_break == False: return res

            if res.loop_should_continue:
                continue

            if res.loop_should_break:
                break

            elements.append(value)

        return res.success(
            Number.null if node.should_return_null else
            List(elements).set_context(context).set_pos(node.pos_start, node.pos_end)
        )

    def visit_WhileNode(self, node, context):
        res = RTResult()
        elements = []

        while True:
            condition = res.register(self.visit(node.condition_node, context))
            if res.should_return(): return res

            if not condition.is_true():
                break

            value = res.register(self.visit(node.body_node, context))
            if res.should_return() and res.loop_should_continue == False and res.loop_should_break == False: return res

            if res.loop_should_continue:
                continue

            if res.loop_should_break:
                break

            elements.append(value)

        return res.success(
            Number.null if node.should_return_null else
            List(elements).set_context(context).set_pos(node.pos_start, node.pos_end)
        )

    def visit_FuncDefNode(self, node, context):
        res = RTResult()

        func_name = node.var_name_tok.value if node.var_name_tok else None
        body_node = node.body_node
        arg_names = [arg_name.value for arg_name in node.arg_name_toks]
        func_value = Function(func_name, body_node, arg_names, node.should_auto_return).set_context(context).set_pos(
            node.pos_start, node.pos_end)

        if node.var_name_tok:
            context.symbol_table.set(func_name, func_value)

        return res.success(func_value)

    def visit_CallNode(self, node, context):
        res = RTResult()
        args = []

        value_to_call = res.register(self.visit(node.node_to_call, context))
        if res.should_return(): return res
        value_to_call = value_to_call.copy().set_pos(node.pos_start, node.pos_end)

        for arg_node in node.arg_nodes:
            args.append(res.register(self.visit(arg_node, context)))
            if res.should_return(): return res

        return_value = res.register(value_to_call.execute(args))
        if res.should_return(): return res
        return_value = return_value.copy().set_pos(node.pos_start, node.pos_end).set_context(context)
        return res.success(return_value)

    def visit_ReturnNode(self, node, context):
        res = RTResult()

        if node.node_to_return:
            value = res.register(self.visit(node.node_to_return, context))
            if res.should_return(): return res
        else:
            value = Number.null

        return res.success_return(value)

    def visit_ContinueNode(self, node, context):
        return RTResult().success_continue()

    def visit_BreakNode(self, node, context):
        return RTResult().success_break()



class Value:
    def __init__(self):
        self.set_pos()
        self.set_context()

    def set_pos(self, pos_start=None, pos_end=None):
        self.pos_start = pos_start
        self.pos_end = pos_end
        return self

    def set_context(self, context=None):
        self.context = context
        return self

    def added_to(self, other):
        return None, self.illegal_operation(other)

    def subbed_by(self, other):
        return None, self.illegal_operation(other)

    def multed_by(self, other):
        return None, self.illegal_operation(other)

    def dived_by(self, other):
        return None, self.illegal_operation(other)

    def powed_by(self, other):
        return None, self.illegal_operation(other)

    def get_comparison_eq(self, other):
        return None, self.illegal_operation(other)

    def get_comparison_ne(self, other):
        return None, self.illegal_operation(other)

    def get_comparison_lt(self, other):
        return None, self.illegal_operation(other)

    def get_comparison_gt(self, other):
        return None, self.illegal_operation(other)

    def get_comparison_lte(self, other):
        return None, self.illegal_operation(other)

    def get_comparison_gte(self, other):
        return None, self.illegal_operation(other)

    def anded_by(self, other):
        return None, self.illegal_operation(other)

    def ored_by(self, other):
        return None, self.illegal_operation(other)

    def notted(self, other):
        return None, self.illegal_operation(other)

    def execute(self, args):
        return RTResult().failure(self.illegal_operation())

    def copy(self):
        raise Exception('No copy method defined')

    def is_true(self):
        return False

    def illegal_operation(self, other=None):
        if not other: other = self
        return RTError(
            self.pos_start, other.pos_end,
            'Illegal operation',
            self.context
        )


class Number(Value):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def added_to(self, other):
        if isinstance(other, Number):
            return Number(self.value + other.value).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def subbed_by(self, other):
        if isinstance(other, Number):
            return Number(self.value - other.value).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def multed_by(self, other):
        if isinstance(other, Number):
            return Number(self.value * other.value).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def dived_by(self, other):
        if isinstance(other, Number):
            if other.value == 0:
                return None, RTError(
                    other.pos_start, other.pos_end,
                    'Division by zero',
                    self.context
                )

            return Number(self.value / other.value).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def powed_by(self, other):
        if isinstance(other, Number):
            return Number(self.value ** other.value).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def get_comparison_eq(self, other):
        if isinstance(other, Number):
            return Number(int(self.value == other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def get_comparison_ne(self, other):
        if isinstance(other, Number):
            return Number(int(self.value != other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def get_comparison_lt(self, other):
        if isinstance(other, Number):
            return Number(int(self.value < other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def get_comparison_gt(self, other):
        if isinstance(other, Number):
            return Number(int(self.value > other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def get_comparison_lte(self, other):
        if isinstance(other, Number):
            return Number(int(self.value <= other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def get_comparison_gte(self, other):
        if isinstance(other, Number):
            return Number(int(self.value >= other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def anded_by(self, other):
        if isinstance(other, Number):
            return Number(int(self.value and other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def ored_by(self, other):
        if isinstance(other, Number):
            return Number(int(self.value or other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def notted(self):
        return Number(1 if self.value == 0 else 0).set_context(self.context), None

    def copy(self):
        copy = Number(self.value)
        copy.set_pos(self.pos_start, self.pos_end)
        copy.set_context(self.context)
        return copy

    def is_true(self):
        return self.value != 0

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)


Number.null = Number(0)
Number.false = Number(0)
Number.true = Number(1)
Number.math_PI = Number(3.141592653589793)


class String(Value):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def added_to(self, other):
        if isinstance(other, String):
            return String(self.value + other.value).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def get_comparison_eq(self, other):
        if isinstance(other, String):
            return Number(int(self.value == other.value)).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def multed_by(self, other):
        if isinstance(other, Number):
            return String(self.value * other.value).set_context(self.context), None
        else:
            return None, Value.illegal_operation(self, other)

    def is_true(self):
        return len(self.value) > 0

    def dived_by(self, other):
        if isinstance(other, Number):
            try:
                return String(self.value[other.value]), None
            except:
                return None, RTError(
                    other.pos_start, other.pos_end,
                    'Element at this index could not be retrieved from list because index is out of bounds',
                    self.context
                )
        else:
            return None, Value.illegal_operation(self, other)

    def copy(self):
        copy = String(self.value)
        copy.set_pos(self.pos_start, self.pos_end)
        copy.set_context(self.context)
        return copy

    def __str__(self):
        return self.value

    def __repr__(self):
        return f'"{self.value}"'


class List(Value):
    def __init__(self, elements):
        super().__init__()
        self.elements = elements

    def added_to(self, other):
        new_list = self.copy()
        new_list.elements.append(other)
        return new_list, None

    def subbed_by(self, other):
        if isinstance(other, Number):
            new_list = self.copy()
            try:
                new_list.elements.pop(other.value)
                return new_list, None
            except:
                return None, RTError(
                    other.pos_start, other.pos_end,
                    'Element at this index could not be removed from list because index is out of bounds',
                    self.context
                )
        else:
            return None, Value.illegal_operation(self, other)

    def multed_by(self, other):
        if isinstance(other, List):
            new_list = self.copy()
            new_list.elements.extend(other.elements)
            return new_list, None
        else:
            return None, Value.illegal_operation(self, other)

    def dived_by(self, other):
        if isinstance(other, Number):
            try:
                return self.elements[other.value], None
            except:
                return None, RTError(
                    other.pos_start, other.pos_end,
                    'Element at this index could not be retrieved from list because index is out of bounds',
                    self.context
                )
        else:
            return None, Value.illegal_operation(self, other)

    def copy(self):
        copy = List(self.elements)
        copy.set_pos(self.pos_start, self.pos_end)
        copy.set_context(self.context)
        return copy

    def __str__(self):
        return ", ".join([str(x) for x in self.elements])

    def __repr__(self):
        return f'[{", ".join([repr(x) for x in self.elements])}]'


class Dict(Value):
    def __init__(self, elements):
        super().__init__()
        self.elements = elements

    def added_to(self, other):
        new_dict = self.copy()
        if isinstance(other, Dict):
            new_dict.elements.update(other.elements)
            return new_dict, None
        else:
            return None, Value.illegal_operation(self, other)

    def subbed_by(self, other):
        if isinstance(other, Dict):
            common_keys = list(set(self.elements.keys()) & set(other.elements.keys()))
            new_dict = {key: self.elements[key] for key in common_keys}
            return Dict(new_dict), None
        else:
            return None, Value.illegal_operation(self, other)

    def multed_by(self, other):
        if isinstance(other, Dict):
            common_keys = list(set(self.elements.keys()) & set(other.elements.keys()))
            new_dict = {key: [self.elements[key], other.elements[key]] for key in common_keys}
            return Dict(new_dict), None
        else:
            return None, Value.illegal_operation(self, other)

    def dived_by(self, other):
        if isinstance(other, String) or isinstance(other, Number):
            if isinstance(self.elements[other.value], List) or isinstance(self.elements[other.value], Dict) :
                value = self.elements[other.value]
                if isinstance(self.elements[other.value], List) : return List(value.elements), None
                else: return Dict(value.elements), None
            elif isinstance(self.elements[other.value], String) or isinstance(self.elements[other.value], Number):
                value = self.elements[other.value]
                return String(str(value)), None
        else:
            return None, Value.illegal_operation(self, other)

    def copy(self):
        copy = Dict(self.elements)
        copy.set_pos(self.pos_start, self.pos_end)
        copy.set_context(self.context)
        return copy

    def __str__(self):
        elements_str = [f"'{key}': {str(value)}" for key, value in self.elements.items()]
        return "{" + ", ".join(elements_str) + "}"

    def __repr__(self):
        return self.__str__()
class BaseFunction(Value):
    def __init__(self, name):
        super().__init__()
        self.name = name or "<anonymous>"

    def generate_new_context(self):
        new_context = Context(self.name, self.context, self.pos_start)
        new_context.symbol_table = SymbolTable(new_context.parent.symbol_table)
        return new_context

    def check_args(self, arg_names, args):
        res = RTResult()

        if len(args) > len(arg_names):
            return res.failure(RTError(
                self.pos_start, self.pos_end,
                f"{len(args) - len(arg_names)} too many args passed into {self}",
                self.context
            ))

        if len(args) < len(arg_names):
            return res.failure(RTError(
                self.pos_start, self.pos_end,
                f"{len(arg_names) - len(args)} too few args passed into {self}",
                self.context
            ))

        return res.success(None)

    def populate_args(self, arg_names, args, exec_ctx):
        for i in range(len(args)):
            arg_name = arg_names[i]
            arg_value = args[i]
            arg_value.set_context(exec_ctx)
            exec_ctx.symbol_table.set(arg_name, arg_value)

    def check_and_populate_args(self, arg_names, args, exec_ctx):
        res = RTResult()
        res.register(self.check_args(arg_names, args))
        if res.should_return(): return res
        self.populate_args(arg_names, args, exec_ctx)
        return res.success(None)


class Function(BaseFunction):
    def __init__(self, name, body_node, arg_names, should_auto_return):
        super().__init__(name)
        self.body_node = body_node
        self.arg_names = arg_names
        self.should_auto_return = should_auto_return

    def execute(self, args):
        res = RTResult()
        interpreter = Interpreter()
        exec_ctx = self.generate_new_context()

        res.register(self.check_and_populate_args(self.arg_names, args, exec_ctx))
        if res.should_return(): return res

        value = res.register(interpreter.visit(self.body_node, exec_ctx))
        if res.should_return() and res.func_return_value == None: return res

        ret_value = (value if self.should_auto_return else None) or res.func_return_value or Number.null
        return res.success(ret_value)

    def copy(self):
        copy = Function(self.name, self.body_node, self.arg_names, self.should_auto_return)
        copy.set_context(self.context)
        copy.set_pos(self.pos_start, self.pos_end)
        return copy

    def __repr__(self):
        return f"<function {self.name}>"


class BuiltInFunction(BaseFunction):
    def __init__(self, name):
        super().__init__(name)

    def execute(self, args):
        res = RTResult()
        exec_ctx = self.generate_new_context()

        method_name = f'execute_{self.name}'
        method = getattr(self, method_name, self.no_visit_method)

        res.register(self.check_and_populate_args(method.arg_names, args, exec_ctx))
        if res.should_return(): return res

        return_value = res.register(method(exec_ctx))
        if res.should_return(): return res
        return res.success(return_value)

    def no_visit_method(self, node, context):
        raise Exception(f'No execute_{self.name} method defined')

    def copy(self):
        copy = BuiltInFunction(self.name)
        copy.set_context(self.context)
        copy.set_pos(self.pos_start, self.pos_end)
        return copy

    def __repr__(self):
        return f"<built-in function {self.name}>"

    #####################################

    def execute_print(self, exec_ctx):
        if isinstance(exec_ctx.symbol_table.get('value'), List) or isinstance(exec_ctx.symbol_table.get('value'), Dict):
            print(exec_ctx.symbol_table.get('value').elements)
        else:
            print(str(exec_ctx.symbol_table.get('value').value))
        return RTResult().success(Number.null)

    execute_print.arg_names = ['value']

    def execute_print_ret(self, exec_ctx):
        return RTResult().success(String(str(exec_ctx.symbol_table.get('value'))))

    execute_print_ret.arg_names = ['value']

    def execute_input(self, exec_ctx):
        text = input()
        return RTResult().success(String(text))

    execute_input.arg_names = []

    def execute_input_int(self, exec_ctx):
        while True:
            text = input()
            try:
                number = int(text)
                break
            except ValueError:
                print(f"'{text}' must be an integer. Try again!")
        return RTResult().success(Number(number))

    execute_input_int.arg_names = []

    def execute_clear(self, exec_ctx):
        os.system('cls' if os.name == 'nt' else 'cls')
        return RTResult().success(Number.null)

    execute_clear.arg_names = []

    def execute_is_number(self, exec_ctx):
        is_number = isinstance(exec_ctx.symbol_table.get("value"), Number)
        return RTResult().success(Number.true if is_number else Number.false)

    execute_is_number.arg_names = ["value"]


    def execute_is_dict(self, exec_ctx):
        is_dict = isinstance(exec_ctx.symbol_table.get("value"), Dict)
        return RTResult().success(Number.true if is_dict else Number.false)

    execute_is_dict.arg_names = ["value"]

    def execute_is_string(self, exec_ctx):
        is_number = isinstance(exec_ctx.symbol_table.get("value"), String)
        return RTResult().success(Number.true if is_number else Number.false)

    execute_is_string.arg_names = ["value"]

    def execute_is_list(self, exec_ctx):
        is_number = isinstance(exec_ctx.symbol_table.get("value"), List)
        return RTResult().success(Number.true if is_number else Number.false)

    execute_is_list.arg_names = ["value"]

    def execute_is_function(self, exec_ctx):
        is_number = isinstance(exec_ctx.symbol_table.get("value"), BaseFunction)
        return RTResult().success(Number.true if is_number else Number.false)

    execute_is_function.arg_names = ["value"]

    def execute_append(self, exec_ctx):
        list_ = exec_ctx.symbol_table.get("list")
        value = exec_ctx.symbol_table.get("value")

        if not isinstance(list_, List):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "First argument must be list",
                exec_ctx
            ))

        list_.elements.append(value)
        return RTResult().success(Number.null)

    execute_append.arg_names = ["list", "value"]

    def execute_pop(self, exec_ctx):
        list_ = exec_ctx.symbol_table.get("list")
        index = exec_ctx.symbol_table.get("index")

        if not isinstance(list_, List):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "First argument must be list",
                exec_ctx
            ))

        if not isinstance(index, Number):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Second argument must be number",
                exec_ctx
            ))

        try:
            element = list_.elements.pop(index.value)
        except:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                'Element at this index could not be removed from list because index is out of bounds',
                exec_ctx
            ))
        return RTResult().success(element)

    execute_pop.arg_names = ["list", "index"]

    def execute_extend(self, exec_ctx):
        listA = exec_ctx.symbol_table.get("listA")
        listB = exec_ctx.symbol_table.get("listB")

        if not isinstance(listA, List):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "First argument must be list",
                exec_ctx
            ))

        if not isinstance(listB, List):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Second argument must be list",
                exec_ctx
            ))

        listA.elements.extend(listB.elements)
        return RTResult().success(Number.null)

    execute_extend.arg_names = ["listA", "listB"]

    def execute_len(self, exec_ctx):
        list_ = exec_ctx.symbol_table.get("list")
        if isinstance(list_, List):
            param = list_.elements
        elif isinstance(list_, String):
            param = list_.value
        else:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Argument must be list",
                exec_ctx
            ))

        return RTResult().success(Number(len(param)))

    execute_len.arg_names = ["list"]

    def execute_run(self, exec_ctx):
        fn = exec_ctx.symbol_table.get("fn")

        if not isinstance(fn, String):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Second argument must be string",
                exec_ctx
            ))

        fn = fn.value

        try:
            with open(fn, "r", encoding="UTF-8") as f:
                script = f.read()
        except Exception as e:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                f"Failed to load script \"{fn}\"\n" + str(e),
                exec_ctx
            ))

        _, error = run(fn, script)

        if error:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                f"Failed to finish executing script \"{fn}\"\n" +
                error.as_string(),
                exec_ctx
            ))

        return RTResult().success(Number.null)

    execute_run.arg_names = ["fn"]

    def execute_import(self, exec_ctx):
        fn = exec_ctx.symbol_table.get("fn")
        baseurl = "https://raw.githubusercontent.com/ZiadRabea/World-Programming/main/libs/"
        if not isinstance(fn, String):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Second argument must be string",
                exec_ctx
            ))

        fn = fn.value

        try:
            with open(f"{app_path}/libs/{fn}", "r", encoding="UTF-8") as f:
                script = f.read()
        except Exception as e:
            try:
                response = requests.get(f"{baseurl}{fn}")
                response.raise_for_status()  # Raise an exception for any unsuccessful request
                with open(f"{app_path}/libs/{fn}", "w", encoding="UTF-8") as f:
                    f.write(response.text)
                with open(f"{app_path}/libs/{fn}", "r", encoding="UTF-8") as f:
                    script = f.read()
            except requests.exceptions.RequestException as e:
                return RTResult().failure(RTError(
                    self.pos_start, self.pos_end,
                    f"Failed to load script \"{fn}\"\n" + str(e),
                    exec_ctx
                ))

        _, error = run(fn, script)

        if error:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                f"Failed to finish executing script \"{fn}\"\n" +
                error.as_string(),
                exec_ctx
            ))

        return RTResult().success(Number.null)

    execute_import.arg_names = ["fn"]

    def execute_readfile(self, exec_ctx):
        fn = exec_ctx.symbol_table.get("fn")
        if not isinstance(fn, String):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Second argument must be string",
                exec_ctx
            ))

        fn = fn.value

        if "https://" in fn or "http://" in fn:
            try:
                response = requests.get(fn)
                response.raise_for_status()  # Raise an exception for any unsuccessful request
                return RTResult().success(String(response.text))
            except requests.exceptions.RequestException as e:
                return RTResult().failure(RTError(
                    self.pos_start, self.pos_end,
                    f"Error occurred while fetching the file: \"{e}\"\n" + str(e),
                    exec_ctx
                ))

        try:
            with open(fn, "r", encoding="UTF-8") as f:
                content = f.read()
        except Exception as e:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                f"Failed to load file \"{fn}\"\n" + str(e),
                exec_ctx
            ))


        return RTResult().success(String(content))

    execute_readfile.arg_names = ["fn"]

    def execute_writefile(self, exec_ctx):
        fn = exec_ctx.symbol_table.get("fn")
        content = exec_ctx.symbol_table.get("content")

        if not isinstance(fn, String):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "First an Second argument must be string",
                exec_ctx
            ))

        fn = fn.value
        content = content.value
        try:
            with open(fn, "w", encoding="UTF-8") as f:
                content = f.write(content)
        except Exception as e:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                f"Failed to load file \"{fn}\"\n" + str(e),
                exec_ctx
            ))


        return RTResult().success(Number.null)

    execute_writefile.arg_names = ["fn", "content"]

    def execute_to_string(self, exec_ctx):
        content = exec_ctx.symbol_table.get("content")

        content = content.elements
        try:
            output = json.dumps(content, indent=4, cls=CustomListEncoder)
        except Exception as e:
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                f"Failed to parse data",
                exec_ctx
            ))


        return RTResult().success(String(output))

    execute_to_string.arg_names = ["content"]

    def execute_keys(self, exec_ctx):
        content = exec_ctx.symbol_table.get("dict")
        if not isinstance(content, Dict):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                f"Argument must be a Dict",
                exec_ctx
            ))
        content = content.elements
        mylist = list()
        for i in content.keys():
            if isinstance(i, int):
                mylist.append(Number(i))
            if isinstance(i, str):
                mylist.append(String(i))
            if isinstance(i, list):
                mylist.append(List(i))
            if isinstance(i, dict):
                mylist.append(Dict(i))

        return RTResult().success(List(mylist))

    execute_keys.arg_names = ["dict"]

    def execute_python(self, exec_ctx):
        exec(exec_ctx.symbol_table.get('code').value, locals())
        return RTResult().success(Number.null)
    execute_python.arg_names = ['code']

    def execute_abspath(self, exec_ctx):
        return RTResult().success(String(f"{app_path}"))
    execute_abspath.arg_names = []

    def execute_sum(self, exec_ctx):
        list_ = exec_ctx.symbol_table.get("list")

        if not isinstance(list_, List):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Argument must be list",
                exec_ctx
            ))

        newlist = [int(f"{i}") for i in list_.elements]
        return RTResult().success(Number(sum(newlist)))

    execute_sum.arg_names = ["list"]

    def execute_max(self, exec_ctx):
        list_ = exec_ctx.symbol_table.get("list")

        if not isinstance(list_, List):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Argument must be list",
                exec_ctx
            ))
        newlist = [int(f"{i}") for i in list_.elements]
        return RTResult().success(Number(max(newlist)))

    execute_max.arg_names = ["list"]

    def execute_min(self, exec_ctx):
        list_ = exec_ctx.symbol_table.get("list")

        if not isinstance(list_, List):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "Argument must be list",
                exec_ctx
            ))
        newlist = [int(f"{i}") for i in list_.elements]
        return RTResult().success(Number(min(newlist)))

    execute_min.arg_names = ["list"]

    def execute_abs(self, exec_ctx):
        result = abs(int(exec_ctx.symbol_table.get('number').value))
        return RTResult().success(Number(result))

    execute_abs.arg_names = ['number']

    def execute_int(self, exec_ctx):
        result = int(exec_ctx.symbol_table.get('number').value)
        return RTResult().success(Number(result))

    execute_int.arg_names = ['number']

    def execute_float(self, exec_ctx):
        result = float(exec_ctx.symbol_table.get('number').value)
        return RTResult().success(Number(result))

    execute_float.arg_names = ['number']

    def execute_str(self, exec_ctx):
        result = str(exec_ctx.symbol_table.get('number').value)
        return RTResult().success(String(result))

    execute_str.arg_names = ['number']

    def execute_eval(self, exec_ctx):
        result, error = run("<std-in>", exec_ctx.symbol_table.get('text').value)
        print(result)
        return RTResult().success(result.elements[0])

    execute_eval.arg_names = ['text']

    def execute_load_img(self, exec_ctx):
        print("It seems like you're using the educational of World Language, please make sure to download the practical version : https://cszido.github.io/worldlang")

        return RTResult().success(Number.null)

    execute_load_img.arg_names = ['path']

    def execute_save_img(self, exec_ctx):
        print("It seems like you're using the educational of World Language, please make sure to download the practical version : https://cszido.github.io/worldlang")

        return RTResult().success(Number.null)

    execute_save_img.arg_names = ['list', 'path']


    def execute_send(self, exec_ctx):
        print("It seems like you're using the educational of World Language, please make sure to download the practical version : https://cszido.github.io/worldlang")
        return RTResult().success(Number.null)

    execute_send.arg_names = ['com', 'port', 'data']

    def execute_exec(self, exec_ctx):
        code = exec_ctx.symbol_table.get('code')
        if not isinstance(code, String):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "code must be a string",
                exec_ctx
            ))
        run("<stdin>", code.value)
        return RTResult().success(Number.null)
    execute_exec.arg_names = ['code']

    def execute_sleep(self, exec_ctx):
        if not isinstance(exec_ctx.symbol_table.get('number'), Number):
            return RTResult().failure(RTError(
                self.pos_start, self.pos_end,
                "code must be a number",
                exec_ctx
            ))
        time.sleep(exec_ctx.symbol_table.get('number').value)
        return RTResult().success(Number.null)

    execute_sleep.arg_names = ['number']
    def execute_listen(self, exec_ctx):
        print("It seems like you're using the educational of World Language, please make sure to download the practical version : https://cszido.github.io/worldlang")

        return RTResult().success(Number.null)
    execute_listen.arg_names = []

    def execute_speak(self, exec_ctx):
        print("It seems like you're using the educational of World Language, please make sure to download the practical version : https://cszido.github.io/worldlang")
        return RTResult().success(Number.null)
    execute_speak.arg_names = ['text']


BuiltInFunction.print = BuiltInFunction("print")
BuiltInFunction.print_ret = BuiltInFunction("print_ret")
BuiltInFunction.input = BuiltInFunction("input")
BuiltInFunction.input_int = BuiltInFunction("input_int")
BuiltInFunction.clear = BuiltInFunction("clear")
BuiltInFunction.is_number = BuiltInFunction("is_number")
BuiltInFunction.is_string = BuiltInFunction("is_string")
BuiltInFunction.is_dict = BuiltInFunction("is_dict")
BuiltInFunction.is_list = BuiltInFunction("is_list")
BuiltInFunction.is_function = BuiltInFunction("is_function")
BuiltInFunction.append = BuiltInFunction("append")
BuiltInFunction.pop = BuiltInFunction("pop")
BuiltInFunction.extend = BuiltInFunction("extend")
BuiltInFunction.len = BuiltInFunction("len")
BuiltInFunction.sum = BuiltInFunction("sum")
BuiltInFunction.max = BuiltInFunction("max")
BuiltInFunction.min = BuiltInFunction("min")
BuiltInFunction.abs = BuiltInFunction("abs")
BuiltInFunction.run = BuiltInFunction("run")
BuiltInFunction.importfile = BuiltInFunction("import")
BuiltInFunction.readfile = BuiltInFunction("readfile")
BuiltInFunction.writefile = BuiltInFunction("writefile")
BuiltInFunction.python = BuiltInFunction("python")
BuiltInFunction.int = BuiltInFunction("int")
BuiltInFunction.str = BuiltInFunction("str")
BuiltInFunction.eval = BuiltInFunction("eval")
BuiltInFunction.float = BuiltInFunction("float")
BuiltInFunction.load_img = BuiltInFunction("load_img")
BuiltInFunction.save_img = BuiltInFunction("save_img")
BuiltInFunction.send = BuiltInFunction("send")
BuiltInFunction.exec = BuiltInFunction("exec")
BuiltInFunction.listen = BuiltInFunction("listen")
BuiltInFunction.speak = BuiltInFunction("speak")
BuiltInFunction.sleep = BuiltInFunction("sleep")
BuiltInFunction.to_string = BuiltInFunction("to_string")
BuiltInFunction.keys = BuiltInFunction("keys")
BuiltInFunction.abspath = BuiltInFunction("abspath")
# RUN

global_symbol_table = SymbolTable()
global_symbol_table.set(f"{data_dict['null']}", Number.null)
global_symbol_table.set(f"{data_dict['false']}", Number.false)
global_symbol_table.set(f"{data_dict['true']}", Number.true)
global_symbol_table.set("MATH_PI", Number.math_PI)
global_symbol_table.set(f"{data_dict['print']}", BuiltInFunction.print)
global_symbol_table.set("print_ret", BuiltInFunction.print_ret)
global_symbol_table.set(f"{data_dict['input']}", BuiltInFunction.input)
global_symbol_table.set(f"{data_dict['int_input']}", BuiltInFunction.input_int)
global_symbol_table.set(f"{data_dict['clear']}", BuiltInFunction.clear)
global_symbol_table.set("cls", BuiltInFunction.clear)
global_symbol_table.set(f"{data_dict['is_int']}", BuiltInFunction.is_number)
global_symbol_table.set(f"{data_dict['is_str']}", BuiltInFunction.is_string)
global_symbol_table.set(f"{data_dict['is_lst']}", BuiltInFunction.is_list)
global_symbol_table.set(f"{data_dict['is_func']}", BuiltInFunction.is_function)
global_symbol_table.set(f"{data_dict['append']}", BuiltInFunction.append)
global_symbol_table.set(f"{data_dict['pop']}", BuiltInFunction.pop)
global_symbol_table.set(f"{data_dict['extend']}", BuiltInFunction.extend)
global_symbol_table.set(f"{data_dict['len']}", BuiltInFunction.len)
global_symbol_table.set("world", BuiltInFunction.run)
global_symbol_table.set(f"{data_dict['import']}", BuiltInFunction.importfile)
global_symbol_table.set(f"{data_dict['readf']}", BuiltInFunction.readfile)
global_symbol_table.set(f"{data_dict['writef']}", BuiltInFunction.writefile)
global_symbol_table.set(f"python", BuiltInFunction.python)
global_symbol_table.set(f"{data_dict['sum']}", BuiltInFunction.sum)
global_symbol_table.set(f"{data_dict['max']}", BuiltInFunction.max)
global_symbol_table.set(f"{data_dict['min']}", BuiltInFunction.min)
global_symbol_table.set(f"{data_dict['abs']}", BuiltInFunction.abs)
global_symbol_table.set(f"{data_dict['int']}", BuiltInFunction.int)
global_symbol_table.set(f"{data_dict['float']}", BuiltInFunction.int)
global_symbol_table.set(f"{data_dict['str']}", BuiltInFunction.str)
global_symbol_table.set(f"{data_dict['load']}", BuiltInFunction.load_img)
global_symbol_table.set(f"{data_dict['save_img']}", BuiltInFunction.save_img)
global_symbol_table.set(f"{data_dict['send']}", BuiltInFunction.send)
global_symbol_table.set(f"{data_dict['exec']}", BuiltInFunction.exec)
global_symbol_table.set(f"{data_dict['listen']}", BuiltInFunction.listen)
global_symbol_table.set(f"{data_dict['speak']}", BuiltInFunction.speak)
global_symbol_table.set(f"{data_dict['eval']}", BuiltInFunction.eval)
global_symbol_table.set(f"{data_dict['is_dict']}", BuiltInFunction.is_dict)
global_symbol_table.set(f"{data_dict['sleep']}", BuiltInFunction.sleep)
global_symbol_table.set(f"{data_dict['to_string']}", BuiltInFunction.to_string)
global_symbol_table.set(f"{data_dict['keys']}", BuiltInFunction.keys)
global_symbol_table.set(f"{data_dict['abspath']}", BuiltInFunction.abspath)


def run(fn, text):
    # Generate tokens
    lexer = Lexer(fn, text)
    tokens, error = lexer.make_tokens()
    if error: return None, error

    # Generate AST
    parser = Parser(tokens)
    ast = parser.parse()
    if ast.error: return None, ast.error

    # Run program
    interpreter = Interpreter()
    context = Context('<program>')
    context.symbol_table = global_symbol_table
    result = interpreter.visit(ast.node, context)

    return result.value, result.error
