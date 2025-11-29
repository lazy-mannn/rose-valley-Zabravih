from django.db import models

# Create your models here.


class TrashCan(models.Model):
    """
    Basic data for every trash can.
    """
    id = models.AutoField(primary_key=True)
    can_map_coordinates = models.TextField()

    def __str__(self):
        return f"TrashCan {self.id}"


class FillRecord(models.Model):
    """
    Records of trash collection events.
    """
    trash_can = models.ForeignKey(
        TrashCan, 
        on_delete=models.CASCADE, 
        related_name='fills'
    )
    date = models.DateField()
    fullness_percent = models.FloatField()
    efpdc = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"Can {self.trash_can.id} | {self.date} | {self.fullness_percent}% | EFPDC: {self.efpdc}"
