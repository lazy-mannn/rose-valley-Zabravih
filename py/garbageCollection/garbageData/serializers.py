from rest_framework import serializers
from .models import TrashCan, FillRecord


class FillRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FillRecord
        fields = ['id', 'fill_level', 'timestamp', 'source']


class TrashCanSerializer(serializers.ModelSerializer):
    fill_level = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = TrashCan
        fields = [
            'id', 'latitude', 'longitude',
            'district_id', 'district_name',
            'waste_type', 'bin_status',
            'capacity_volume', 'bin_count',
            'last_cleaned', 'fill_level',
        ]
