import json
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from .models import AcademicYear, AnnualExam, AnnualExamClassStatistics, AnnualExamGradeSheet, AnnualExamOverallStatistics, AnnualExamSubjectGrade, Class, ClassSubject, Exam, ExtraExamData, GeneralExam, GeneralExamClassStatistics, GeneralExamGradeSheet, GeneralExamOverallStatistics, GeneralExamSubjectGrade, GradeSheet, Student, SubjectGrade, ClassStatistics, OverallStatistics, TeacherSubject
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Prefetch
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.db.models import Value
from django.db.models.functions import Concat
from django.utils.decorators import method_decorator



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







def parse_value(value, expected_type='decimal'):
    """
    Helper function to convert 'Absent', 'N/A', 'None', or null values to appropriate data types.
    - 'decimal' returns None if the value is invalid, allowing fields to stay unset.
    - 'int' for integer fields like ranks or counts, where valid.
    """
    if expected_type == 'decimal':
        try:
            # Return None if the value is invalid or if it's supposed to be absent
            return float(value) if value not in ['Absent', 'N/A', None] else None
        except ValueError:
            return None
    elif expected_type == 'int':
        try:
            # Return None for invalid rank values
            return int(value) if value not in ['Absent', 'N/A', None] else None
        except ValueError:
            return None
    else:
        # For string values or other data types, return the value or None if absent
        return value if value not in ['Absent', 'N/A', None] else None




@csrf_exempt
def update_results(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        try:
            with transaction.atomic():
                # Fetch academic year, class, and exam from IDs
                academic_year = AcademicYear.objects.get(id=data['academic_year_id'])
                class_obj = Class.objects.get(id=data['class_id'])
                exam = Exam.objects.get(id=data['exam_id'])

                print(f"Processing update for class '{class_obj.name}', academic year '{academic_year.year}', exam '{exam.name}'")

                # Fetch all students in the given class and academic year
                students_in_class = Student.objects.filter(current_class=class_obj, is_active=True)

                # Iterate through the students' data from the request
                for student_data in data['students']:
                    # Match student by full name from the students enrolled in the class for the given academic year
                    matching_students = students_in_class.annotate(
                        full_name=Concat('first_name', Value(' '), 'last_name')
                    ).filter(full_name=student_data['name'])
                    
                    if matching_students.exists():
                        student = matching_students.first()
                        print(f"Processing grades for student: {student.get_full_name()}")

                        # Fetch the student's existing grade sheet
                        grade_sheet = GradeSheet.objects.get(
                            student=student,
                            exam=exam,
                            class_obj=class_obj,
                            academic_year=academic_year
                        )

                        # Update the grade sheet fields (allow None for unset values)
                        grade_sheet.total_score = parse_value(student_data.get('totalScore'), 'decimal')
                        grade_sheet.credits_attempted = parse_value(student_data.get('creditsAttempted'), 'decimal')
                        grade_sheet.credits_obtained = parse_value(student_data.get('creditsObtained'), 'decimal')
                        grade_sheet.average = parse_value(student_data.get('average'), 'decimal')
                        grade_sheet.rank = parse_value(student_data.get('rank'), 'int')
                        grade_sheet.remark = parse_value(student_data.get('remark'), 'string')
                        grade_sheet.save()
                        print(f"Updated GradeSheet for {student.get_full_name()}")

                        # Now iterate through the student's grades and update the SubjectGrade model
                        for grade_data in student_data['grades']:
                            # Fetch the class subject by its code
                            class_subject = get_object_or_404(ClassSubject, class_obj=class_obj, subject__code=grade_data['subject'])

                            # Fetch the subject grade
                            subject_grade = SubjectGrade.objects.get(
                                grade_sheet=grade_sheet,
                                class_subject=class_subject
                            )

                            # Update the subject grade fields, handling 'Absent', 'N/A', and other invalid values
                            # If the score is absent, it will be set to None
                            subject_grade.score = parse_value(grade_data.get('score'), 'decimal')
                            subject_grade.rank = parse_value(grade_data.get('rank'), 'int')
                            subject_grade.observation = parse_value(grade_data.get('observation'), 'string')
                            subject_grade.save()
                            print(f"Updated SubjectGrade for {student.get_full_name()} in subject {class_subject.subject.name}: Score = {subject_grade.score}")
                    else:
                        print(f"Student {student_data['name']} not found in class {class_obj.name} for academic year {academic_year.year}.")

                # Update ClassStatistics
                for stat_data in data['classStats']:
                    class_subject = get_object_or_404(ClassSubject, class_obj=class_obj, subject__code=stat_data['subject'])
                    class_stat = ClassStatistics.objects.get(
                        exam=exam,
                        class_obj=class_obj,
                        class_subject=class_subject,
                        academic_year=academic_year
                    )

                    # Update class statistics fields, using None for unset values
                    class_stat.max_score = parse_value(stat_data['maxScore'], 'decimal')
                    class_stat.min_score = parse_value(stat_data['minScore'], 'decimal')
                    class_stat.avg_score = parse_value(stat_data['avgScore'], 'decimal')
                    class_stat.num_sat = parse_value(stat_data['numSat'], 'int')
                    class_stat.num_passed = parse_value(stat_data['numPassed'], 'int')
                    class_stat.percentage_passed = parse_value(stat_data['percentagePassed'], 'decimal')
                    print(class_stat.percentage_passed)
                    class_stat.save()
                    print(f"Updated ClassStatistics for {class_subject.subject.name}")

                # Update OverallStatistics
                overall_stat = OverallStatistics.objects.get(
                    exam=exam,
                    class_obj=class_obj,
                    academic_year=academic_year
                )

                # Update overall statistics fields, allowing None where appropriate
                overall_stat.num_students = parse_value(data['overallStats']['numStudents'], 'int')
                overall_stat.num_passes = parse_value(data['overallStats']['numPasses'], 'int')
                overall_stat.class_average = parse_value(data['overallStats']['classAverage'], 'decimal')
                overall_stat.overall_percentage_pass = parse_value(data['overallStats']['overallPercentagePass'], 'decimal')
                overall_stat.save()
                print(f"Updated OverallStatistics")

                return JsonResponse({"status": "success"})

        except Exception as e:
            # Handle any errors
            print(f"Error occurred: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)




class ManageGeneralExamsView(View):
    template_name = 'result_system/manage_general_exams.html'

    def get(self, request):
        school = request.user.school
        academic_years = AcademicYear.objects.filter(school=school).order_by('-year')

        context = {
            'academic_years': academic_years,
        }

        return render(request, self.template_name, context)
    def post(self, request):
        # Capture the form data: academic year, class, and general exam
        academic_year_id = request.POST.get('academic_year')
        class_id = request.POST.get('class')
        general_exam_id = request.POST.get('general_exam')

        # Ensure that all fields are selected
        if academic_year_id and class_id and general_exam_id:
            # Redirect to GeneralExamResultsAvailabilityView with the selected data
            return redirect('general_exam_results_availability', 
                            general_exam_id=general_exam_id, 
                            class_id=class_id, 
                            academic_year_id=academic_year_id)
        
        # If any fields are missing, render the form again with an error message
        return self.get(request)


class ManageExtraExamsDataView(View):
    template_name = 'result_system/manage_extra_exams_data.html'

    def get(self, request):
        school = request.user.school
        academic_years = AcademicYear.objects.filter(school=school).order_by('-year')

        context = {
            'academic_years': academic_years,
        }

        return render(request, self.template_name, context)
    def post(self, request):
        # Capture the form data: academic year, class, and general exam
        academic_year_id = request.POST.get('academic_year')
        class_id = request.POST.get('class')
        general_exam_id = request.POST.get('general_exam')

        # Ensure that all fields are selected
        if academic_year_id and class_id and general_exam_id:
            # Redirect to GeneralExamResultsAvailabilityView with the selected data
            return redirect('extra_group_exam_data_availability', 
                            general_exam_id=general_exam_id, 
                            class_id=class_id, 
                            academic_year_id=academic_year_id)
        
        # If any fields are missing, render the form again with an error message
        return self.get(request)




class ManageAnnualExamsView(View):
    template_name = 'result_system/manage_annual_exams.html'

    def get(self, request):
        school = request.user.school
        academic_years = AcademicYear.objects.filter(school=school).order_by('-year')

        context = {
            'academic_years': academic_years,
        }

        return render(request, self.template_name, context)
    def post(self, request):
        # Capture the form data: academic year, class, and general exam
        academic_year_id = request.POST.get('academic_year')
        class_id = request.POST.get('class')
        annual_exam_id = request.POST.get('annual_exam')

        # Ensure that all fields are selected
        if academic_year_id and class_id and annual_exam_id:
            # Redirect to AnnualExamResultsAvailabilityView with the selected data
            return redirect('annual_exam_results_availability', 
                            annual_exam_id=annual_exam_id, 
                            class_id=class_id, 
                            academic_year_id=academic_year_id)
        
        # If any fields are missing, render the form again with an error message
        return self.get(request)



def get_general_exams(request):
    academic_year_id = request.GET.get('academic_year')
    general_exams = GeneralExam.objects.filter(academic_year_id=academic_year_id, school=request.user.school)
    data = [{'id': e.id, 'name': e.name} for e in general_exams]
    return JsonResponse(data, safe=False)

def get_annual_exams(request):
    academic_year_id = request.GET.get('academic_year')
    annual_exams = AnnualExam.objects.filter(academic_year_id=academic_year_id, school=request.user.school)
    data = [{'id': e.id, 'name': e.name} for e in annual_exams]
    return JsonResponse(data, safe=False)









class GeneralExamResultsAvailabilityView(View):
    template_name = 'result_system/general_exam_results_availability.html'

    def get(self, request, general_exam_id, class_id, academic_year_id):
        try:
            with transaction.atomic():
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                class_obj = Class.objects.get(id=class_id)
                general_exam = GeneralExam.objects.get(id=general_exam_id)

                # Fetch all subjects for the class
                class_subjects = ClassSubject.objects.filter(class_obj=class_obj, is_active=True).select_related('subject')

                # Format it for use by JavaScript
                class_subjects_data = []
                for class_subject in class_subjects:
                    teacher_subject = TeacherSubject.objects.filter(subject=class_subject.subject, class_obj=class_obj).first()
                    teacher_name = teacher_subject.teacher.user.get_full_name() if teacher_subject else "N/A"
                    class_subjects_data.append({
                        'id': class_subject.subject.id,
                        'code': class_subject.subject.code,
                        'credit': float(class_subject.subject.default_credit),  # Convert Decimal to float
                        'teacher': teacher_name,
                        'name': class_subject.subject.name
                    })

                # Fetch all students in the class
                students = Student.objects.filter(current_class=class_obj, is_active=True)

                # Format in a way that Excel will use
                students_data = []
                for student in students:
                    students_data.append({
                        'name': student.get_full_name(),
                        'id': student.id  # Assuming you have an 'id' to match scores with subjects
                    })

                # Prepare data structures
                created_items = {'general_exam_grade_sheets': 0, 'subject_grades': 0, 'general_exam_class_stats': 0}
                retrieved_items = {'general_exam_grade_sheets': 0, 'subject_grades': 0, 'general_exam_class_stats': 0}

                # Process students and subjects
                for student in students:
                    # Get or create GeneralExamGradeSheet
                    general_exam_grade_sheet, created = GeneralExamGradeSheet.objects.get_or_create(
                        student=student,
                        general_exam=general_exam,  # Using general_exam
                        class_obj=class_obj,
                        academic_year=academic_year
                    )
                    if created:
                        created_items['general_exam_grade_sheets'] += 1
                    else:
                        retrieved_items['general_exam_grade_sheets'] += 1

                    for class_subject in class_subjects:
                        # Get or create GeneralExamSubjectGrade for each subject
                        general_exam_subject_grade, created = GeneralExamSubjectGrade.objects.get_or_create(
                            grade_sheet=general_exam_grade_sheet,
                            class_subject=class_subject
                        )
                        if created:
                            created_items['subject_grades'] += 1
                        else:
                            retrieved_items['subject_grades'] += 1

                # Process GeneralExamClassStatistics
                for class_subject in class_subjects:
                    general_exam_class_stat, created = GeneralExamClassStatistics.objects.get_or_create(
                        general_exam=general_exam,  # Using general_exam
                        class_obj=class_obj,
                        class_subject=class_subject,
                        academic_year = academic_year,
                        defaults={
                            'max_score': 0,
                            'min_score': 0,
                            'avg_score': 0,
                            'num_students': 0,
                            'num_passed': 0,
                            'percentage_passed': 0
                        }
                    )
                    if created:
                        created_items['general_exam_class_stats'] += 1
                    else:
                        retrieved_items['general_exam_class_stats'] += 1

                # Process GeneralExamOverallStatistics
                general_exam_overall_stat, created = GeneralExamOverallStatistics.objects.get_or_create(
                    general_exam=general_exam,  # Using general_exam
                    class_obj=class_obj,
                    academic_year = academic_year,
                    defaults={
                        'num_students': students.count(),
                        'num_passes': 0,
                        'class_average': 0,
                        'overall_percentage_pass': 0
                    }
                )

                # Fetch all necessary data for the template
                general_exam_grade_sheets = GeneralExamGradeSheet.objects.filter(
                    academic_year=academic_year,
                    class_obj=class_obj,
                    general_exam=general_exam  # Using general_exam
                ).prefetch_related(
                    Prefetch('subject_grades', queryset=GeneralExamSubjectGrade.objects.select_related('class_subject__subject'))
                ).select_related('student')

                students_with_grades = []
                for general_exam_grade_sheet in general_exam_grade_sheets:
                    student_grades = []
                    for class_subject in class_subjects:
                        # Fetch all individual exams in the general exam
                        individual_exams = general_exam.exams.all()

                        # Sum the scores for this subject across all individual exams
                        total_score = 0
                        exam_count = 0
                        for exam in individual_exams:
                            # Get the student's grade sheet for the individual exam
                            grade_sheet = GradeSheet.objects.filter(
                                student=general_exam_grade_sheet.student,
                                exam=exam,
                                class_obj=class_obj,
                                academic_year=academic_year
                            ).first()

                            if grade_sheet:
                                # Get the subject grade for the current subject
                                subject_grade = grade_sheet.subject_grades.filter(class_subject=class_subject).first()
                                if subject_grade and subject_grade.score is not None:
                                    total_score += subject_grade.score
                                    exam_count += 1

                        # Calculate the average score if there are exams for the subject
                        average_score = total_score / exam_count if exam_count > 0 else None

                        student_grades.append({
                            'subject': class_subject.subject.code,
                            'credit': float(class_subject.subject.default_credit),  # Convert Decimal to float
                            'score': float(average_score) if average_score is not None else None  # Convert to float
                        })
                    students_with_grades.append({
                        'name': general_exam_grade_sheet.student.get_full_name(),
                        'grades': student_grades
                    })

                general_exam_class_stats = GeneralExamClassStatistics.objects.filter(
                    class_obj=class_obj,
                    general_exam=general_exam  # Using general_exam
                ).select_related('class_subject__subject')

                # Now let's add the detailed results for every exam in the general exam
                individual_exam_results = []
                for exam in general_exam.exams.all():
                    # Fetch GradeSheets and SubjectGrades for this individual exam
                    grade_sheets = GradeSheet.objects.filter(
                        academic_year=academic_year,
                        class_obj=class_obj,
                        exam=exam
                    ).prefetch_related(
                        Prefetch('subject_grades', queryset=SubjectGrade.objects.select_related('class_subject__subject'))
                    ).select_related('student')

                    individual_students_data = []
                    for grade_sheet in grade_sheets:
                        student_grades = []
                        for class_subject in class_subjects:
                            subject_grade = grade_sheet.subject_grades.filter(class_subject=class_subject).first()
                            student_grades.append({
                                'subject': class_subject.subject.code,
                                'credit': float(class_subject.subject.default_credit),  # Convert Decimal to float
                                'score': float(subject_grade.score) if subject_grade and subject_grade.score is not None else None,
                                'rank': subject_grade.rank,
                                'observation': subject_grade.observation,
                            })
                        individual_students_data.append({
                            'name': grade_sheet.student.get_full_name(),
                            'grades': student_grades
                        })

                    # Fetch and serialize ClassStatistics for this individual exam
                    class_stats = ClassStatistics.objects.filter(
                        academic_year=academic_year,
                        class_obj=class_obj,
                        exam=exam
                    ).select_related('class_subject__subject')

                    class_stats_data = []
                    for stat in class_stats:
                        class_stats_data.append({
                            'subject': stat.class_subject.subject.code,
                            'max_score': float(stat.max_score) if stat.max_score is not None else None,  # Check if None
                            'min_score': float(stat.min_score) if stat.min_score is not None else None,  # Check if None
                            'avg_score': float(stat.avg_score) if stat.avg_score is not None else None,  # Check if None
                            'num_students': stat.num_sat,  # Integer
                            'num_passed': stat.num_passed,  # Integer
                            'percentage_passed': float(stat.percentage_passed) if stat.percentage_passed is not None else None  # Check if None
                        })



                    # Fetch and serialize OverallStatistics for this individual exam
                    overall_stat = OverallStatistics.objects.get(
                        exam=exam,
                        class_obj=class_obj,
                        academic_year=academic_year
                    )
                    overall_stat_data = {
                        'num_students': overall_stat.num_students,  # Integer
                        'num_passes': overall_stat.num_passes,  # Integer
                        'class_average': float(overall_stat.class_average) if overall_stat.class_average is not None else None,  # Check if None
                        'overall_percentage_pass': float(overall_stat.overall_percentage_pass) if overall_stat.overall_percentage_pass is not None else None  # Check if None
                    }


                    # Store results for this exam
                    individual_exam_results.append({
                        'exam': {
                            'id': exam.id,
                            'name': exam.name
                        },
                        'students': individual_students_data,
                        'class_stats': class_stats_data,  # Serialized class stats
                        'overall_stats': overall_stat_data  # Serialized overall stats
                    })

                # Prepare context for template
                context = {
                    'academic_year': academic_year,
                    'class_obj': class_obj,
                    'general_exam': general_exam,  # Using general_exam

                    'subjects': json.dumps(class_subjects_data),
                    'students': students_data,
                    'students_with_grades': json.dumps(students_with_grades),

                    'general_exam_grade_sheets': general_exam_grade_sheets,
                    'general_exam_class_stats': general_exam_class_stats,
                    'general_exam_overall_stats': general_exam_overall_stat,

                    'individual_exam_results': json.dumps(individual_exam_results),  # Results for each individual exam
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






class AnnualExamResultsAvailabilityView(View):
    template_name = 'result_system/annual_exam_results_availability.html'

    def get(self, request, annual_exam_id, class_id, academic_year_id):
        try:
            with transaction.atomic():
                # Fetch the academic year, class, and annual exam
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                class_obj = Class.objects.get(id=class_id)
                annual_exam = AnnualExam.objects.get(id=annual_exam_id)

                # Fetch all subjects for the class
                class_subjects = ClassSubject.objects.filter(class_obj=class_obj, is_active=True).select_related('subject')

                # Prepare subjects data for JavaScript use
                class_subjects_data = []
                for class_subject in class_subjects:
                    teacher_subject = TeacherSubject.objects.filter(subject=class_subject.subject, class_obj=class_obj).first()
                    teacher_name = teacher_subject.teacher.user.get_full_name() if teacher_subject else "N/A"
                    class_subjects_data.append({
                        'id': class_subject.subject.id,
                        'code': class_subject.subject.code,
                        'credit': float(class_subject.subject.default_credit),  # Convert Decimal to float
                        'teacher': teacher_name,
                        'name': class_subject.subject.name
                    })

                # Fetch all students in the class
                students = Student.objects.filter(current_class=class_obj, is_active=True)

                # Format student data for export
                students_data = []
                for student in students:
                    students_data.append({
                        'name': student.get_full_name(),
                        'id': student.id  # Assuming you have an 'id' to match scores with subjects
                    })

                # Prepare data structures
                created_items = {'annual_exam_grade_sheets': 0, 'subject_grades': 0, 'annual_exam_class_stats': 0}
                retrieved_items = {'annual_exam_grade_sheets': 0, 'subject_grades': 0, 'annual_exam_class_stats': 0}

                # Process students and subjects for AnnualExamGradeSheet and AnnualExamSubjectGrade
                for student in students:
                    # Get or create AnnualExamGradeSheet for each student
                    annual_exam_grade_sheet, created = AnnualExamGradeSheet.objects.get_or_create(
                        student=student,
                        annual_exam=annual_exam,
                        class_obj=class_obj,
                        academic_year=academic_year
                    )
                    if created:
                        created_items['annual_exam_grade_sheets'] += 1
                    else:
                        retrieved_items['annual_exam_grade_sheets'] += 1

                    for class_subject in class_subjects:
                        # Get or create AnnualExamSubjectGrade for each subject
                        annual_exam_subject_grade, created = AnnualExamSubjectGrade.objects.get_or_create(
                            grade_sheet=annual_exam_grade_sheet,
                            class_subject=class_subject
                        )
                        if created:
                            created_items['subject_grades'] += 1
                        else:
                            retrieved_items['subject_grades'] += 1

                # Process AnnualExamClassStatistics
                for class_subject in class_subjects:
                    annual_exam_class_stat, created = AnnualExamClassStatistics.objects.get_or_create(
                        annual_exam=annual_exam,
                        class_obj=class_obj,
                        class_subject=class_subject,
                        academic_year=academic_year,
                        defaults={
                            'max_score': 0,
                            'min_score': 0,
                            'avg_score': 0,
                            'num_students': 0,
                            'num_passed': 0,
                            'percentage_passed': 0
                        }
                    )
                    if created:
                        created_items['annual_exam_class_stats'] += 1
                    else:
                        retrieved_items['annual_exam_class_stats'] += 1

                # Process AnnualExamOverallStatistics
                annual_exam_overall_stat, created = AnnualExamOverallStatistics.objects.get_or_create(
                    annual_exam=annual_exam,
                    class_obj=class_obj,
                    academic_year=academic_year,
                    defaults={
                        'num_students': students.count(),
                        'num_passes': 0,
                        'class_average': 0,
                        'overall_percentage_pass': 0
                    }
                )

                # Fetch all grade sheets for the annual exam
                annual_exam_grade_sheets = AnnualExamGradeSheet.objects.filter(
                    academic_year=academic_year,
                    class_obj=class_obj,
                    annual_exam=annual_exam
                ).prefetch_related(
                    Prefetch('subject_grades', queryset=AnnualExamSubjectGrade.objects.select_related('class_subject__subject'))
                ).select_related('student')

                students_with_grades = []
                for annual_exam_grade_sheet in annual_exam_grade_sheets:
                    student_grades = []
                    for class_subject in class_subjects:
                        # Fetch all general exams in the annual exam
                        individual_general_exams = annual_exam.general_exams.all()

                        # Sum the scores for this subject across all general exams
                        total_score = 0
                        exam_count = 0
                        for general_exam in individual_general_exams:
                            # Get the student's grade sheet for the individual general exam
                            grade_sheet = GeneralExamGradeSheet.objects.filter(
                                student=annual_exam_grade_sheet.student,
                                general_exam=general_exam,
                                class_obj=class_obj,
                                academic_year=academic_year
                            ).first()

                            if grade_sheet:
                                # Get the subject grade for the current subject in the general exam
                                subject_grade = grade_sheet.subject_grades.filter(class_subject=class_subject).first()
                                if subject_grade and subject_grade.calculated_score is not None:
                                    total_score += subject_grade.calculated_score
                                    exam_count += 1

                        # Calculate the average score if there are general exams for the subject
                        average_score = total_score / exam_count if exam_count > 0 else None

                        student_grades.append({
                            'subject': class_subject.subject.code,
                            'credit': float(class_subject.subject.default_credit),
                            'score': float(average_score) if average_score is not None else None
                        })
                    students_with_grades.append({
                        'name': annual_exam_grade_sheet.student.get_full_name(),
                        'grades': student_grades
                    })

                annual_exam_class_stats = AnnualExamClassStatistics.objects.filter(
                    class_obj=class_obj,
                    annual_exam=annual_exam
                ).select_related('class_subject__subject')

                # Fetch detailed results for each general exam in the annual exam
                individual_exam_results = []
                for general_exam in annual_exam.general_exams.all():
                    # Fetch GradeSheets and SubjectGrades for each general exam
                    grade_sheets = GeneralExamGradeSheet.objects.filter(
                        academic_year=academic_year,
                        class_obj=class_obj,
                        general_exam=general_exam
                    ).prefetch_related(
                        Prefetch('subject_grades', queryset=GeneralExamSubjectGrade.objects.select_related('class_subject__subject'))
                    ).select_related('student')

                    individual_students_data = []
                    for grade_sheet in grade_sheets:
                        student_grades = []
                        for class_subject in class_subjects:
                            subject_grade = grade_sheet.subject_grades.filter(class_subject=class_subject).first()
                            student_grades.append({
                                'subject': class_subject.subject.code,
                                'credit': float(class_subject.subject.default_credit),
                                'score': float(subject_grade.calculated_score) if subject_grade and subject_grade.calculated_score is not None else None,
                                'rank': subject_grade.rank,
                                'observation': subject_grade.observation,
                            })
                        individual_students_data.append({
                            'name': grade_sheet.student.get_full_name(),
                            'grades': student_grades
                        })

                    # Fetch and serialize ClassStatistics for this individual general exam
                    class_stats = GeneralExamClassStatistics.objects.filter(
                        academic_year=academic_year,
                        class_obj=class_obj,
                        general_exam=general_exam
                    ).select_related('class_subject__subject')

                    class_stats_data = []
                    for stat in class_stats:
                        class_stats_data.append({
                            'subject': stat.class_subject.subject.code,
                            'max_score': float(stat.max_score) if stat.max_score is not None else None,
                            'min_score': float(stat.min_score) if stat.min_score is not None else None,
                            'avg_score': float(stat.avg_score) if stat.avg_score is not None else None,
                            'num_students': stat.num_students,
                            'num_passed': stat.num_passed,
                            'percentage_passed': float(stat.percentage_passed) if stat.percentage_passed is not None else None
                        })

                    # Fetch and serialize OverallStatistics for this individual general exam
                    overall_stat = GeneralExamOverallStatistics.objects.get(
                        general_exam=general_exam,
                        class_obj=class_obj,
                        academic_year=academic_year
                    )
                    overall_stat_data = {
                        'num_students': overall_stat.num_students,
                        'num_passes': overall_stat.num_passes,
                        'class_average': float(overall_stat.class_average) if overall_stat.class_average is not None else None,
                        'overall_percentage_pass': float(overall_stat.overall_percentage_pass) if overall_stat.overall_percentage_pass is not None else None
                    }

                    # Store results for this general exam
                    individual_exam_results.append({
                        'exam': {
                            'id': general_exam.id,
                            'name': general_exam.name
                        },
                        'students': individual_students_data,
                        'class_stats': class_stats_data,
                        'overall_stats': overall_stat_data
                    })

                # Prepare context for the template
                context = {
                    'academic_year': academic_year,
                    'class_obj': class_obj,
                    'annual_exam': annual_exam,

                    'subjects': json.dumps(class_subjects_data),
                    'students': students_data,
                    'students_with_grades': json.dumps(students_with_grades),

                    'annual_exam_grade_sheets': annual_exam_grade_sheets,
                    'annual_exam_class_stats': annual_exam_class_stats,
                    'annual_exam_overall_stats': annual_exam_overall_stat,

                    'individual_exam_results': json.dumps(individual_exam_results),
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
def update_general_results(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        try:
            with transaction.atomic():
                # Fetch academic year, class, and exam from IDs
                academic_year = AcademicYear.objects.get(id=data['academic_year_id'])
                class_obj = Class.objects.get(id=data['class_id'])
                general_exam = GeneralExam.objects.get(id=data['general_exam_id'])

                print(f"Processing update for class '{class_obj.name}', academic year '{academic_year.year}', exam '{general_exam.name}'")

                # Fetch all students in the given class and academic year
                students_in_class = Student.objects.filter(current_class=class_obj, is_active=True)

                # Iterate through the students' data from the request
                for student_data in data['students']:
                    # Match student by full name from the students enrolled in the class for the given academic year
                    matching_students = students_in_class.annotate(
                        full_name=Concat('first_name', Value(' '), 'last_name')
                    ).filter(full_name=student_data['name'])
                    
                    if matching_students.exists():
                        student = matching_students.first()
                        print(f"Processing grades for student: {student.get_full_name()}")

                        # Fetch the student's existing grade sheet
                        grade_sheet = GeneralExamGradeSheet.objects.get(
                            student=student,
                            general_exam=general_exam,
                            class_obj=class_obj,
                            academic_year=academic_year
                        )

                        # Update the grade sheet fields (allow None for unset values)
                        grade_sheet.total_score = parse_value(student_data.get('totalScore'), 'decimal')
                        grade_sheet.credits_attempted = parse_value(student_data.get('creditsAttempted'), 'decimal')
                        grade_sheet.credits_obtained = parse_value(student_data.get('creditsObtained'), 'decimal')
                        grade_sheet.average = parse_value(student_data.get('average'), 'decimal')
                        grade_sheet.rank = parse_value(student_data.get('rank'), 'int')
                        grade_sheet.remark = parse_value(student_data.get('remark'), 'string')
                        grade_sheet.save()
                        print(f"Updated GradeSheet for {student.get_full_name()}")

                        # Now iterate through the student's grades and update the SubjectGrade model
                        for grade_data in student_data['grades']:
                            # Fetch the class subject by its code
                            class_subject = get_object_or_404(ClassSubject, class_obj=class_obj, subject__code=grade_data['subject'])

                            # Fetch the subject grade
                            subject_grade = GeneralExamSubjectGrade.objects.get(
                                grade_sheet=grade_sheet,
                                class_subject=class_subject
                            )

                            # Update the subject grade fields, handling 'Absent', 'N/A', and other invalid values
                            # If the score is absent, it will be set to None
                            subject_grade.calculated_score = parse_value(grade_data.get('score'), 'decimal')
                            subject_grade.rank = parse_value(grade_data.get('rank'), 'int')
                            subject_grade.observation = parse_value(grade_data.get('observation'), 'string')
                            subject_grade.save()
                            print(f"Updated SubjectGrade for {student.get_full_name()} in subject {class_subject.subject.name}: Score = {subject_grade.calculated_score}")
                    else:
                        print(f"Student {student_data['name']} not found in class {class_obj.name} for academic year {academic_year.year}.")

                # Update ClassStatistics
                for stat_data in data['classStats']:
                    class_subject = get_object_or_404(ClassSubject, class_obj=class_obj, subject__code=stat_data['subject'])
                    class_stat = GeneralExamClassStatistics.objects.get(
                        general_exam=general_exam,
                        class_obj=class_obj,
                        class_subject=class_subject,
                        academic_year=academic_year
                    )

                    # Update class statistics fields, using None for unset values
                    class_stat.max_score = parse_value(stat_data['maxScore'], 'decimal')
                    class_stat.min_score = parse_value(stat_data['minScore'], 'decimal')
                    class_stat.avg_score = parse_value(stat_data['avgScore'], 'decimal')
                    class_stat.num_students = parse_value(stat_data['numSat'], 'int')
                    class_stat.num_passed = parse_value(stat_data['numPassed'], 'int')
                    class_stat.percentage_passed = parse_value(stat_data['percentagePassed'], 'decimal')
                    print(class_stat.percentage_passed)
                    class_stat.save()
                    print(f"Updated ClassStatistics for {class_subject.subject.name}")

                # Update OverallStatistics
                overall_stat = GeneralExamOverallStatistics.objects.get(
                    general_exam=general_exam,
                    class_obj=class_obj,
                    academic_year=academic_year
                )

                # Update overall statistics fields, allowing None where appropriate
                overall_stat.num_students = parse_value(data['overallStats']['numStudents'], 'int')
                overall_stat.num_passes = parse_value(data['overallStats']['numPasses'], 'int')
                overall_stat.class_average = parse_value(data['overallStats']['classAverage'], 'decimal')
                overall_stat.overall_percentage_pass = parse_value(data['overallStats']['overallPercentagePass'], 'decimal')
                overall_stat.save()
                print(f"Updated OverallStatistics")

                return JsonResponse({"status": "success"})

        except Exception as e:
            # Handle any errors
            print(f"Error occurred: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)



@csrf_exempt
def update_annual_results(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        try:
            with transaction.atomic():
                # Fetch academic year, class, and annual exam from IDs
                academic_year = AcademicYear.objects.get(id=data['academic_year_id'])
                class_obj = Class.objects.get(id=data['class_id'])
                annual_exam = AnnualExam.objects.get(id=data['annual_exam_id'])

                print(f"Processing update for class '{class_obj.name}', academic year '{academic_year.year}', annual exam '{annual_exam.name}'")

                # Fetch all students in the given class and academic year
                students_in_class = Student.objects.filter(current_class=class_obj, is_active=True)

                # Iterate through the students' data from the request
                for student_data in data['students']:
                    # Match student by full name from the students enrolled in the class for the given academic year
                    matching_students = students_in_class.annotate(
                        full_name=Concat('first_name', Value(' '), 'last_name')
                    ).filter(full_name=student_data['name'])
                    
                    if matching_students.exists():
                        student = matching_students.first()
                        print(f"Processing grades for student: {student.get_full_name()}")

                        # Fetch the student's existing annual exam grade sheet
                        annual_exam_grade_sheet = AnnualExamGradeSheet.objects.get(
                            student=student,
                            annual_exam=annual_exam,
                            class_obj=class_obj,
                            academic_year=academic_year
                        )

                        # Update the annual exam grade sheet fields
                        annual_exam_grade_sheet.total_score = parse_value(student_data.get('totalScore'), 'decimal')
                        annual_exam_grade_sheet.credits_attempted = parse_value(student_data.get('creditsAttempted'), 'decimal')
                        annual_exam_grade_sheet.credits_obtained = parse_value(student_data.get('creditsObtained'), 'decimal')
                        annual_exam_grade_sheet.average = parse_value(student_data.get('average'), 'decimal')
                        annual_exam_grade_sheet.rank = parse_value(student_data.get('rank'), 'int')
                        annual_exam_grade_sheet.remark = parse_value(student_data.get('remark'), 'string')
                        annual_exam_grade_sheet.save()
                        print(f"Updated AnnualExamGradeSheet for {student.get_full_name()}")

                        # Now iterate through the student's grades and update the AnnualExamSubjectGrade model
                        for grade_data in student_data['grades']:
                            # Fetch the class subject by its code
                            class_subject = get_object_or_404(ClassSubject, class_obj=class_obj, subject__code=grade_data['subject'])

                            # Fetch the subject grade
                            annual_exam_subject_grade = AnnualExamSubjectGrade.objects.get(
                                grade_sheet=annual_exam_grade_sheet,
                                class_subject=class_subject
                            )

                            # Update the subject grade fields
                            annual_exam_subject_grade.calculated_score = parse_value(grade_data.get('score'), 'decimal')
                            annual_exam_subject_grade.rank = parse_value(grade_data.get('rank'), 'int')
                            annual_exam_subject_grade.observation = parse_value(grade_data.get('observation'), 'string')
                            annual_exam_subject_grade.save()
                            print(f"Updated AnnualExamSubjectGrade for {student.get_full_name()} in subject {class_subject.subject.name}: Score = {annual_exam_subject_grade.calculated_score}")
                    else:
                        print(f"Student {student_data['name']} not found in class {class_obj.name} for academic year {academic_year.year}.")

                # Update ClassStatistics for the annual exam
                for stat_data in data['classStats']:
                    class_subject = get_object_or_404(ClassSubject, class_obj=class_obj, subject__code=stat_data['subject'])
                    annual_exam_class_stat = AnnualExamClassStatistics.objects.get(
                        annual_exam=annual_exam,
                        class_obj=class_obj,
                        class_subject=class_subject,
                        academic_year=academic_year
                    )

                    # Update class statistics fields
                    annual_exam_class_stat.max_score = parse_value(stat_data['maxScore'], 'decimal')
                    annual_exam_class_stat.min_score = parse_value(stat_data['minScore'], 'decimal')
                    annual_exam_class_stat.avg_score = parse_value(stat_data['avgScore'], 'decimal')
                    annual_exam_class_stat.num_students = parse_value(stat_data['numSat'], 'int')
                    annual_exam_class_stat.num_passed = parse_value(stat_data['numPassed'], 'int')
                    annual_exam_class_stat.percentage_passed = parse_value(stat_data['percentagePassed'], 'decimal')
                    print(f"Updated ClassStatistics for {class_subject.subject.name}")
                    annual_exam_class_stat.save()

                # Update OverallStatistics for the annual exam
                overall_stat = AnnualExamOverallStatistics.objects.get(
                    annual_exam=annual_exam,
                    class_obj=class_obj,
                    academic_year=academic_year
                )

                # Update overall statistics fields
                overall_stat.num_students = parse_value(data['overallStats']['numStudents'], 'int')
                overall_stat.num_passes = parse_value(data['overallStats']['numPasses'], 'int')
                overall_stat.class_average = parse_value(data['overallStats']['classAverage'], 'decimal')
                overall_stat.overall_percentage_pass = parse_value(data['overallStats']['overallPercentagePass'], 'decimal')
                overall_stat.save()
                print(f"Updated OverallStatistics for class {class_obj.name}")

                return JsonResponse({"status": "success"})

        except Exception as e:
            # Handle any errors
            print(f"Error occurred: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=400)





class ExtraGroupExamsDataAvailabilityView(View):
    template_name = 'result_system/extra_group_exams_availability.html'

    def get(self, request, academic_year_id, class_id, general_exam_id):
        try:
            with transaction.atomic():
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                class_obj = Class.objects.get(id=class_id)
                general_exam = GeneralExam.objects.get(id=general_exam_id)

                # Fetch all students in the class
                students = Student.objects.filter(current_class=class_obj, is_active=True)

                # Initialize tracking of created and retrieved items
                created_items = {'extraexamdata': 0}
                retrieved_items = {'extraexamdata': 0}

                # Process students for extra exam data
                for student in students:
                    extra_exam_data, created = ExtraExamData.objects.get_or_create(
                        academic_year=academic_year,
                        class_obj=class_obj,
                        general_exam=general_exam,
                        student=student,
                        defaults={
                            'absences': 0,
                            'conduct': 5,  # default to 'Excellent'
                            'human_investment': 5,  # default to 'Excellent'
                            'fees_owed': 0.00,
                            'participation_in_extracurricular': False,
                            'remarks': ''
                        }
                    )

                    if created:
                        created_items['extraexamdata'] += 1
                        print(f"Created ExtraExamData for student {student.get_full_name()}")
                    else:
                        retrieved_items['extraexamdata'] += 1
                        print(f"Retrieved ExtraExamData for student {student.get_full_name()}")

                # Prepare the student data for JSON format
                students_data = [{
                    'name': student.get_full_name(),
                    'id': student.id
                } for student in students]

                # Fetch existing extra exam data entries for the current class and general exam
                extra_exam_data_entries = ExtraExamData.objects.filter(
                    academic_year=academic_year,
                    class_obj=class_obj,
                    general_exam=general_exam
                ).select_related('student')

                # Serialize extra exam data to be used by JS
                extra_exam_data_json = [
                    {
                        'student': {
                            'id': entry.student.id,
                            'name': entry.student.get_full_name()
                        },
                        'absences': entry.absences,
                        'conduct': entry.conduct,
                        'human_investment': entry.human_investment,
                        'fees_owed': float(entry.fees_owed),
                        'participation_in_extracurricular': entry.participation_in_extracurricular,
                        'remarks': entry.remarks
                    }
                    for entry in extra_exam_data_entries
                ]

                # Prepare the context and JSON encode the data
                context = {
                    'academic_year': academic_year,
                    'class_obj': class_obj,
                    'general_exam': general_exam,
                    'students': json.dumps(students_data),  # Students data in JSON format
                    'extra_exam_data': json.dumps(extra_exam_data_json),  # Extra exam data in JSON format
                    'created_items': json.dumps(created_items),  # Track created items in JSON
                    'retrieved_items': json.dumps(retrieved_items),  # Track retrieved items in JSON
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
def update_extra_exam_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            updated_data = data.get('updated_data', {})

            # Retrieve the academic year, class, and general exam from the request data
            academic_year = AcademicYear.objects.get(id=data['academic_year_id'])
            class_obj = Class.objects.get(id=data['class_id'])
            general_exam = GeneralExam.objects.get(id=data['general_exam_id'])

            print("Received data:", data)
            print("Updated data:", updated_data)

            for student_name, fields in updated_data.items():
                print(f"Processing student: {student_name}")

                # Retrieve all active students in the class
                students_in_class = Student.objects.filter(current_class=class_obj, is_active=True)

                # Concatenate first_name and last_name to match the full name
                matching_students = students_in_class.annotate(
                    full_name=Concat('first_name', Value(' '), 'last_name')
                ).filter(full_name=student_name)

                if matching_students.exists():
                    student = matching_students.first()
                    print(f"Found student: {student.get_full_name()}")
                else:
                    return JsonResponse({'status': 'error', 'message': f"Student {student_name} not found in class {class_obj.name}"})

                # Retrieve the existing ExtraExamData entry for this student, academic year, class, and exam
                try:
                    extra_exam_data = ExtraExamData.objects.get(
                        student=student,
                        academic_year=academic_year,
                        class_obj=class_obj,
                        general_exam=general_exam
                    )
                    print(f"Found ExtraExamData for student: {student.get_full_name()}")
                except ExtraExamData.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': f"ExtraExamData for {student_name} not found."})

                # Update the fields
                extra_exam_data.absences = fields['absences']
                extra_exam_data.conduct = fields['conduct']
                extra_exam_data.human_investment = fields['human_investment']
                extra_exam_data.fees_owed = fields['fees_owed']
                extra_exam_data.participation_in_extracurricular = fields['participation'] == 'Yes'
                extra_exam_data.remarks = fields['remarks']

                # Save the updated data
                extra_exam_data.save()
                print(f"Updated ExtraExamData saved for student: {student_name}")

            return JsonResponse({'status': 'success'})
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})