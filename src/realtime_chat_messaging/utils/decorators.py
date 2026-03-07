"""
Exception handling utilities for WebSocket consumers.

This module provides a centralized exception handling mechanism for Django
Channels consumers, ensuring consistent error responses and proper logging
across all WebSocket event handlers.

The ExceptionHandler class implements a decorator pattern that catches common
Django and DRF exceptions, maps them to custom WebSocket close codes, and
sends standardized error payloads to clients.
"""

from functools import wraps
import json
import logging

from django.db import IntegrityError
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.http.response import Http404

logger = logging.getLogger(__name__)


class ExceptionHandler:
    """
        Centralized exception handler for WebSocket consumers.

        This class provides a decorator that wraps consumer event handlers with
        comprehensive exception handling. It catches common Django/DRF exceptions,
        logs errors, and sends structured error responses to WebSocket clients.

        The handler uses custom WebSocket close codes (4000-4999 range) to
        distinguish application-level errors from standard WebSocket protocol
        errors, enabling clients to implement specific error handling logic.

        Custom Close Codes:
            - 4002: Permission denied (authorization failures)
            - 4003: Validation error (invalid input data)
            - 4004: Resource not found (missing database objects)
            - 4005: Integrity error (database constraint violations)
            - 4006: Internal server error (unexpected exceptions)
    """

    def send_error(consumer, detail, func, exc, code=4003):
        """
            Send a structured error message to the WebSocket client.

            This utility method formats error details into a standardized JSON
            payload and sends it through the consumer's WebSocket connection.
            It also logs the full exception traceback for debugging (in the terminal).

            Args:
                consumer: The WebSocket consumer instance.
                detail (str | dict | list): Human-readable error description.
                    Can be a string, dictionary, or list depending on the
                    exception type.
                func (callable): The function where the error occurred (used for
                    logging context).
                exc (Exception): The original exception instance.
                code (int, optional): Custom WebSocket close code. Defaults to
                    4003 (validation error).

            Returns:
                Coroutine: An awaitable that sends the error payload to the client.

            Example:
                Error payload sent to client::

                    {
                        "error": {
                            "code": 4003,
                            "detail": "Invalid room_id format"
                        }
                    }

            Note:
                This method logs the full exception traceback using Python's
                logging framework, which is essential for production debugging.
        """
        error_payload = {
            "error": {
                "code": code,
                "detail": detail
            }
        }
        logger.error(f"Error in {func.__name__}: {exc}", exc_info=True)
        return consumer.send(text_data=json.dumps(error_payload))

    @classmethod
    def exception_handler_decorator(cls, func):
        """
            Decorator that wraps consumer methods with exception handling.

            This decorator catches exceptions thrown during event handler execution
            and converts them into structured error responses. It ensures that
            WebSocket connections remain stable even when errors occur, preventing
            unexpected disconnections.



            Args:
                func (callable): The async function to wrap (typically a consumer
                    event handler method).

            Returns:
                callable: The wrapped async function with exception handling.

            Raises:
                None: All exceptions are caught and converted to error messages.

            Exception Handling:
                - DRFValidationError: Serializer validation failures (code 4003)
                - DjangoValidationError: Model validation failures (code 4003)
                - IntegrityError: Database constraint violations (code 4005)
                - ObjectDoesNotExist: Missing database objects (code 4004)
                - Http404: Resource not found (code 4004)
                - PermissionDenied: Authorization failures (code 4002)
                - Exception: All other unexpected errors (code 4006)

            Example:
                Usage in a consumer::

                    class ChatConsumer(AsyncWebsocketConsumer):
                        @ExceptionHandler.exception_handler_decorator
                        async def receive_message_send(self, data):
                            # If this raises ValidationError, client receives:
                            # {"error": {"code": 4003, "detail": "Invalid data"}}
                            message = await create_message(data)

            Note:
                This decorator should be applied to all event handler methods in
                your consumer to ensure consistent error handling across the
                application.

                You can override with custom ExceptionHandler class in settings 
                with `EXCEPTION_HANDLER_CLASS`
        """

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            
            # DRF / serializer errors
            except DRFValidationError as exc:
                await cls.send_error(
                    self, 
                    exc.detail, 
                    func, 
                    exc, 
                    code=4003
                )

            # Django model validation
            except DjangoValidationError as exc:
                detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                await cls.send_error(
                    self, 
                    detail, 
                    func, 
                    exc, 
                    code=4003
                )
            
            # DB constraint / uniqueness / FK errors
            except IntegrityError as e:
                await cls.send_error(
                    self,
                    "Database constraint violated.",
                    func,
                    e,
                    code=4005,
                )
            # ORM object not found
            except ObjectDoesNotExist as e:
                await cls.send_error(
                    self,
                    "Resource not found.",
                    func,
                    e,
                    code=4004,
                )
            except Http404 as e:
                await cls.send_error(
                    self,
                    "Resource not found.",
                    func,
                    e,
                    code=4004,
                )

            # Permission issues
            except PermissionDenied as e:
                await cls.send_error(
                    self,
                    str(e),
                    func,
                    e,
                    code=4002,
                )
            # Everything else (bug / unexpected)
            except Exception as e:
                await cls.send_error(
                    self,
                    "Internal server error.",
                    func,
                    e,
                    code=4006,
                )


                
        return wrapper




from django.db import connection
from channels.db import database_sync_to_async


def sqlite_safe_db_sync_to_async(func):
    """
        Wrapper around database_sync_to_async for SQLite compatibility especially if
        you're running on Django 6.0.

        This decorator ensures that the database connection is properly initialized
        before executing synchronous database operations in an async context. It
        fixes a specific SQLite bug where connection.connection can be None,
        causing AttributeError on getlimit() calls.

        Args:
            func (callable): The synchronous function that performs database
                operations.

        Returns:
            callable: An async-safe version of the function that ensures the
                database connection is active.

        Raises:
            AttributeError: Prevented by ensuring connection before execution.

        Example:
            Usage::

                @sqlite_safe_db_sync_to_async
                def get_user(user_id):
                    return User.objects.get(id=user_id)

                # Can now be called from async context
                user = await get_user(123)

        Bug Context:
            Without this wrapper, SQLite connections can be in an uninitialized
            state when accessed from async contexts, causing::

                AttributeError: 'NoneType' object has no attribute 'getlimit'
                at self.connection.connection.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER)

        Note:
            This is specifically needed for SQLite databases. PostgreSQL, MySQL,
            and other databases typically do not exhibit this issue, but using
            this wrapper is harmless and ensures cross-database compatibility.
    """

    @database_sync_to_async
    def wrapper(*args, **kwargs):
        connection.ensure_connection()
        return func(*args, **kwargs)
    return wrapper
 