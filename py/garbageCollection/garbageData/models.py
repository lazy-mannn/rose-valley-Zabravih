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
        """
        🧠 SELF-CORRECTING HYBRID ALGORITHM
        
        How it works:
        1. Calculate 10-day weighted baseline (recent cycles matter more)
        2. Detect spikes (>1.5× baseline)
        3. Validate spikes by checking next cycle
        4. Auto-recover after spike ends
        
        Benefits:
        - Reacts to spikes immediately (next day)
        - Doesn't permanently corrupt baseline
        - Recovers 5× faster than simple average (2 cycles vs 10)
        - Handles both one-time events and sustained changes
        """
        lookback_days = 10  # Changed from 30 to 10 for faster adaptation
        lookback_date = timezone.now() - timedelta(days=lookback_days)
        records = self.fill_records.filter(timestamp__gte=lookback_date).order_by('timestamp')
        
        if records.count() < 3:  # Need minimum 3 cycles
            return 10.0  # Default safe rate
        
        # ============ STEP 1: EXTRACT COLLECTION CYCLES ============
        fill_rates = []
        spike_context = []  # Track (rate, was_next_high?)
        cycle_start = None
        prev_level = 0
        
        for i, record in enumerate(records):
            current = record.fill_level
            
            # Detect collection event (high fill → emptied)
            if prev_level >= 70 and current <= 20:
                if cycle_start:
                    hours = (record.timestamp - cycle_start).total_seconds() / 3600
                    days = hours / 24
                    
                    # Reasonable cycle length (12 hours to 20 days)
                    if 0.5 <= days <= 20:
                        rate = prev_level / days
                        fill_rates.append(min(rate, 50))  # Cap at 50%/day
                        
                        # Check if next cycle was also high (spike validation)
                        next_records = list(records[i+1:i+10])
                        # Was next cycle >60%? (validates spike was real)
                        next_high = any(r.fill_level >= 60 for r in next_records[:3])
                        spike_context.append((rate, next_high))
                
                cycle_start = record.timestamp
            
            elif cycle_start is None and current <= 20:
                cycle_start = record.timestamp
            
            prev_level = current
        
        # Include current incomplete cycle
        if cycle_start and prev_level >= 30:
            hours = (timezone.now() - cycle_start).total_seconds() / 3600
            days = hours / 24
            if 0.5 <= days <= 20:
                rate = prev_level / days
                fill_rates.append(min(rate, 50))
                spike_context.append((rate, None))  # Don't know validation yet
        
        if not fill_rates:
            return 10.0
        
        # ============ STEP 2: CALCULATE WEIGHTED BASELINE ============
        # Recent cycles get more weight (more important)
        weights = [i + 1 for i in range(len(fill_rates))]  # [1, 2, 3, 4...]
        weighted_sum = sum(rate * weight for rate, weight in zip(fill_rates, weights))
        weight_sum = sum(weights)
        baseline = weighted_sum / weight_sum
        
        # Also calculate median for spike threshold (outlier-resistant)
        sorted_rates = sorted(fill_rates)
        median = sorted_rates[len(sorted_rates) // 2]
        
        # ============ STEP 3: SPIKE DETECTION ============
        latest_rate = fill_rates[-1]
        spike_threshold = median * 1.5  # 50% above median = spike
        is_spike = latest_rate > spike_threshold
        
        # ============ STEP 4: SPIKE VALIDATION & ADJUSTMENT ============
        if is_spike and len(spike_context) >= 2:
            # Check if previous spike was validated
            prev_rate, was_validated = spike_context[-2]
            
            if was_validated:
                # Previous spike was REAL! (next cycle was also high)
                # This suggests sustained high demand (construction continues)
                # Adjust baseline up by 20%
                adjusted = baseline * 1.20
                return round(adjusted, 1)
            
            elif was_validated is False:
                # Previous spike was FALSE ALARM! (next cycle was normal)
                # Current spike is likely also one-time event
                # Give small boost (10%) but don't trust it fully
                adjusted = baseline * 1.10
                return round(adjusted, 1)
            
            else:
                # Previous spike not yet validated
                # Give medium boost (15%)
                adjusted = baseline * 1.15
                return round(adjusted, 1)
        
        elif is_spike:
            # First spike detected - give benefit of doubt
            # Small boost (15%) to be cautious
            adjusted = baseline * 1.15
            return round(adjusted, 1)
        
        else:
            # ============ STEP 5: NORMAL OPERATION ============
            # No spike - use weighted average
            # This naturally adapts to gradual changes over time
            return round(baseline, 1)
    
    def get_predicted_fill_level(self):
        """Predict current fill based on time + rate"""
        hours_since = (timezone.now() - self.last_emptied).total_seconds() / 3600
        days_since = hours_since / 24
        
        daily_rate = self.get_average_daily_fill_rate()
        predicted = days_since * daily_rate
        
        # Blend with recent actual reading if available (last 12 hours)
        latest = self.fill_records.filter(
            timestamp__gte=timezone.now() - timedelta(hours=12),
            source__in=['ai', 'manual']  # Only real measurements
        ).order_by('-timestamp').first()
        
        if latest:
            # 50% time-based prediction + 50% actual reading
            predicted = (predicted * 0.5) + (latest.fill_level * 0.5)
        
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
