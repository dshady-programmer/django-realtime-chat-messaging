from django.contrib import admin

# Register your models here.
from .models import  Message, Room, GroupChat, Channel, OneToOneChat, ReadReceipt, Reaction, ChatNotification


admin.site.register(Message)
admin.site.register(Room)
admin.site.register(GroupChat)
admin.site.register(Channel)
admin.site.register(OneToOneChat)
admin.site.register(ReadReceipt)
admin.site.register(Reaction)
admin.site.register(ChatNotification)