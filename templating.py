from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def render(request, name, context=None, status_code=200):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={**(context or {}), "current_user": getattr(request.state, "current_user", None)},
        status_code=status_code,
    )
