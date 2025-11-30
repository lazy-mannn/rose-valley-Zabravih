from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets

class TrashCan(models.Model):
    id = models.IntegerField(primary_key=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    last_emptied = models.DateTimeField(default=timezone.now)
    nfc_uid = models.CharField(max_length=50, blank=True, null=True, unique=True, 
                                help_text="NFC tag UID (hardware address)")

    def __str__(self):
        return f"Bin {self.id}" + (f" (NFC: {self.nfc_uid})" if self.nfc_uid else "")
    
    @classmethod
    def get_by_nfc_uid(cls, uid):
        """Find bin by NFC UID"""
        try:
            return cls.objects.get(nfc_uid=uid)
        except cls.DoesNotExist:
            return None
    
    def get_average_daily_fill_rate(self):
        """Calculate fill rate from collection cycles"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        records = self.fill_records.filter(timestamp__gte=thirty_days_ago).order_by('timestamp')
        
        if records.count() < 4:
            return 10.0
        
        fill_rates = []
        cycle_start = None
        prev_level = 0
        
        for record in records:
            current = record.fill_level
            
            if prev_level >= 70 and current <= 20:
                if cycle_start:
                    hours = (record.timestamp - cycle_start).total_seconds() / 3600
                    days = hours / 24
                    
                    if 1 <= hours <= 480:
                        rate = prev_level / days
                        fill_rates.append(min(rate, 50))
                
                cycle_start = record.timestamp
            
            elif cycle_start is None and current <= 20:
                cycle_start = record.timestamp
            
            prev_level = current
        
        if cycle_start and prev_level >= 30:
            hours = (timezone.now() - cycle_start).total_seconds() / 3600
            days = hours / 24
            if 1 <= hours <= 480:
                rate = prev_level / days
                fill_rates.append(min(rate, 50))
        
        return round(sum(fill_rates) / len(fill_rates), 1) if fill_rates else 10.0
    
    def get_predicted_fill_level(self):
        """Predict current fill based on time + rate"""
        hours_since = (timezone.now() - self.last_emptied).total_seconds() / 3600
        days_since = hours_since / 24
        
        daily_rate = self.get_average_daily_fill_rate()
        predicted = days_since * daily_rate
        
        latest = self.fill_records.filter(
            timestamp__gte=timezone.now() - timedelta(hours=12)
        ).order_by('-timestamp').first()
        
        if latest:
            predicted = (predicted * 0.7) + (latest.fill_level * 0.3)
        
        return max(0, round(predicted, 1))
    
    def get_days_until_full(self):
        """Days until 100% full"""
        current = self.get_predicted_fill_level()
        rate = self.get_average_daily_fill_rate()
        
        if current >= 100:
            return 0.0
        if rate <= 0:
            return 99.9
        
        return round((100 - current) / rate, 1)
    
    def mark_as_emptied(self):
        """Mark bin as collected"""
        self.last_emptied = timezone.now()
        self.save()
        FillRecord.objects.create(trashcan=self, fill_level=0, source='manual')

    class Meta:
        verbose_name = "Trash Can"
        verbose_name_plural = "Trash Cans"


class FillRecord(models.Model):
    trashcan = models.ForeignKey(TrashCan, on_delete=models.CASCADE, related_name='fill_records')
    fill_level = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=20, default='manual', 
                             choices=[('manual', 'Manual'), ('ai', 'AI'), ('predicted', 'Predicted')])

    def __str__(self):
        overflow = " ⚠️ OVERFLOW" if self.fill_level > 100 else ""
        return f"Bin {self.trashcan.id}: {self.fill_level}%{overflow}"

    class Meta:
        ordering = ['-timestamp']


class APIKey(models.Model):
    """Simple API key for Raspberry Pi authentication"""
    key = models.CharField(max_length=64, unique=True, db_index=True)
    device_name = models.CharField(max_length=100, help_text="Device identifier (e.g., 'RPi-Truck-1')")
    description = models.TextField(blank=True, help_text="Optional notes")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="Disable key without deleting it")
    
    def __str__(self):
        return f"{self.device_name} ({'Active' if self.is_active else 'Inactive'})"
    
    @staticmethod
    def generate_key():
        """Generate secure random API key"""
        return secrets.token_urlsafe(48)
    
    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ['-created_at']
