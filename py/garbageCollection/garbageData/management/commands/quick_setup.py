from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = "Complete system setup in one command"

    def add_arguments(self, parser):
        parser.add_argument('--fast', action='store_true', help='Fast fill rates (for testing)')
        parser.add_argument('--slow', action='store_true', help='Slow fill rates (realistic)')
        parser.add_argument('--days', type=int, default=7, help='Days of history to generate (default: 7)')

    def handle(self, *args, **options):
        days = options['days']
        
        self.stdout.write(self.style.SUCCESS("\n" + "="*70))
        self.stdout.write(self.style.SUCCESS("🚀 QUICK SETUP - COMPLETE SYSTEM INITIALIZATION"))
        self.stdout.write(self.style.SUCCESS("="*70 + "\n"))
        
        # Step 1: Reset
        self.stdout.write(self.style.WARNING("Step 1/4: Resetting system..."))
        call_command('reset_system')
        
        # Step 2: Create bins
        self.stdout.write(self.style.WARNING("\nStep 2/4: Creating 250 bins..."))
        call_command('initialfill')
        
        # Step 3: Generate data with proper arguments
        self.stdout.write(self.style.WARNING(f"\nStep 3/4: Generating {days} days of historical data..."))
        
        gen_args = ['--days', str(days)]
        
        if options['fast']:
            gen_args.append('--fast')
        elif options['slow']:
            gen_args.append('--slow')
        
        call_command('generate_realistic_data', *gen_args)
        
        # Step 4: Update predictions
        self.stdout.write(self.style.WARNING("\nStep 4/4: Calculating predictions..."))
        call_command('update_predictions')
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("="*70))
        self.stdout.write(self.style.SUCCESS("✅ SETUP COMPLETE!"))
        self.stdout.write(self.style.SUCCESS("="*70))
        self.stdout.write("")
        self.stdout.write("🌐 Dashboard: http://your-server/")
        self.stdout.write("")
        self.stdout.write("💡 Test commands:")
        self.stdout.write("   python manage.py simulate_day        # Advance 1 day")
        self.stdout.write("   python manage.py simulate_day --days 7   # Advance 1 week")
        self.stdout.write("")