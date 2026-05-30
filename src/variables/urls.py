from django.urls import path

from .views import ProjectVariableViewSet, VariableAuditViewSet

_list = ProjectVariableViewSet.as_view({"get": "list", "post": "create"})
_audit = VariableAuditViewSet.as_view({"get": "list", "post": "create"})
_detail = ProjectVariableViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    path(
        "projects/<str:project_id>/variables/",
        _list,
        name="projectvariable-list",
    ),
    path(
        "projects/<str:project_id>/variables/<str:pk>/",
        _detail,
        name="projectvariable-detail",
    ),
    path("variable-audits/", _audit, name="variableaudit-list"),
]
