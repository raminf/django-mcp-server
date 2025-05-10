from django.db import models


# Create your models here.
class Bird(models.Model):
    species = models.CharField(max_length=100)
    count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.species} - Count: {self.count}"