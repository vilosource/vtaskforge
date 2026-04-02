from django.core.management.base import BaseCommand

from prefs.services import create_service_account


class Command(BaseCommand):
    help = "Create a service account with a token"

    def add_arguments(self, parser):
        parser.add_argument("name", type=str, help="Service account username")

    def handle(self, *args, **options):
        name = options["name"]
        user, token = create_service_account(name)
        self.stdout.write(f"Created service account: {name}")
        self.stdout.write(f"Token: {token.key}")
