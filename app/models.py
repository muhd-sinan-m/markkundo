# Re-export all models from the root-level models module so that
# `from app.models import ...` works correctly.
from models import User, Student, Mark, MLInsight, Notification, Subject

__all__ = ['User', 'Student', 'Mark', 'MLInsight', 'Notification', 'Subject']
