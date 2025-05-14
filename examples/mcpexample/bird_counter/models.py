from django.db import models


# Create your models here.
class Bird(models.Model):
    """
    Inventory of observation of a certain species of birds
    """
    location = models.ForeignKey('Location', on_delete=models.CASCADE, related_name='birds',
                                 null=True, help_text="The location of the observation")
    species = models.CharField(max_length=100)
    count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.species} - Count: {self.count}"


class Location(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    city = models.ForeignKey('City', on_delete=models.CASCADE, related_name='locations', null=True)
    def __str__(self):
        return self.name


class City(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, choices=[
        ('USA', 'United States'),
        ('FRA', 'France'),
        ('CAN', 'Canada'),
        ('MEX', 'Mexico'),
        ('ESP', 'Spain'),
        ('ITA', 'Italy'),
        ('DEU', 'Germany'),
    ], default='USA')

    def __str__(self):
        return f"{self.name}, {self.country}"