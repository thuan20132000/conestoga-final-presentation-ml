from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from review.models import Review
from appointment.models import Appointment, AppointmentStatusType
from client.models import Client
from business.models import Business, BusinessType
from payment.models import PaymentStatusType, PaymentMethodType


class ReviewModelTestCase(TestCase):
    """Test cases for Review model"""
    
    def setUp(self):
        """Set up test data"""
        business_type = BusinessType.objects.create(name="Test Business Type")
        self.business = Business.objects.create(
            name="Test Business",
            business_type=business_type,
            email="test@business.com",
            phone_number="1234567890",
            address="123 Main St, Anytown, USA",
            city="Anytown",
            state_province="ON",
            postal_code="12345",
            country="Canada"
        )
        
        self.client_obj = Client.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="1234567890",
            primary_business=self.business
        )
        
        self.appointment = Appointment.objects.create(
            business=self.business,
            client=self.client_obj,
            appointment_date=date.today(),
            status=AppointmentStatusType.CHECKED_OUT,
            payment_status=PaymentStatusType.COMPLETED,
            completed_at=timezone.now()
        )
    
    def test_review_creation(self):
        """Test creating a review"""
        review = Review.objects.create(
            appointment=self.appointment,
            client=self.client_obj,
            rating=5,
            comment="Great service!"
        )
        
        self.assertIsNotNone(review.id)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Great service!")
        self.assertTrue(review.is_visible)
        self.assertTrue(review.is_verified)  # Should be auto-verified if appointment is completed
        self.assertIsNotNone(review.reviewed_at)
    
    def test_review_auto_verification(self):
        """Test that review is auto-verified when appointment is completed"""
        review = Review.objects.create(
            appointment=self.appointment,
            client=self.client_obj,
            rating=4
        )
        
        self.assertTrue(review.is_verified)
    
    def test_review_unique_constraint(self):
        """Test that only one review per appointment is allowed"""
        Review.objects.create(
            appointment=self.appointment,
            client=self.client_obj,
            rating=5
        )
        
        # Try to create another review for the same appointment
        with self.assertRaises(Exception):
            Review.objects.create(
                appointment=self.appointment,
                client=self.client_obj,
                rating=4
            )
    
    def test_review_str_representation(self):
        """Test review string representation"""
        review = Review.objects.create(
            appointment=self.appointment,
            client=self.client_obj,
            rating=5
        )
        
        self.assertIn("Review", str(review))
        self.assertIn("5", str(review))
    
    def test_review_is_recent_property(self):
        """Test is_recent property"""
        review = Review.objects.create(
            appointment=self.appointment,
            client=self.client_obj,
            rating=5
        )
        
        self.assertTrue(review.is_recent)
        
        # Set reviewed_at to 8 days ago
        review.reviewed_at = timezone.now() - timedelta(days=8)
        review.save()
        
        self.assertFalse(review.is_recent)