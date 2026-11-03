from django.urls import path

from .views import JoinedDebateListView, MyStanceView

urlpatterns = [
    path("debates/<int:debate_id>/me/stance", MyStanceView.as_view(), name="my-stance"),
    path("me/debates", JoinedDebateListView.as_view(), name="joined-debate-list"),
]

