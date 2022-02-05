from typing import Optional, Union, Callable, Type, TypeVar, Any
from sanic import Request

F = TypeVar('F', bound=Callable[..., Any])

# noinspection PyUnusedLocal
def validate(
    json: Optional[Union[Callable[[Request], bool], Type[object]]] = None,
    form: Optional[Union[Callable[[Request], bool], Type[object]]] = None,
    query: Optional[Union[Callable[[Request], bool], Type[object]]] = None,
    body_argument: str = "body",
    query_argument: str = "query",
) -> Callable[[F], F]:
    ...