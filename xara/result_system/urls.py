from django.urls import path
from . import views

urlpatterns = [
    path('manage-results/', views.ManageResultsView.as_view(), name='manage_results'),
    path('get-classes/', views.get_classes, name='get_classes'),
    path('get-exams/', views.get_exams, name='get_exams'),
    path('results-availability/<int:academic_year_id>/<int:class_id>/<int:exam_id>/', views.ResultsAvailabilityView.as_view(), name='results_availability'),
    path('update-results/', views.update_results, name='update_results'),
    path('update-extra-exam-data/', views.update_extra_exam_data, name='update_extra_exam_data'),

    path('update_general-results/', views.update_general_results, name='update_general_results'),
    path('manage-general-exams/', views.ManageGeneralExamsView.as_view(), name='manage_general_exams'),
    path('get-general-exams/', views.get_general_exams, name='get_general_exams'),


    path('manage-extra-group-exams-data/', views.ManageExtraExamsDataView.as_view(), name='manage_extra_group_exams_data'),
    path('extra-group-exams-data-availability/<int:academic_year_id>/<int:class_id>/<int:general_exam_id>/', views.ExtraGroupExamsDataAvailabilityView.as_view(), name='extra_group_exam_data_availability'),


    path('manage-annual-exams/', views.ManageAnnualExamsView.as_view(), name='manage_annual_exams'),
    path('get-annual-exams/', views.get_annual_exams, name='get_annual_exams'),
    path('update_annual-results/', views.update_annual_results, name='update_annual_results'),

    path('general_exam_results/<int:general_exam_id>/<int:class_id>/<int:academic_year_id>/', 
         views.GeneralExamResultsAvailabilityView.as_view(), 
         name='general_exam_results_availability'),
    path('annual_exam_results/<int:annual_exam_id>/<int:class_id>/<int:academic_year_id>/', 
         views.AnnualExamResultsAvailabilityView.as_view(), 
         name='annual_exam_results_availability'),

]