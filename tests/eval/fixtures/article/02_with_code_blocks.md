# Understanding Python Decorators

By Alice Smith — April 1, 2026

Python decorators are a powerful pattern for modifying or enhancing functions without
changing their source code. They are built on higher-order functions and closures, and
appear throughout the Python ecosystem in web frameworks, test libraries, and caching.

## Basic Decorator

A decorator is a function that takes another function and returns a new function:

```python
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Before the call")
        result = func(*args, **kwargs)
        print("After the call")
        return result
    return wrapper

@my_decorator
def say_hello(name: str) -> str:
    return f"Hello, {name}!"
```

## Decorator with Arguments

When you need to pass parameters, add an extra nesting level:

```python
def repeat(times: int):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(times):
                func(*args, **kwargs)
        return wrapper
    return decorator

@repeat(3)
def greet() -> None:
    print("Hello!")
```

## Preserving Metadata with functools.wraps

Always use `functools.wraps` to keep the wrapped function's `__name__` and docstring:

```python
import functools

def log_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
```

Mastering decorators is essential for idiomatic Python and unlocks most modern frameworks.
