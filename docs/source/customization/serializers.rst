Serializer Customization
========================

Customizing serializers to handle custom model fields and change JSON output.

.. contents:: Table of Contents
   :local:
   :depth: 1

Basic Customization
-------------------

Extending MessageSerializer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import MessageSerializer as BaseMessageSerializer
   from rest_framework import serializers

   class CustomMessageSerializer(BaseMessageSerializer):
       priority = serializers.CharField(read_only=True)
       is_pinned = serializers.BooleanField(read_only=True)
       
       class Meta(BaseMessageSerializer.Meta):
           model = CustomMessage
           fields = BaseMessageSerializer.Meta.fields + ['priority', 'is_pinned']

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer"
       }
   }

Extending RoomPolymorphicSerializer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When extending Room model:

.. code-block:: python

   from realtime_chat_messaging.serializers import RoomPolymorphicSerializer as BaseRoomSerializer

   class CustomRoomPolymorphicSerializer(BaseRoomSerializer):
       model_serializer_mapping = {
           CustomOneToOneChat: CustomOneToOneChatSerializer,
           CustomGroupChat: CustomGroupChatSerializer,
           CustomChannel: CustomChannelSerializer,
       }
       
       def create(self, _):
           # MUST override if Room model changed
           # Copy logic from base and adapt
           pass

Dynamic Model Loading
---------------------

Serializers use dynamic model loading via ``get_model()``:

.. code-block:: python

   from realtime_chat_messaging.utils.loader import get_model

   Message = get_model("Message")
   Room = get_model("Room")

   class CustomSerializer(serializers.ModelSerializer):
       room = serializers.PrimaryKeyRelatedField(
           queryset=get_model("Room").objects.all()
       )

Common Patterns
---------------

Computed Fields
~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessageSerializer(BaseMessageSerializer):
       is_from_admin = serializers.SerializerMethodField()
       
       def get_is_from_admin(self, obj):
           return obj.sender.is_staff

Custom Validation
~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessageSerializer(BaseMessageSerializer):
       def validate_content(self, value):
           # Call parent validation
           value = super().validate_content(value)
           
           # Custom checks
           if len(value) > 5000:
               raise serializers.ValidationError("Message too long")
           
           return value

See Also
--------

* :doc:`models` - Custom models
* :doc:`../api-reference/settings` - SERIALIZERS setting