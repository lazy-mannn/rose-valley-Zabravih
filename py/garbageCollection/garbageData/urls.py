from django.urls import path
from . import views

app_name = 'garbageData'

urlpatterns = [
    path('', views.home, name='home'),
    path('pitch/', views.pitch, name='pitch'),

    # Map generation endpoints (legacy Folium)
    path('api/heatmap/', views.generate_heatmap_view, name='generate_heatmap'),
    path('api/route/', views.generate_route_view, name='generate_route'),

    # API endpoints for Raspberry Pi (do not remove)
    path('api/trashcan/<int:trashcan_id>/', views.api_get_trashcan, name='api_get_trashcan'),
    path('api/update/', views.api_update_fill_level, name='api_update_fill_level'),
    path('api/emptied/', views.api_mark_emptied, name='api_mark_emptied'),
    path('api/trashcans/', views.api_list_trashcans, name='api_list_trashcans'),

    # Phase 2: public DRF endpoints for Next.js frontend
    path('api/bins/clusters/', views.BinClustersView.as_view(), name='bins_clusters'),
    path('api/bins/viewport/', views.BinViewportView.as_view(), name='bins_viewport'),
    path('api/districts/', views.DistrictsView.as_view(), name='districts'),
]