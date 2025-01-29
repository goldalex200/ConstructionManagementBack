from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

# from .views import WorkViewSet, WorkItemViewSet, FacilityViewSet, ContractorRatingViewSet, UserRoleListViewSet
from .views import WorkViewSet, WorkItemViewSet, FacilityViewSet, UserRoleListViewSet, PaymentViewSet, CommentViewSet

# router = DefaultRouter()
# router.register(r'works', WorkViewSet, basename='work')
# router.register(r'work-items', WorkItemViewSet, basename='workitem')
# router.register(r'facilities', FacilityViewSet, basename='facility')
# # router.register(r'contractor-ratings', ContractorRatingViewSet, basename='contractorrating')
# router.register(r'user-roles', UserRoleListViewSet, basename='user-roles')
# router.register(r'payments', PaymentViewSet, basename='payment')
#
# urlpatterns = [
#     path('', include(router.urls)),
#     path('auth/', include('dj_rest_auth.urls')),
#     path('auth/registration/', include('dj_rest_auth.registration.urls')),
#     path('api-auth/', include('rest_framework.urls')),  # new
#     path('accounts/', include('allauth.urls')),  # allauth urls
#
# ]

router = DefaultRouter()
router.register(r'works', WorkViewSet, basename='work')
router.register(r'work-items', WorkItemViewSet, basename='workitem')
router.register(r'facilities', FacilityViewSet, basename='facility')
router.register(r'user-roles', UserRoleListViewSet, basename='user-roles')
router.register(r'payments', PaymentViewSet, basename='payment')

# Add nested router for comments
works_router = routers.NestedSimpleRouter(router, r'works', lookup='work')
works_router.register(r'comments', CommentViewSet, basename='work-comments')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(works_router.urls)),  # Add this line
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', include('dj_rest_auth.registration.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('accounts/', include('allauth.urls')),
]