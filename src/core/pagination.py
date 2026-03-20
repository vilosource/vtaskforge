from rest_framework.pagination import CursorPagination


class VTFCursorPagination(CursorPagination):
    page_size = 50
    max_page_size = 100
    ordering = "-created_at"
    page_size_query_param = "page_size"


class VTFEventCursorPagination(CursorPagination):
    page_size = 50
    max_page_size = 100
    ordering = "-timestamp"


class VTFAgentCursorPagination(CursorPagination):
    page_size = 50
    max_page_size = 100
    ordering = "-registered_at"


class VTFNoteCursorPagination(CursorPagination):
    """Notes are ordered oldest-first (ascending created_at)."""
    page_size = 50
    max_page_size = 100
    ordering = "created_at"
