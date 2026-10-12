"""Every API route the app serves, wherever FastAPI keeps it.

From FastAPI 0.139 an included router stays one entry of `app.routes`, its routes
resolved when a request comes in, so a plain walk over `app.routes` finds only the two
the app declares itself. `iter_route_contexts` is FastAPI's own walk into the routers."""

from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts


def api_routes(app: FastAPI) -> list[APIRoute]:
    return [context.original_route for context in iter_route_contexts(app.routes)
            if isinstance(context.original_route, APIRoute)]
