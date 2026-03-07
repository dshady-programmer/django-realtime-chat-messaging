Error Codes
===========

The package uses custom WebSocket application-level error codes in the ``4000``
range to distinguish domain errors from standard protocol errors. Errors are
**never** sent as WebSocket close frames during normal operation — the connection
stays open and errors are delivered as JSON messages so the client can handle
them gracefully.

Error Payload Format
--------------------

All errors are delivered as JSON messages:

.. code-block:: json

   {
     "error": {
       "code": 4003,
       "detail": "Human-readable description"
     }
   }

Error Codes
-----------

.. list-table::
   :header-rows: 1
   :widths: 15 25 60

   * - Code
     - Name
     - When it occurs
   * - ``4001``
     - Authentication Failed
     - The WebSocket connection was rejected because the user is anonymous or
       unauthenticated. The connection is **closed** with this code (not sent as
       a message).
   * - ``4002``
     - Permission Denied
     - A permission decorator rejected the request. Examples: trying to send a
       message to a room you are not a member of, or trying to delete a room when
       you are not the creator.
   * - ``4003``
     - Validation Error
     - A DRF ``ValidationError`` or Django ``ValidationError`` was raised.
       Examples: invalid room type, missing required field, bad payload structure.
       The ``detail`` field may be a string, list, or nested dictionary.
   * - ``4004``
     - Resource Not Found
     - An ``ObjectDoesNotExist`` or ``Http404`` was raised. Examples: room ID
       does not exist, message ID does not exist.
   * - ``4005``
     - Integrity Error
     - A database constraint was violated. Examples: duplicate reaction,
       duplicate read receipt, duplicate ``OneToOneChat`` between the same two
       users.
   * - ``4006``
     - Internal Server Error
     - An unexpected exception occurred. The full traceback is logged
       server-side. The client receives a generic message to avoid leaking
       implementation details.

Handling Errors on the Client
------------------------------

.. code-block:: javascript

   ws.onmessage = (e) => {
     const msg = JSON.parse(e.data);

     if (msg.error) {
       const { code, detail } = msg.error;
       switch (code) {
         case 4002:
           console.warn("Permission denied:", detail);
           break;
         case 4003:
           console.warn("Validation error:", detail);
           // detail may be an object: { field: ["error message"] }
           break;
         case 4004:
           console.warn("Not found:", detail);
           break;
         case 4005:
           console.warn("Conflict:", detail);
           break;
         case 4006:
           console.error("Server error — try again");
           break;
       }
       return;
     }

     // Handle normal dispatches
     handleDispatch(msg.eventType, msg.data);
   };

The Connection Close Code
--------------------------

Code ``4001`` is the only error that **closes** the connection rather than
delivering a message. On the client:

.. code-block:: javascript

   ws.onclose = (e) => {
     if (e.code === 4001) {
       // Redirect to login, refresh token, etc.
       redirectToLogin();
     }
   };

Invalid Event Types
-------------------

If the client sends an ``event_type`` that is not in the ``EVENT_MAPPER``, the
server responds with:

.. code-block:: json

   {"error": "invalid event type"}

This is not wrapped in the standard error format — it is a plain object. Check
for both formats in your client error handler.

Custom Exception Handlers
--------------------------

To add custom exception types or change error formatting, provide a custom
``EXCEPTION_HANDLER_CLASS``. See :doc:`custom_handlers` for a full example.
