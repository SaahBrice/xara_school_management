let data = [];
let subjects = [];
let currentExamId;


function handleGradeChange(input) {
    const studentIndex = parseInt(input.dataset.studentIndex);
    const gradeIndex = parseInt(input.dataset.gradeIndex);
    const newScore = parseFloat(input.value);

    if (isNaN(newScore)) {
        console.error('Invalid score entered');
        return;
    }

    // Update the data
    data[studentIndex].grades[gradeIndex].score = newScore;

    // Recalculate totals and averages
    recalculateStudentStats(studentIndex);

    // Update the UI
    updateStudentRow(studentIndex);

    // Save the changes to the server
    saveGrade(studentIndex, gradeIndex, newScore);
}

function recalculateStudentStats(studentIndex) {
    const student = data[studentIndex];
    student.total = student.grades.reduce((sum, grade) => sum + (parseFloat(grade.score) || 0), 0);
    student.average = student.creditsAttempted > 0 ? student.total / student.creditsAttempted : 0;
    student.remark = student.average >= 10 ? 'PASSED' : 'FAILED';
    
    // Recalculate ranks (simplified version)
    data.sort((a, b) => (b.average || 0) - (a.average || 0));
    data.forEach((student, index) => {
        student.rank = index + 1;
    });
}

function updateStudentRow(studentIndex) {
    const student = data[studentIndex];
    const row = document.querySelector(`#tableContainer tr:nth-child(${studentIndex + 1})`);
    
    if (row) {
        row.children[subjects.length + 1].textContent = isNaN(student.total) ? 'N/A' : Number(student.total).toFixed(2);
        row.children[subjects.length + 2].textContent = student.creditsAttempted;
        row.children[subjects.length + 3].textContent = isNaN(student.average) ? 'N/A' : Number(student.average).toFixed(2);
        row.children[subjects.length + 4].textContent = student.remark;
        row.children[subjects.length + 4].className = student.remark === 'PASSED' ? 'table-success' : 'table-danger';
        row.children[subjects.length + 5].textContent = student.rank;
    }
}

function saveGrade(studentIndex, gradeIndex, newScore) {
    const student = data[studentIndex];
    const grade = student.grades[gradeIndex];
    
    fetch('/users/api/save-grade/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            student_id: student.id,
            subject_id: subjects[gradeIndex].id,
            score: newScore,
            exam_id: currentExamId
        })
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            console.log('Grade saved successfully');
            // Update the input with the rounded score from the server
            const input = document.querySelector(`input[data-student-index="${studentIndex}"][data-grade-index="${gradeIndex}"]`);
            if (input) {
                input.value = result.rounded_score.toFixed(2);
            }
            // Update the data
            data[studentIndex].grades[gradeIndex].score = result.rounded_score;
            // Recalculate and update the UI
            recalculateStudentStats(studentIndex);
            updateStudentRow(studentIndex);
        } else {
            console.error('Failed to save grade:', result.error);
            alert(`Failed to save grade: ${result.error}`);
            // Revert the input to the previous valid value
            const input = document.querySelector(`input[data-student-index="${studentIndex}"][data-grade-index="${gradeIndex}"]`);
            if (input) {
                input.value = grade.score !== null && grade.score !== undefined ? Number(grade.score).toFixed(2) : '';
            }
        }
    })
    .catch(error => {
        console.error('Error saving grade:', error);
        alert(`Error saving grade: ${error}`);
        // Revert the input to the previous valid value
        const input = document.querySelector(`input[data-student-index="${studentIndex}"][data-grade-index="${gradeIndex}"]`);
        if (input) {
            input.value = grade.score !== null && grade.score !== undefined ? Number(grade.score).toFixed(2) : '';
        }
    });
}




function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', function() {
    const academicYearSelect = document.getElementById('academic-year-select');
    const classSelect = document.getElementById('class-select');
    const examSelect = document.getElementById('exam-select');
    const searchInput = document.getElementById('searchInput');
    const tableContainer = document.getElementById('tableContainer');
    const overallStatsContainer = document.getElementById('overallStats');

    academicYearSelect.addEventListener('change', function() {
        fetchClasses(this.value);
    });

    classSelect.addEventListener('change', function() {
        fetchExams(academicYearSelect.value);
    });

    examSelect.addEventListener('change', function() {
        if (this.value) {
            fetchResults(academicYearSelect.value, classSelect.value, this.value);
        }
    });

    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredData = data.filter(student => 
            student.name.toLowerCase().includes(searchTerm)
        );
        renderTable(filteredData);
    });

    function fetchClasses(academicYearId) {
        resetSelect(classSelect);
        resetSelect(examSelect);
        tableContainer.innerHTML = '';

        if (!academicYearId) return;

        fetch(`/users/api/classes/?academic_year=${academicYearId}`)
            .then(response => response.json())
            .then(data => {
                classSelect.disabled = false;
                data.forEach(cls => {
                    const option = new Option(cls.name, cls.id);
                    classSelect.add(option);
                });
            })
            .catch(error => console.error('Error fetching classes:', error));
    }

    function fetchExams(academicYearId) {
        resetSelect(examSelect);
        tableContainer.innerHTML = '';

        if (!academicYearId) return;

        fetch(`/users/api/exams/?academic_year=${academicYearId}`)
            .then(response => response.json())
            .then(data => {
                examSelect.disabled = false;
                data.forEach(exam => {
                    const option = new Option(exam.name, exam.id);
                    examSelect.add(option);
                });
            })
            .catch(error => console.error('Error fetching exams:', error));
    }

    function fetchResults(academicYearId, classId, examId) {
        currentExamId = examId;  // Add this line
        fetch(`/users/api/results/?academic_year=${academicYearId}&class=${classId}&exam=${examId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(responseData => {
                data = responseData.students;
                subjects = responseData.subjects;
                renderTable(data);
                renderOverallStats(responseData.overall_stats);
            })
            .catch(error => {
                console.error('Error fetching results:', error);
                tableContainer.innerHTML = `<p class="text-danger">Error loading results: ${error.message}</p>`;
            });
    }

    function renderTable(data) {
        let tableHTML = `
            <table class="table table-bordered table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>NAME</th>
                        ${subjects.map(subject => `<th class="subject-column">${subject.name} (${subject.credit})</th>`).join('')}
                        <th>TOTAL</th>
                        <th>CREDITS</th>
                        <th>AVER</th>
                        <th>REMARK</th>
                        <th>RANK</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map((student, studentIndex) => `
                        <tr>
                            <td class="clickable text-primary" data-student='${JSON.stringify(student)}'>${student.name}</td>
                            ${student.grades.map((grade, gradeIndex) => `
                                <td>
                                    <input type="number" class="form-control subject-column" 
                                        value="${grade.score !== null && grade.score !== undefined ? Number(grade.score).toFixed(2) : ''}"
                                        data-student-index="${studentIndex}"
                                        data-grade-index="${gradeIndex}"
                                        onchange="handleGradeChange(this)">
                                </td>
                            `).join('')}
                            <td>${student.total !== null && student.total !== undefined ? Number(student.total).toFixed(2) : ''}</td>
                            <td>${student.creditsAttempted}</td>
                            <td>${student.average !== null && student.average !== undefined ? Number(student.average).toFixed(2) : ''}</td>
                            <td class="${student.remark === 'PASSED' ? 'table-success' : 'table-danger'}">${student.remark}</td>
                            <td>${student.rank}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        tableContainer.innerHTML = tableHTML;
    
        // Add event listeners for student details
        document.querySelectorAll('td.clickable').forEach(td => {
            td.addEventListener('click', () => {
                const student = JSON.parse(td.dataset.student);
                showStudentDetails(student);
            });
        });
    }

    function renderOverallStats(stats) {
        overallStatsContainer.innerHTML = `
            <p><strong>Overall Number of students:</strong> ${stats.num_students}</p>
            <p><strong>Overall Number of passes:</strong> ${stats.num_passes}</p>
            <p><strong>Overall Class Average:</strong> ${stats.class_average !== null && stats.class_average !== undefined ? Number(stats.class_average).toFixed(2) : 'N/A'}</p>
            <p><strong>Overall Percentage pass:</strong> ${stats.overall_percentage_pass !== null && stats.overall_percentage_pass !== undefined ? Number(stats.overall_percentage_pass).toFixed(2) : 'N/A'}%</p>
        `;
    }

    function showStudentDetails(student) {
        const modal = new bootstrap.Modal(document.getElementById('modalContainer'));
        const modalBody = document.querySelector('.modal-body');
        modalBody.innerHTML = `
            <h5>${student.name}</h5>
            <table class="table table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>Subject (Credit)</th>
                        <th>Score</th>
                        <th>Rank</th>
                        <th>Teacher</th>
                    </tr>
                </thead>
                <tbody>
                    ${student.grades.map((grade, index) => `
                        <tr>
                            <td>${subjects[index].name} (${subjects[index].credit})</td>
                            <td>${grade.score !== null && grade.score !== undefined ? Number(grade.score).toFixed(2) : 'N/A'}</td>
                            <td>${grade.rank || 'N/A'}</td>
                            <td>${subjects[index].teacher}</td>
                        </tr>
                    `).join('')}
                </tbody>
                <tfoot>
                    <tr>
                        <td>Total Score</td>
                        <td colspan="3">${student.total !== null && student.total !== undefined ? Number(student.total).toFixed(2) : 'N/A'}</td>
                    </tr>
                    <tr>
                        <td>Credits Attempted</td>
                        <td colspan="3">${student.creditsAttempted}</td>
                    </tr>
                    <tr>
                        <td>Average</td>
                        <td colspan="3">${student.average !== null && student.average !== undefined ? Number(student.average).toFixed(2) : 'N/A'}</td>
                    </tr>
                    <tr>
                        <td>Remark</td>
                        <td colspan="3">${student.remark}</td>
                    </tr>
                    <tr>
                        <td>Overall Rank</td>
                        <td colspan="3">${student.rank}</td>
                    </tr>
                </tfoot>
            </table>
        `;
        modal.show();
    }

    function resetSelect(select) {
        select.innerHTML = '<option value="">Select</option>';
        select.disabled = true;
    }
});