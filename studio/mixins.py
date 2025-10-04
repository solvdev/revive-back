# from django.db import models
# from rest_framework import status
# from rest_framework.response import Response


class SedeFilterMixin:
    """
    Mixin to add sede filtering capabilities to ViewSets.
    """

    def get_queryset(self):
        """Filter queryset by sede_ids from request."""
        queryset = super().get_queryset()

        # Apply sede filtering if sede_ids are provided
        if hasattr(self.request, "sede_ids") and self.request.sede_ids:
            # Check if the model has a sede field
            if hasattr(queryset.model, "sede"):
                # Use the manager's for_sede method if available
                if hasattr(queryset, 'for_sede'):
                    queryset = queryset.for_sede(self.request.sede_ids[0])
                else:
                    queryset = queryset.filter(sede_id__in=self.request.sede_ids)

        return queryset

    def perform_create(self, serializer):
        """Set sede_id from request when creating objects."""
        # Check if the model has a sede field
        if hasattr(serializer.Meta.model, "sede"):
            # If sede_ids are provided, use the first one
            if hasattr(self.request, "sede_ids") and self.request.sede_ids:
                serializer.save(sede_id=self.request.sede_ids[0])
            else:
                # Try to get sede from user if available
                if hasattr(self.request, 'user_sede') and self.request.user_sede:
                    serializer.save(sede_id=self.request.user_sede.id)
                else:
                    serializer.save()
        else:
            serializer.save()

    def list(self, request, *args, **kwargs):
        """Add sede information to list response."""
        response = super().list(request, *args, **kwargs)

        # Add sede information to response metadata
        # Only add metadata if response.data is a dict (not a list)
        if isinstance(response.data, dict):
            if hasattr(request, "sede_ids") and request.sede_ids:
                response.data["sede_ids"] = request.sede_ids
                response.data["sede_filter_applied"] = True
            else:
                response.data["sede_filter_applied"] = False

        return response


class SedeValidationMixin:
    """
    Mixin to add sede validation for write operations.
    """

    def validate_sede_access(self, sede_id):
        """Validate that the user has access to the specified sede."""
        if not hasattr(self.request, "sede_ids") or not self.request.sede_ids:
            return True  # No sede filtering applied

        return sede_id in self.request.sede_ids

    def validate_membership_scope(self, membership, sede_id):
        """Validate that membership scope matches sede requirements."""
        if membership.scope == "GLOBAL":
            return True  # Global memberships are valid everywhere

        if membership.scope == "SEDE":
            return membership.sede_id == sede_id

        return False

    def validate_schedule_sede(self, schedule, sede_id):
        """Validate that schedule belongs to the specified sede."""
        return schedule.sede_id == sede_id
