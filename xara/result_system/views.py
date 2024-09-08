from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from .models import AcademicYear, Class, Exam, GradeSheet, SubjectGrade, ClassStatistics, OverallStatistics

class ManageResultsView(View):
    template_name = 'result_system/manage_results.html'

    def get(self, request):
        school = request.user.school
        academic_years = AcademicYear.objects.filter(school=school).order_by('-year')
        
        context = {
            'academic_years': academic_years,
        }
        
        return render(request, self.template_name, context)

    def post(self, request):
        academic_year_id = request.POST.get('academic_year')
        class_id = request.POST.get('class')
        exam_id = request.POST.get('exam')
        
        if academic_year_id and class_id and exam_id:
            return redirect('results_availability', academic_year_id=academic_year_id, class_id=class_id, exam_id=exam_id)
        
        return self.get(request)

def get_classes(request):
    academic_year_id = request.GET.get('academic_year')
    classes = Class.objects.filter(academic_year_id=academic_year_id, school=request.user.school)
    data = [{'id': c.id, 'name': c.name} for c in classes]
    return JsonResponse(data, safe=False)

def get_exams(request):
    academic_year_id = request.GET.get('academic_year')
    exams = Exam.objects.filter(academic_year_id=academic_year_id, school=request.user.school)
    data = [{'id': e.id, 'name': e.name} for e in exams]
    return JsonResponse(data, safe=False)

class ResultsAvailabilityView(View):
    template_name = 'result_system/results_availability.html'

    def get(self, request, academic_year_id, class_id, exam_id):
        academic_year = AcademicYear.objects.get(id=academic_year_id)
        class_obj = Class.objects.get(id=class_id)
        exam = Exam.objects.get(id=exam_id)

        results_available = (
            GradeSheet.objects.filter(academic_year=academic_year, class_obj=class_obj, exam=exam).exists() and
            SubjectGrade.objects.filter(grade_sheet__academic_year=academic_year, grade_sheet__class_obj=class_obj, grade_sheet__exam=exam).exists() and
            ClassStatistics.objects.filter(academic_year=academic_year, class_obj=class_obj, exam=exam).exists() and
            OverallStatistics.objects.filter(academic_year=academic_year, class_obj=class_obj, exam=exam).exists()
        )

        context = {
            'academic_year': academic_year,
            'class_obj': class_obj,
            'exam': exam,
            'results_available': results_available,
        }
        
        return render(request, self.template_name, context)