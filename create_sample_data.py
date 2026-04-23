#!/usr/bin/env python
"""
Simple script to create sample data for the receptionist app.
Run this script from the project root directory.
"""

from django.core.management import call_command
import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()


def main():
    """Create sample data for the receptionist app."""
    print("Creating sample data for receptionist app...")

    # Create sample data with default parameters
    # You can modify these values as needed
    call_command('create_business_types')
    call_command('create_sample_businesses')
    call_command('create_sample_services')
    call_command('create_sample_staff',
                 per_business=3,
                 assign_services=True)
    # Notifications sample data
    # call_command('create_sample_notifications', per_business=10, push_devices_per_business=3)
    # # Receptionist sample data
    # call_command('create_receptionist_sample_data')
    # # Appointment sample data
    # call_command('create_appointment_samples', per_business=15, days_ahead=30, include_past=True)

    print("Sample data creation completed!")
    print("\nYou can now:")
    print("1. Check the Django admin interface at /admin/")
    print("2. Use the REST API endpoints to query the data")
    print("3. Run the sample data command again with different parameters")


if __name__ == '__main__':
    main()
