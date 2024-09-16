from django.urls import path
from . import views

urlpatterns = [
    path('manage-results/', views.ManageResultsView.as_view(), name='manage_results'),
    path('get-classes/', views.get_classes, name='get_classes'),
    path('get-exams/', views.get_exams, name='get_exams'),
    path('results-availability/<int:academic_year_id>/<int:class_id>/<int:exam_id>/', views.ResultsAvailabilityView.as_view(), name='results_availability'),
    path('update-results/', views.update_results, name='update_results'),
    path('manage-general-exams/', views.ManageGeneralExamsView.as_view(), name='manage_general_exams'),
    path('get-general-exams/', views.get_general_exams, name='get_general_exams'),
    path('general_exam_results/<int:general_exam_id>/<int:class_id>/<int:academic_year_id>/', 
         views.GeneralExamResultsAvailabilityView.as_view(), 
         name='general_exam_results_availability'),
         
]