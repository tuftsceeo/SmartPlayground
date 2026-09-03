"""
Sync-to-async AST transform for wand game modules.

Converts blocking MicroPython game/lib code into awaitable form so the
blocking `while True: ... time.sleep_ms(...)` game loops can run on the
browser main thread without freezing the tab.

Applied at load time to game modules AND to verbatim libs (leds, buzzer)
because those also sleep internally (flash, beep, fade_shape).
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import time as _time


# ---------------------------------------------------------------------------
# Runtime helpers injected into transformed module namespaces
# ---------------------------------------------------------------------------

class SimTimeout(Exception):
    """Raised when transformed code runs too long without yielding."""


_YIELD_EVERY = 64
_TIMEOUT_S = 2.0

_aw_calls = 0
_last_yield = _time.monotonic()
_busy_start = None


def reset_watchdog():
    global _aw_calls, _last_yield, _busy_start
    _aw_calls = 0
    _last_yield = _time.monotonic()
    _busy_start = None


async def _aw(value):
    """Await *value* if it is awaitable; otherwise pass it through.

    Forces an event-loop yield every N calls so the UI stays responsive,
    and raises SimTimeout if wall-clock time spent without a meaningful
    sleep (await that takes >=1ms) exceeds _TIMEOUT_S.
    """
    global _aw_calls, _last_yield, _busy_start

    now = _time.monotonic()
    if _busy_start is None:
        _busy_start = now
    elif now - _busy_start > _TIMEOUT_S:
        raise SimTimeout(
            "game loop ran >%.1fs without sleeping — likely a busy loop"
            % _TIMEOUT_S
        )

    if inspect.isawaitable(value):
        t0 = _time.monotonic()
        result = await value
        elapsed = _time.monotonic() - t0
        # Only real sleeps / blocking awaits reset the busy timer.
        # Instant async functions (transformed no-ops) do not.
        if elapsed >= 0.001:
            now = _time.monotonic()
            _busy_start = now
            _last_yield = now
            _aw_calls = 0
        else:
            _aw_calls += 1
            if _aw_calls >= _YIELD_EVERY:
                _aw_calls = 0
                await asyncio.sleep(0)
                _last_yield = _time.monotonic()
        return result

    _aw_calls += 1
    if _aw_calls >= _YIELD_EVERY:
        _aw_calls = 0
        await asyncio.sleep(0)
        _last_yield = _time.monotonic()

    return value


class _SimMeta(type):
    """Metaclass that awaits an async __init__.

    Injected onto classes whose __init__ was converted to async. Call sites
    are already wrapped in `await _aw(...)`, so construction resolves
    transparently.
    """

    async def __call__(cls, *args, **kwargs):
        obj = cls.__new__(cls)
        if isinstance(obj, cls):
            init = getattr(type(obj), "__init__", None)
            if init is not object.__init__:
                result = init(obj, *args, **kwargs)
                if inspect.isawaitable(result):
                    await result
        return obj


# Known-sync callees: skip _aw wrapping for these (optional fast path).
_SYNC_BUILTINS = frozenset({
    "len", "int", "float", "str", "bool", "bytes", "bytearray", "list",
    "dict", "set", "tuple", "range", "enumerate", "zip", "map", "filter",
    "min", "max", "sum", "abs", "round", "sorted", "reversed", "any", "all",
    "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
    "type", "id", "hash", "repr", "hex", "bin", "oct", "chr", "ord",
    "print", "iter", "next", "callable", "super", "property", "staticmethod",
    "classmethod", "object", "Exception", "ValueError", "TypeError",
    "RuntimeError", "OSError", "KeyError", "IndexError", "AttributeError",
    "StopIteration", "NotImplementedError",
})

_SYNC_MODULES = frozenset({
    "math", "random", "struct", "json", "sys", "gc", "array", "collections",
    "binascii", "hashlib", "re", "io", "errno",
})


# ---------------------------------------------------------------------------
# AST transformer
# ---------------------------------------------------------------------------

def _is_property_decorator(node):
    """True if *node* has @property or @x.setter / @x.deleter."""
    for d in node.decorator_list:
        if isinstance(d, ast.Name) and d.id == "property":
            return True
        if isinstance(d, ast.Attribute) and d.attr in ("setter", "deleter", "getter"):
            return True
    return False


def _has_yield(node):
    """True if the function body contains yield / yield from."""
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            # Don't look into nested defs — they get their own decision.
            # But walk() descends into everything; we need a smarter check.
            pass
        if isinstance(child, (ast.Yield, ast.YieldFrom)):
            # Make sure the yield belongs to this function, not a nested one.
            return True
    # More precise: only yields directly in this function's body tree,
    # not inside nested FunctionDef/Lambda/ClassDef.
    return _has_yield_in_body(node)


def _has_yield_in_body(node):
    class Finder(ast.NodeVisitor):
        def __init__(self):
            self.found = False
            self._depth = 0

        def visit_FunctionDef(self, n):
            if self._depth == 0:
                self._depth += 1
                self.generic_visit(n)
                self._depth -= 1
            # else: nested — skip

        def visit_AsyncFunctionDef(self, n):
            if self._depth == 0:
                self._depth += 1
                self.generic_visit(n)
                self._depth -= 1

        def visit_Lambda(self, n):
            pass

        def visit_ClassDef(self, n):
            pass

        def visit_Yield(self, n):
            if self._depth == 1:
                self.found = True

        def visit_YieldFrom(self, n):
            if self._depth == 1:
                self.found = True

    f = Finder()
    f.visit(node)
    return f.found


def _is_exception_base(base):
    """Heuristic: does this ClassDef base look like an Exception subclass?"""
    if isinstance(base, ast.Name):
        return base.id.endswith(("Error", "Exception")) or base.id in (
            "Exception", "BaseException", "OSError", "Warning",
        )
    if isinstance(base, ast.Attribute):
        return base.attr.endswith(("Error", "Exception"))
    return False


def _callee_is_known_sync(call_node):
    """True if the call target is a known-sync builtin or stdlib method."""
    func = call_node.func
    if isinstance(func, ast.Name):
        return func.id in _SYNC_BUILTINS
    if isinstance(func, ast.Attribute):
        # math.sqrt, random.choice, etc.
        if isinstance(func.value, ast.Name) and func.value.id in _SYNC_MODULES:
            return True
    return False


class _Asyncify(ast.NodeTransformer):
    """Convert sync functions to async and wrap calls in await _aw(...)."""

    def __init__(self):
        self._async_depth = 0
        self._skip_wrap = 0  # >0 inside lambda / comprehension / defaults
        self._classes_needing_meta = set()  # class names that got async __init__

    # -- helpers ------------------------------------------------------------

    def _should_skip_function(self, node):
        name = node.name
        if name.startswith("__") and name.endswith("__") and name != "__init__":
            return True
        if _is_property_decorator(node):
            return True
        if _has_yield_in_body(node):
            return True
        return False

    def _wrap_call(self, node):
        """Wrap a Call node in await _aw(...), unless known-sync."""
        if _callee_is_known_sync(node):
            return node
        return ast.Await(
            value=ast.Call(
                func=ast.Name(id="_aw", ctx=ast.Load()),
                args=[node],
                keywords=[],
            )
        )

    # -- visitors -----------------------------------------------------------

    def visit_FunctionDef(self, node):
        if self._should_skip_function(node):
            # Still visit nested functions.
            self._skip_wrap += 1
            node = self.generic_visit(node)
            self._skip_wrap -= 1
            return node

        # Convert to AsyncFunctionDef.
        new = ast.AsyncFunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=getattr(node, "type_comment", None),
        )
        # Preserve location info.
        ast.copy_location(new, node)
        if hasattr(node, "lineno"):
            new.lineno = node.lineno
            new.col_offset = node.col_offset

        # Transform defaults / decorators WITHOUT wrapping (sync context).
        self._skip_wrap += 1
        new.decorator_list = [self.visit(d) for d in new.decorator_list]
        new.args = self.visit(new.args)
        if new.returns is not None:
            new.returns = self.visit(new.returns)
        self._skip_wrap -= 1

        # Transform body IN async scope.
        self._async_depth += 1
        new.body = [self.visit(stmt) for stmt in new.body]
        self._async_depth -= 1

        if new.name == "__init__":
            # Mark enclosing class — handled by visit_ClassDef via a flag
            # we set on a stack. Use a simple attribute.
            self._pending_async_init = True

        return new

    def visit_AsyncFunctionDef(self, node):
        # Already async — still wrap calls in body.
        self._skip_wrap += 1
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args = self.visit(node.args)
        if node.returns is not None:
            node.returns = self.visit(node.returns)
        self._skip_wrap -= 1

        self._async_depth += 1
        node.body = [self.visit(stmt) for stmt in node.body]
        self._async_depth -= 1
        return node

    def visit_Lambda(self, node):
        self._skip_wrap += 1
        node = self.generic_visit(node)
        self._skip_wrap -= 1
        return node

    def visit_ListComp(self, node):
        self._skip_wrap += 1
        node = self.generic_visit(node)
        self._skip_wrap -= 1
        return node

    def visit_SetComp(self, node):
        self._skip_wrap += 1
        node = self.generic_visit(node)
        self._skip_wrap -= 1
        return node

    def visit_DictComp(self, node):
        self._skip_wrap += 1
        node = self.generic_visit(node)
        self._skip_wrap -= 1
        return node

    def visit_GeneratorExp(self, node):
        self._skip_wrap += 1
        node = self.generic_visit(node)
        self._skip_wrap -= 1
        return node

    def visit_arguments(self, node):
        # Defaults are evaluated at def time — always skip wrapping.
        self._skip_wrap += 1
        node = self.generic_visit(node)
        self._skip_wrap -= 1
        return node

    def visit_Call(self, node):
        # Transform children first (so chained calls get inner wrap first).
        node = self.generic_visit(node)
        if self._async_depth > 0 and self._skip_wrap == 0:
            return self._wrap_call(node)
        return node

    def visit_ClassDef(self, node):
        prev = getattr(self, "_pending_async_init", False)
        self._pending_async_init = False

        # Visit bases / keywords / decorators outside async scope.
        self._skip_wrap += 1
        node.bases = [self.visit(b) for b in node.bases]
        node.keywords = [self.visit(k) for k in node.keywords]
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        self._skip_wrap -= 1

        # Visit body — methods set their own async depth.
        # Class-level statements (assignments) stay sync: _async_depth == 0.
        node.body = [self.visit(stmt) for stmt in node.body]

        needs_meta = self._pending_async_init
        self._pending_async_init = prev

        if needs_meta:
            # Don't inject onto Exception subclasses.
            if any(_is_exception_base(b) for b in node.bases):
                return node
            # Don't overwrite an existing metaclass.
            if any(kw.arg == "metaclass" for kw in node.keywords):
                return node
            node.keywords.append(
                ast.keyword(arg="metaclass", value=ast.Name(id="_SimMeta", ctx=ast.Load()))
            )
            self._classes_needing_meta.add(node.name)

        return node


def transform_source(source, filename="<game>"):
    """Transform MicroPython source into async form.

    Returns (transformed_source: str, tree: ast.Module).
    """
    tree = ast.parse(source, filename=filename)
    transformer = _Asyncify()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    # Python 3.8+: type_ignores
    try:
        new_tree = ast.fix_missing_locations(new_tree)
    except Exception:
        pass
    return ast.unparse(new_tree), new_tree


def transform_and_compile(source, filename="<game>"):
    """Transform and compile. Returns a code object."""
    _src, tree = transform_source(source, filename=filename)
    return compile(tree, filename, "exec")


def runtime_namespace():
    """Return the dict of helpers to inject into a transformed module."""
    return {
        "_aw": _aw,
        "_SimMeta": _SimMeta,
        "SimTimeout": SimTimeout,
        "reset_watchdog": reset_watchdog,
    }
