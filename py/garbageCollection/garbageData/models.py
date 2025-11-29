from django.db import models
from django.utils import timezone
from datetime import timedelta

class TrashCan(models.Model):
    id = models.IntegerField(primary_key=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    last_emptied = models.DateTimeField(default=timezone.now, help_text="Last time bin was emptied")

    def __str__(self):
        return f"TrashCan {self.id} ({self.latitude}, {self.longitude})"
    
    def get_average_daily_fill_rate(self):
        """
        Calculate average fill rate per day based on collection cycles.
        
        LOGIC:
        1. Get last 30 days of records
        2. Find "collection events" (where fill level drops from >70% to <20%)
        3. For each cycle: calculate days from empty to full
        4. Average fill rate = (final_fill_level) / (days_in_cycle)
        5. Return average across all cycles
        """
        thirty_days_ago = timezone.now() - timedelta(days=30)
        records = self.fill_records.filter(timestamp__gte=thirty_days_ago).order_by('timestamp')
        
        if records.count() < 2:
            return 10.0  # Default if no history
        
        fill_rates = []
        cycle_start_time = None
        cycle_start_level = 0
        previous_level = 0
        
        for record in records:
            current_level = min(record.fill_level, 100)  # Normalize overflow
            
            # Detect collection event (drop from high to low)
            if previous_level > 70 and current_level < 20:
                # End of cycle - calculate fill rate
                if cycle_start_time:
                    days_in_cycle = (record.timestamp - cycle_start_time).total_seconds() / 86400
                    if days_in_cycle > 0.1:  # At least 2.4 hours
                        # Fill rate = how much it filled / days it took
                        fill_rate = previous_level / days_in_cycle
                        fill_rates.append(fill_rate)
                
                # Start new cycle
                cycle_start_time = record.timestamp
                cycle_start_level = current_level
            elif cycle_start_time is None:
                # First record - start tracking
                cycle_start_time = record.timestamp
                cycle_start_level = current_level
            
            previous_level = current_level
        
        # If we have an ongoing cycle, calculate its rate too
        if cycle_start_time and previous_level > 20:
            days_in_cycle = (timezone.now() - cycle_start_time).total_seconds() / 86400
            if days_in_cycle > 0.1:
                fill_rate = previous_level / days_in_cycle
                fill_rates.append(fill_rate)
        
        # Return average of all rates, or default
        if fill_rates:
            avg_rate = sum(fill_rates) / len(fill_rates)
            return round(avg_rate, 2)
        else:
            return 10.0
    
    def get_predicted_fill_level(self):
        """
        Calculate predicted current fill level.
        
        LOGIC:
        1. Days since last emptied
        2. Multiply by average daily fill rate = predicted fill
        3. Get latest actual reading (if recent)
        4. Weight: 70% predicted + 30% latest reading
        5. Allow >100% for overflow prediction
        """
        days_since_emptied = (timezone.now() - self.last_emptied).total_seconds() / 86400
        daily_rate = self.get_average_daily_fill_rate()
        
        # Prediction based on time and fill rate
        time_based_prediction = days_since_emptied * daily_rate
        
        # Get latest reading (within last 24 hours)
        latest_record = self.fill_records.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-timestamp').first()
        
        if latest_record:
            # Weight: 60% time-based, 40% latest reading
            weighted_prediction = (time_based_prediction * 0.6) + (latest_record.fill_level * 0.4)
        else:
            # No recent reading, use time-based prediction only
            weighted_prediction = time_based_prediction
        
        # Allow overflow (>100%)
        return max(0, round(weighted_prediction, 1))
    
    def get_days_until_full(self):
        """
        Estimate days until bin reaches 100%.
        
        LOGIC:
        1. Current predicted fill level
        2. If already ≥100%, return 0
        3. Otherwise: (100 - current) / daily_rate
        """
        current_fill = self.get_predicted_fill_level()
        daily_rate = self.get_average_daily_fill_rate()
        
        if current_fill >= 100:
            return 0.0
        
        if daily_rate <= 0:
            return 999.0
        
        days_until_full = (100 - current_fill) / daily_rate
        return max(0, round(days_until_full, 1))
    
    def mark_as_emptied(self):
        """
        Mark bin as emptied (called after collection).
        
        LOGIC:
        1. Set last_emptied to now
        2. Create a 0% fill record
        """
        self.last_emptied = timezone.now()
        self.save()
        FillRecord.objects.create(trashcan=self, fill_level=0, source='manual')

    class Meta:
        verbose_name = "Trash Can"
        verbose_name_plural = "Trash Cans"

class FillRecord(models.Model):
    trashcan = models.ForeignKey(TrashCan, on_delete=models.CASCADE, related_name='fill_records')
    fill_level = models.IntegerField(default=0, help_text="Fill level (0-110, >100 means overflowing)")
    timestamp = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=20, default='manual', 
                             choices=[('manual', 'Manual'), ('ai', 'AI Camera'), ('predicted', 'Predicted')])

    def __str__(self):
        overflow_indicator = " [OVERFLOW]" if self.fill_level > 100 else ""
        return f"TrashCan {self.trashcan.id}: {self.fill_level}%{overflow_indicator} at {self.timestamp}"

    class Meta:
        verbose_name = "Fill Record"
        verbose_name_plural = "Fill Records"
        ordering = ['-timestamp']
