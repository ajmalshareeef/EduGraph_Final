from django.db import models

# Create your models here.
class Student(models.Model):
    name = models.CharField(max_length=255)
    sgpa = models.FloatField()
    result = models.CharField(max_length=10)  # 'pass' or 'fail'

    def __str__(self):
        return self.name

class FailedSubject(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='failed_subjects')
    subject_name = models.CharField(max_length=255)

    def __str__(self):
        return self.subject_name