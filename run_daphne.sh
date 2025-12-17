#!/bin/bash
daphne -b 0.0.0.0 -p 8000 django_realtime_chat_messaging.asgi:application