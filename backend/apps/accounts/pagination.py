from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """统一分页格式：{code, message, data: {count, results}}"""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("code", 0),
                    ("message", "success"),
                    (
                        "data",
                        OrderedDict(
                            [
                                ("count", self.page.paginator.count),
                                ("page", self.page.number),
                                ("page_size", self.get_page_size(self.request)),
                                ("total_pages", self.page.paginator.num_pages),
                                ("results", data),
                            ]
                        ),
                    ),
                ]
            )
        )
