from django.urls import path

from .views import DebateResultView, JoinedDebateListView, MyStanceEventListView, MyStanceView

urlpatterns = [
    path("debates/<int:debate_id>/result", DebateResultView.as_view(), name="debate-result"),
    path("debates/<int:debate_id>/me/events", MyStanceEventListView.as_view(), name="my-stance-events"),
    path("debates/<int:debate_id>/me/stance", MyStanceView.as_view(), name="my-stance"),
    path("me/debates", JoinedDebateListView.as_view(), name="joined-debate-list"),
]
