from django.urls import path
from . import views

urlpatterns = [
    path('manage-results/', views.ManageResultsView.as_view(), name='manage_results'),
    path('get-classes/', views.get_classes, name='get_classes'),
    path('get-exams/', views.get_exams, name='get_exams'),
    path('results-availability/<int:academic_year_id>/<int:class_id>/<int:exam_id>/', 
         views.ResultsAvailabilityView.as_view(), name='results_availability'),
]