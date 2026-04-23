import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from receptionist.models import (
    AIConfiguration, CallSession, ConversationMessage,
    Intent, AudioRecording, SystemLog
)
from business.models import Business  # Ensure Business is imported

from faker import Faker

class Command(BaseCommand):
    help = 'Create sample data for the receptionist app'

    def add_arguments(self, parser):
        parser.add_argument(
            '--businesses', type=int, default=3,
            help='Number of businesses to create (default: 3)'
        )
        parser.add_argument(
            '--calls-per-business', type=int, default=5,
            help='Number of calls per business (default: 5)'
        )
        parser.add_argument(
            '--clear-existing', action='store_true',
            help='Clear existing data before creating new sample data'
        )

    def handle(self, *args, **options):
        num_businesses = options['businesses']
        calls_per_business = options['calls_per_business']
        clear_existing = options['clear_existing']

        if clear_existing:
            self.stdout.write('Clearing existing receptionist data...')
            self.clear_existing_data()

        self.stdout.write(f'Creating {num_businesses} businesses with {calls_per_business} calls each...')

        businesses = self.create_sample_businesses(num_businesses)

        for business in businesses:
            self.create_sample_calls(business, calls_per_business)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created sample data: {num_businesses} businesses, '
                f'{num_businesses * calls_per_business} calls'
            )
        )

    def clear_existing_data(self):
        """Clear all existing receptionist-related data in the correct order."""
        SystemLog.objects.all().delete()
        AudioRecording.objects.all().delete()
        Intent.objects.all().delete()
        ConversationMessage.objects.all().delete()
        CallSession.objects.all().delete()
        AIConfiguration.objects.all().delete()
        Business.objects.all().delete()

    def create_sample_businesses(self, count):
        """Create sample businesses and their AI configurations."""
        sample_businesses =  Business.objects.all()
        businesses = []
        for business in sample_businesses[:count]:
           
            AIConfiguration.objects.create(
                business=business,
                ai_name='Sarah',
                greeting_message=Faker().sentence(),
                language=Faker().language_code(),
                voice_provider=Faker().language_code(),
                stt_provider=Faker().language_code(),
                model_name=Faker().language_code(),
                temperature=random.uniform(0.1, 1.0),
                max_tokens=random.randint(100, 1000),
                webhook_url=Faker().url()
            )
            businesses.append(business)
            self.stdout.write(f'Created business: {business.name}')
        return businesses

    def create_sample_calls(self, business, count):
        """Create sample call sessions, messages, intents, audio, and logs for a business."""
        call_scenarios = [
            {
                'type': 'booking',
                'messages': [
                    ('user', "Hi, I'd like to book an appointment for a haircut"),
                    ('assistant', "I'd be happy to help you book an appointment! What day works best for you?"),
                    ('user', "How about next Tuesday afternoon?"),
                    ('assistant', "Let me check our availability for Tuesday afternoon. What time would you prefer?"),
                    ('user', "Around 2 PM if possible"),
                    ('assistant', "Perfect! I have 2:00 PM available on Tuesday. May I get your name and phone number?"),
                    ('user', "My name is John Smith and my number is 416-555-1234"),
                    ('assistant', "Great! I've booked you for Tuesday at 2:00 PM. Is there anything else I can help you with?"),
                    ('user', "No, that's perfect. Thank you!"),
                    ('assistant', "You're welcome! We'll see you Tuesday at 2:00 PM. Have a great day!")
                ],
                'intents': [
                    ('book_appointment', 0.95, {'service': 'haircut', 'date': 'Tuesday', 'time': '2:00 PM'}),
                    ('provide_contact_info', 0.90, {'name': 'John Smith', 'phone': '416-555-1234'})
                ],
                'duration': lambda: random.randint(180, 480),
                'status': 'completed'
            },
            {
                'type': 'inquiry',
                'messages': [
                    ('user', "What are your hours?"),
                    ('assistant', "We're open Monday to Friday 9 AM to 7 PM, and Saturday 10 AM to 5 PM. We're closed on Sundays."),
                    ('user', "Do you offer hair coloring services?"),
                    ('assistant', "Yes, we do! We offer full hair coloring, highlights, and color corrections. Would you like to book a consultation?"),
                    ('user', "Maybe later, thanks for the info"),
                    ('assistant', "You're welcome! Feel free to call back anytime to book. Have a great day!")
                ],
                'intents': [
                    ('inquire_hours', 0.92, {}),
                    ('inquire_services', 0.88, {'service': 'hair coloring'})
                ],
                'duration': lambda: random.randint(120, 300),
                'status': 'completed'
            },
            {
                'type': 'cancellation',
                'messages': [
                    ('user', "I need to cancel my appointment for tomorrow"),
                    ('assistant', "I'd be happy to help you cancel. May I get your name and the appointment details?"),
                    ('user', "It's Sarah Johnson, I have an appointment at 3 PM"),
                    ('assistant', "I found your appointment for Sarah Johnson at 3 PM tomorrow. I'll cancel that for you."),
                    ('user', "Thank you"),
                    ('assistant', "You're welcome! Is there anything else I can help you with today?"),
                    ('user', "No, that's all"),
                    ('assistant', "Have a great day!")
                ],
                'intents': [
                    ('cancel_appointment', 0.93, {'name': 'Sarah Johnson', 'time': '3:00 PM'})
                ],
                'duration': lambda: random.randint(90, 240),
                'status': 'completed'
            },
            {
                'type': 'failed_call',
                'messages': [
                    ('user', "Hello?"),
                    ('assistant', "Hello! How can I help you today?"),
                    ('user', "I can barely hear you"),
                    ('assistant', "I apologize for the audio issues. Can you hear me better now?"),
                    ('user', "No, this is too difficult"),
                    ('assistant', "I understand. Would you like to try calling back?")
                ],
                'intents': [
                    ('audio_issue', 0.85, {})
                ],
                'duration': lambda: random.randint(30, 120),
                'status': 'failed'
            }
        ]

        for _ in range(count):
            scenario = random.choice(call_scenarios)
            duration = scenario['duration']()
            call_sid = f'CA{str(uuid.uuid4()).replace("-", "")[:30]}'
            start_time = timezone.now() - timedelta(days=random.randint(1, 30))
            end_time = start_time + timedelta(seconds=duration)

            call = CallSession.objects.create(
                business=business,
                direction='inbound',
                caller_number=f'+1-416-555-{random.randint(1000, 9999)}',
                receiver_number=business.phone_number,
                call_sid=call_sid,
                started_at=start_time,
                ended_at=end_time,
                duration_seconds=duration,
                status=scenario['status'],
                transcript_summary=Faker().sentence()
            )

            self._create_conversation_messages(call, scenario['messages'])
            self._create_intents(call, scenario['intents'])
            if scenario['status'] == 'completed':
                self._create_audio_recording(call)
            self._create_system_logs(call, scenario['status'])

            self.stdout.write(f'  Created call {call_sid} ({scenario["type"]}) - {duration}s')

    def _create_conversation_messages(self, call, messages):
        """Create conversation messages for a call."""
        base_time = call.started_at
        total = len(messages)
        for i, (role, content) in enumerate(messages):
            message_time = base_time + timedelta(seconds=(i * call.duration_seconds / total))
            ConversationMessage.objects.create(
                call=call,
                role=role,
                content=content,
                timestamp=message_time,
                confidence_score=random.uniform(0.85, 0.98) if role == 'user' else None
            )

    def _create_intents(self, call, intents):
        """Create intent records for a call."""
        base_time = call.started_at
        for i, (name, confidence, data) in enumerate(intents):
            Intent.objects.create(
                call=call,
                name=name,
                confidence=confidence,
                extracted_data=data,
                created_at=base_time + timedelta(seconds=i * 30)
            )

    def _create_audio_recording(self, call):
        """Create audio recording reference."""
        user_msgs = call.messages.filter(role='user')
        transcription = ' '.join([msg.content for msg in user_msgs])
        AudioRecording.objects.create(
            call=call,
            audio_url=f'https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/{call.call_sid}.mp3',
            duration_seconds=call.duration_seconds,
            transcription_text=transcription,
        )

    def _create_system_logs(self, call, status):
        """Create system logs for a call."""
        logs = [
            ('info', 'Call initiated', {'call_sid': call.call_sid}),
            ('info', 'AI assistant activated', {'model': call.business.ai_configs.first().model_name}),
        ]
        if status == 'completed':
            logs.extend([
                ('info', 'Call completed successfully', {'duration': call.duration_seconds}),
                ('info', 'Transcript generated', {'message_count': call.messages.count()}),
            ])
        elif status == 'failed':
            logs.append(('error', 'Call failed due to audio issues', {'error_type': 'audio_quality'}))

        base_time = call.started_at
        for i, (level, message, metadata) in enumerate(logs):
            SystemLog.objects.create(
                call=call,
                level=level,
                message=message,
                metadata=metadata,
                created_at=base_time + timedelta(seconds=i * 10)
            )
