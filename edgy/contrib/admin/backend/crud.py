from lilya.exceptions import HTTPException
from lilya.requests import Request
from lilya.responses import JSONResponse

from edgy.contrib.admin.backend.registry import get_model_by_name


async def list_objects(request: Request, model_name: str) -> JSONResponse:
    model = get_model_by_name(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not registered")

    objects = await model.query.all()
    return JSONResponse([obj.dict() for obj in objects])


async def create_object(request: Request, model_name: str) -> JSONResponse:
    model = get_model_by_name(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not registered")

    data = await request.json()
    instance = model(**data)
    await instance.save()
    return JSONResponse(instance.dict(), status_code=201)


async def retrieve_object(request: Request, model_name: str, pk: str) -> JSONResponse:
    model = get_model_by_name(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not registered")

    obj = await model.query.get(pk)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    return JSONResponse(obj.dict())


async def update_object(request: Request, model_name: str, pk: str) -> JSONResponse:
    model = get_model_by_name(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not registered")

    obj = await model.query.get(pk)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    data = await request.json()
    for key, value in data.items():
        setattr(obj, key, value)
    await obj.update()
    return JSONResponse(obj.dict())


async def delete_object(request: Request, model_name: str, pk: str) -> JSONResponse:
    model = get_model_by_name(model_name)
    if not model:
        raise HTTPException(status_code=404, detail="Model not registered")

    obj = await model.query.get(pk)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    await obj.delete()
    return JSONResponse({}, status_code=204)
