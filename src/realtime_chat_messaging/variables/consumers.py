map_event_type_to_handlers = lambda self:  {
            "message.send": self.receive_message_send_event,
            "message.acknowledged": self.receive_message_acknowledged_event,
            "message.read": self.receive_message_read_event,
            "message.react": self.receive_message_reaction_event, 
            "message.typing": self.receive_message_typing_event,
            "message.modify": self.receive_message_modify_event,
            "room.create": self.receive_room_create_event,
            "room.list": self.receive_get_rooms,
            "room.info": self.receive_get_room_info,
            "room.add_members": self.receive_add_members_to_room,
            "room.remove_members": self.receive_remove_members_from_room,
            "room.messages": self.receive_message_list,
            "room.join": self.receive_join_room_event,
            "room.leave": self.receive_leave_room_event,
            "room.modify": self.receive_modify_room_event, # add or remove admins/moderators (for the user),  change name/description/preferences,
            "session.heartbeat": self.receive_update_session_heartbeat

        }


