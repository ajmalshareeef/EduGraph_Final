import os
import re
import pdfplumber
from collections import defaultdict
from django.shortcuts import render, redirect
from django.conf import settings
from django.core.files.storage import default_storage
from django.template.loader import get_template
from django.http import HttpResponse
from datetime import datetime
from .models import Student, FailedSubject
from xhtml2pdf import pisa

def index(request):
 return render(request, 'home.html')


def extract_exam_details(text):
    lines = text.split("\n")
    exam_name = next((line.replace("Examination", "").strip() for line in lines if "Examination" in line), "Unknown")
    programme_name = next((match.group(1).strip() for match in [re.search(r"Programme\s+([^\n]+)", text)] if match), "Unknown")
    return exam_name, programme_name


def check_pass_fail_and_sgpa(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(filter(None, (page.extract_text() for page in pdf.pages)))
    
    exam_name, programme_name = extract_exam_details(text)
    student_name = next((line.replace("Name ", "").strip() for line in text.split("\n") if line.startswith("Name ")), "Unknown")
    sgpa = float(next((match.group(1) for match in [re.search(r"SGPA\s*:\s*([\d.]+)", text)] if match), 0.0))
    failed_subjects = [" ".join(line.split()[1:-4]).rsplit(" ", 1)[0].strip() for line in text.split("\n") if line.endswith("Failed")]
    
    return "fail" if failed_subjects else "pass", student_name, failed_subjects, sgpa, exam_name, programme_name


def process_pdfs(request):
    if request.method == 'POST' and request.FILES.getlist('pdf_files'):
        Student.objects.all().delete()
        FailedSubject.objects.all().delete()

        for pdf_file in request.FILES.getlist('pdf_files'):
            file_path = default_storage.save(pdf_file.name, pdf_file)
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            result, student_name, failed_subjects, sgpa, exam_name, programme_name = check_pass_fail_and_sgpa(full_path)
            
            student = Student.objects.create(name=student_name, sgpa=sgpa, result=result)
            FailedSubject.objects.bulk_create([FailedSubject(student=student, subject_name=subj) for subj in failed_subjects])
            os.remove(full_path)

        request.session.update({'exam_name': exam_name, 'programme_name': programme_name})
        return redirect('results')
    return render(request, 'upload.html')


def show_results(request):
    students = Student.objects.all()
    failed_students = students.filter(result='fail')
    
    subject_fail_count = defaultdict(int)
    for subject in FailedSubject.objects.values_list('subject_name', flat=True):
        subject_fail_count[subject] += 1
    
    sorted_students = sorted(students, key=lambda s: s.sgpa, reverse=True)
    
    top_ranks, rank, prev_sgpa = [], 0, None
    for student in sorted_students:
        if prev_sgpa != student.sgpa:
            rank += 1
            if rank > 3:
                break
            top_ranks.append((rank, [(student.name, student.sgpa)]))
        else:
            top_ranks[-1][1].append((student.name, student.sgpa))
        prev_sgpa = student.sgpa

    return render(request, 'results.html', {
        'total_students': students.count(),
        'total_pass': students.filter(result='pass').count(),
        'total_fail': failed_students.count(),
        'failed_students': failed_students,
        'subject_fail_count': list(subject_fail_count.items()),
        'top_students': top_ranks,
        'current_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'exam_name': request.session.get('exam_name', 'Unknown'),
        'programme_name': request.session.get('programme_name', 'Unknown')
    })


def generate_pdf(html_content):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="results.pdf"'
    if pisa.CreatePDF(html_content, dest=response).err:
        return HttpResponse("Error generating PDF", content_type='text/plain')
    return response


def download_results_pdf(request):
    students = Student.objects.all()
    failed_students = students.filter(result='fail')
    
    subject_fail_count = defaultdict(int)
    for subject in FailedSubject.objects.values_list('subject_name', flat=True):
        subject_fail_count[subject] += 1
    
    sorted_students = sorted(students, key=lambda s: s.sgpa, reverse=True)
    
    top_ranks, rank, prev_sgpa = [], 0, None
    for student in sorted_students:
        if prev_sgpa != student.sgpa:
            rank += 1
            if rank > 3:
                break
            top_ranks.append((rank, [(student.name, student.sgpa)]))
        else:
            top_ranks[-1][1].append((student.name, student.sgpa))
        prev_sgpa = student.sgpa

    context = {
        'total_students': students.count(),
        'total_pass': students.filter(result='pass').count(),
        'total_fail': failed_students.count(),
        'failed_students': failed_students,
        'subject_fail_count': list(subject_fail_count.items()),
        'top_students': top_ranks,
        'current_date': datetime.now().strftime('%d/%m/%y'),
        'current_time': datetime.now().strftime('%I:%M %p'),
        'exam_name': request.session.get('exam_name', 'Unknown'),
        'programme_name': request.session.get('programme_name', 'Unknown')
    }
    return generate_pdf(get_template('download.html').render(context))
