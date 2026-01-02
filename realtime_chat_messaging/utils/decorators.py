from functools import wraps
import json
import logging

from django.db import IntegrityError
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

logger = logging.getLogger(__name__)


def send_error(consumer, detail, func, exc, code=4003):
    """
    Utility function to send error messages to the WebSocket client.
    """
    error_payload = {
        "error": {
            "code": code,
            "detail": detail
        }
    }
    logger.error(f"Error in {func.__name__}: {exc}", exc_info=True)
    return consumer.send(text_data=json.dumps(error_payload))

def event_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        self = args[0]
        try:
            return await func(*args, **kwargs)
        
        # DRF / serializer errors
        except DRFValidationError as exc:
            await send_error(self, exc.detail, func, exc, code=4003)

        # Django model validation
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            await send_error(self, detail, func, exc, code=4003)
        
        # DB constraint / uniqueness / FK errors
        except IntegrityError as e:
            await send_error(
                self,
                "Database constraint violated.",
                func,
                e,
                code=4005,
            )
        # ORM object not found
        except ObjectDoesNotExist as e:
            await send_error(
                self,
                "Resource not found.",
                func,
                e,
                code=4004,
            )

        # Permission issues
        except PermissionDenied as e:
            await send_error(
                self,
                str(e),
                func,
                e,
                code=4002,
            )
        # Everything else (bug / unexpected)
        except Exception as e:
            await send_error(
                self,
                "Internal server error.",
                func,
                e,
                code=4006,
            )


            
    return wrapper

