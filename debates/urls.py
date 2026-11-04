from django.urls import include, path


urlpatterns = [
    path("", include("debates.part_c.timing.urls")),
]
