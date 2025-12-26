from functools import wraps
import json



def event_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        
        except Exception as e:
            self = args[0]
            await self.send(text_data=json.dumps({"error": str(e)}))
            # import traceback
            # traceback.print_exc()
            print(f"Error in {func.__name__}: {e}")
    return wrapper





"""


import logging
from functools import wraps

from django.db import IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

logger = logging.getLogger(__name__)


def channel_exception_handler(send_error):
   

    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)

            # DRF / serializer errors
            except DRFValidationError as exc:
                await send_error(self, exc.detail, code="validation_error")

            # Django model validation
            except DjangoValidationError as exc:
                detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                await send_error(self, detail, code="validation_error")

            # DB constraint / uniqueness / FK errors
            except IntegrityError:
                logger.warning("IntegrityError", exc_info=True)
                await send_error(
                    self,
                    "Database constraint violated.",
                    code="integrity_error",
                )

            # ORM object not found
            except ObjectDoesNotExist:
                await send_error(
                    self,
                    "Resource not found.",
                    code="not_found",
                )

            # Everything else (bug / unexpected)
            except Exception:
                logger.exception("Unhandled Channels exception")
                await send_error(
                    self,
                    "Internal server error.",
                    code="server_error",
                )

        return wrapper
    return decorator
"""