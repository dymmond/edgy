from lilya.exceptions import HTTPException
from lilya.requests import Request
from lilya.responses import JSONResponse

from edgy.contrib.admin.backend.crud import (
    create_object,
    delete_object,
    list_objects,
    retrieve_object,
    update_object,
)
from edgy.contrib.admin.backend.registry import get_model_by_name, get_registered_models
from edgy.contrib.admin.backend.schemas import get_model_schema


async def model_schema(model_name: str) -> JSONResponse:
    model = get_model_by_name(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not registered")
    return JSONResponse(get_model_schema(model))

async def list_registered_models() -> JSONResponse:
    models = get_registered_models()
    return JSONResponse({"models": list(models.keys())})

async def list_all(model_name: str, request: Request) -> JSONResponse:
    return await list_objects(request, model_name)


async def create(model_name: str, request: Request) -> JSONResponse:
    return await create_object(request, model_name)


async def retrieve(model_name: str, pk: str, request: Request) -> JSONResponse:
    return await retrieve_object(request, model_name, pk)


async def update(model_name: str, pk: str, request: Request) -> JSONResponse:
    return await update_object(request, model_name, pk)


async def delete(model_name: str, pk: str, request: Request) -> JSONResponse:
    return await delete_object(request, model_name, pk)
