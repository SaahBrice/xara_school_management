import json
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from .models import AcademicYear, Class, ClassSubject, Exam, GradeSheet, Student, SubjectGrade, ClassStatistics, OverallStatistics, TeacherSubject
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch
from django.core.exceptions import ObjectDoesNotExist


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
        try:
            with transaction.atomic():
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                class_obj = Class.objects.get(id=class_id)
                exam = Exam.objects.get(id=exam_id)

                # Fetch all subjects for the class
                class_subjects = ClassSubject.objects.filter(class_obj=class_obj, is_active = True).select_related('subject')

                #format it to a way usable by js
                class_subjects_data = []
                for class_subject in class_subjects:
                    teacher_subject = TeacherSubject.objects.filter(subject=class_subject.subject, class_obj=class_obj).first()
                    teacher_name = teacher_subject.teacher.user.get_full_name() if teacher_subject else "N/A"
                    class_subjects_data.append({
                        'id': class_subject.subject.id,
                        'code': class_subject.subject.code,
                        'credit': float(class_subject.subject.default_credit), 
                        'teacher': teacher_name, 
                        'name': class_subject.subject.name
                    })
                # Fetch all students in the class
                students = Student.objects.filter(current_class=class_obj, is_active=True)

                #format in a way excel will use
                students_data = []
                for student in students:
                    students_data.append({
                        'name': student.get_full_name(),
                        'id': student.id  # Assuming you have an 'id' to match scores with subjects
                    })



                # Prepare data structures
                created_items = {'grade_sheets': 0, 'subject_grades': 0, 'class_stats': 0}
                retrieved_items = {'grade_sheets': 0, 'subject_grades': 0, 'class_stats': 0}

                # Process students and subjects
                for student in students:
                    grade_sheet, created = GradeSheet.objects.get_or_create(
                        student=student,
                        exam=exam,
                        class_obj=class_obj,
                        academic_year=academic_year
                    )
                    if created:
                        created_items['grade_sheets'] += 1
                        print(f"Created GradeSheet for student {student.id}")
                    else:
                        retrieved_items['grade_sheets'] += 1
                        print(f"Retrieved GradeSheet for student {student.id}")

                    for class_subject in class_subjects:
                        subject_grade, created = SubjectGrade.objects.get_or_create(
                            grade_sheet=grade_sheet,
                            class_subject=class_subject
                        )
                        if created:
                            created_items['subject_grades'] += 1
                            print(f"Created SubjectGrade for student {student.id}, subject {class_subject.subject.name}")
                        else:
                            retrieved_items['subject_grades'] += 1
                            print(f"Retrieved SubjectGrade for student {student.id}, subject {class_subject.subject.name}")

                # Process ClassStatistics
                for class_subject in class_subjects:
                    class_stat, created = ClassStatistics.objects.get_or_create(
                        exam=exam,
                        class_obj=class_obj,
                        class_subject=class_subject,
                        academic_year=academic_year,
                        defaults={
                            'max_score': 0,
                            'min_score': 0,
                            'avg_score': 0,
                            'num_sat': 0,
                            'num_passed': 0,
                            'percentage_passed': 0
                        }
                    )
                    if created:
                        created_items['class_stats'] += 1
                        print(f"Created ClassStatistics for subject {class_subject.subject.name}")
                    else:
                        retrieved_items['class_stats'] += 1
                        print(f"Retrieved ClassStatistics for subject {class_subject.subject.name}")

                # Process OverallStatistics
                overall_stat, created = OverallStatistics.objects.get_or_create(
                    exam=exam,
                    class_obj=class_obj,
                    academic_year=academic_year,
                    defaults={
                        'num_students': students.count(),
                        'num_passes': 0,
                        'class_average': 0,
                        'overall_percentage_pass': 0
                    }
                )
                if created:
                    print("Created OverallStatistics")
                else:
                    print("Retrieved OverallStatistics")

                # Fetch all necessary data for the template
                grade_sheets = GradeSheet.objects.filter(
                    academic_year=academic_year,
                    class_obj=class_obj,
                    exam=exam
                ).prefetch_related(
                    Prefetch('subject_grades', queryset=SubjectGrade.objects.select_related('class_subject__subject'))
                ).select_related('student')

                students_with_grades = []
                for grade_sheet in grade_sheets:
                    student_grades = []
                    for class_subject in class_subjects:
                        subject_grade = grade_sheet.subject_grades.filter(class_subject=class_subject).first()
                        student_grades.append({
                            'subject': class_subject.subject.code,
                            'credit': float(class_subject.subject.default_credit),
                            'score': float(subject_grade.score) if subject_grade and subject_grade.score is not None else None
                        })
                    students_with_grades.append({
                        'name': grade_sheet.student.get_full_name(),
                        'grades': student_grades
                    })

                class_stats = ClassStatistics.objects.filter(
                    academic_year=academic_year,
                    class_obj=class_obj,
                    exam=exam
                ).select_related('class_subject__subject')

                # Prepare context for template
                context = {
                    'academic_year': academic_year,
                    'class_obj': class_obj,
                    'exam': exam,

                    'subjects': json.dumps(class_subjects_data),
                    'students': students_data,
                    'students_with_grades': json.dumps(students_with_grades),

                    'grade_sheets': grade_sheets,
                    'class_stats': class_stats,
                    'overall_stats': overall_stat,
                    'created_items': created_items,
                    'retrieved_items': retrieved_items,
                    'students': students,
                }

                # Print summary
                print("\nSummary:")
                print(f"Created items: {created_items}")
                print(f"Retrieved items: {retrieved_items}")
                return render(request, self.template_name, context)


        except ObjectDoesNotExist as e:
            print(f"Error: {str(e)}")
            context = {'error': f"Required object not found: {str(e)}"}
            return render(request, self.template_name, context)

        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            context = {'error': "An unexpected error occurred. Please try again."}
            return render(request, self.template_name, context)




@csrf_exempt
def update_results(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        try:
            with transaction.atomic():
                for student_data in data['students']:
                    # Update GradeSheet
                    grade_sheet = GradeSheet.objects.get(id=student_data['id'])
                    grade_sheet.total_score = student_data['new_total_score']
                    grade_sheet.average = student_data['new_average']
                    grade_sheet.remark = student_data['new_remark']
                    grade_sheet.rank = student_data['new_rank']
                    grade_sheet.save()

                    # Update SubjectGrade for the student
                    for grade in student_data['grades']:
                        subject_grade = SubjectGrade.objects.get(id=grade['id'])
                        subject_grade.score = grade['new_score']
                        subject_grade.rank = grade['new_rank']
                        subject_grade.save()

                # Update ClassStatistics and OverallStatistics
                for subject, stats in data['class_stats'].items():
                    class_stat = ClassStatistics.objects.get(class_subject__subject__name=subject)
                    class_stat.max_score = stats['new_max_score']
                    class_stat.min_score = stats['new_min_score']
                    class_stat.avg_score = stats['new_avg_score']
                    class_stat.num_sat = stats['new_num_sat']
                    class_stat.num_passed = stats['new_num_passed']
                    class_stat.percentage_passed = stats['new_percentage_passed']
                    class_stat.save()

                overall_stat = OverallStatistics.objects.get(
                    academic_year_id=data['academic_year_id'],
                    class_obj_id=data['class_id'],
                    exam_id=data['exam_id']
                )
                overall_stat.num_students = data['overall_stats']['new_num_students']
                overall_stat.num_passes = data['overall_stats']['new_num_passes']
                overall_stat.class_average = data['overall_stats']['new_class_average']
                overall_stat.overall_percentage_pass = data['overall_stats']['new_overall_percentage_pass']
                overall_stat.save()

            return JsonResponse({"status": "success"})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)