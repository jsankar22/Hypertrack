import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fitness_assistant.settings')
application = get_wsgi_application()

def wsgi_application(environ, start_response):
    return application(environ, start_response)
