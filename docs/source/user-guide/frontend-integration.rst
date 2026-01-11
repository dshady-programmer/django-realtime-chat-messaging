Frontend Integration
====================

Quick examples for integrating with popular frontend frameworks.

.. contents:: Table of Contents
   :local:
   :depth: 1

Vanilla JavaScript
------------------

.. code-block:: javascript

   class ChatClient {
       constructor(roomId) {
           this.roomId = roomId;
           this.socket = null;
           this.connect();
       }

       connect() {
           this.socket = new WebSocket('ws://localhost:8000/messaging/');
           
           this.socket.onopen = () => this.onConnect();
           this.socket.onmessage = (e) => this.onMessage(JSON.parse(e.data));
           this.socket.onerror = (e) => console.error('WebSocket error:', e);
           this.socket.onclose = (e) => this.onDisconnect(e);
       }

       onConnect() {
           console.log('Connected');
           this.loadMessages();
       }

       onMessage(response) {
           switch(response.eventType) {
               case 'message.dispatch':
                   this.displayMessage(response.data);
                   break;
               case 'roommessages.dispatch':
                   this.displayMessages(response.data.messages);
                   break;
           }
       }

       sendMessage(content) {
           this.socket.send(JSON.stringify({
               event_type: 'message.send',
               data: {room_id: this.roomId, content}
           }));
       }

       loadMessages() {
           this.socket.send(JSON.stringify({
               event_type: 'room.messages',
               data: {room_id: this.roomId, paginate: {page: 1, size: 50}}
           }));
       }
   }

   // Usage
   const chat = new ChatClient('room-uuid');
   document.getElementById('send-btn').onclick = () => {
       const input = document.getElementById('message-input');
       chat.sendMessage(input.value);
       input.value = '';
   };

React
-----

.. code-block:: javascript

   import { useState, useEffect, useCallback } from 'react';

   function useChat(roomId) {
       const [socket, setSocket] = useState(null);
       const [messages, setMessages] = useState([]);
       const [connected, setConnected] = useState(false);

       useEffect(() => {
           const ws = new WebSocket('ws://localhost:8000/messaging/');
           
           ws.onopen = () => {
               setConnected(true);
               ws.send(JSON.stringify({
                   event_type: 'room.messages',
                   data: {room_id: roomId, paginate: {page: 1, size: 50}}
               }));
           };

           ws.onmessage = (e) => {
               const response = JSON.parse(e.data);
               if (response.eventType === 'message.dispatch') {
                   setMessages(prev => [...prev, response.data]);
               } else if (response.eventType === 'roommessages.dispatch') {
                   setMessages(response.data.messages.reverse());
               }
           };

           ws.onclose = () => setConnected(false);
           
           setSocket(ws);
           return () => ws.close();
       }, [roomId]);

       const sendMessage = useCallback((content) => {
           if (socket && connected) {
               socket.send(JSON.stringify({
                   event_type: 'message.send',
                   data: {room_id: roomId, content}
               }));
           }
       }, [socket, connected, roomId]);

       return {messages, sendMessage, connected};
   }

   function ChatRoom({roomId}) {
       const {messages, sendMessage, connected} = useChat(roomId);
       const [input, setInput] = useState('');

       const handleSend = () => {
           sendMessage(input);
           setInput('');
       };

       return (
           <div>
               <div className="messages">
                   {messages.map(msg => (
                       <div key={msg.id}>
                           <strong>{msg.sender.username}</strong>: {msg.content}
                       </div>
                   ))}
               </div>
               <input value={input} onChange={e => setInput(e.target.value)} />
               <button onClick={handleSend} disabled={!connected}>Send</button>
           </div>
       );
   }

Vue.js
------

.. code-block:: javascript

   // useChat.js
   import { ref, onMounted, onUnmounted } from 'vue';

   export function useChat(roomId) {
       const socket = ref(null);
       const messages = ref([]);
       const connected = ref(false);

       const connect = () => {
           socket.value = new WebSocket('ws://localhost:8000/messaging/');
           
           socket.value.onopen = () => {
               connected.value = true;
               socket.value.send(JSON.stringify({
                   event_type: 'room.messages',
                   data: {room_id: roomId, paginate: {page: 1, size: 50}}
               }));
           };

           socket.value.onmessage = (e) => {
               const response = JSON.parse(e.data);
               if (response.eventType === 'message.dispatch') {
                   messages.value.push(response.data);
               } else if (response.eventType === 'roommessages.dispatch') {
                   messages.value = response.data.messages.reverse();
               }
           };

           socket.value.onclose = () => connected.value = false;
       };

       const sendMessage = (content) => {
           if (socket.value && connected.value) {
               socket.value.send(JSON.stringify({
                   event_type: 'message.send',
                   data: {room_id: roomId, content}
               }));
           }
       };

       onMounted(connect);
       onUnmounted(() => socket.value?.close());

       return {messages, sendMessage, connected};
   }

   // ChatRoom.vue
   <template>
       <div>
           <div v-for="msg in messages" :key="msg.id">
               <strong>{{ msg.sender.username }}</strong>: {{ msg.content }}
           </div>
           <input v-model="input" @keyup.enter="handleSend" />
           <button @click="handleSend" :disabled="!connected">Send</button>
       </div>
   </template>

   <script setup>
   import { ref } from 'vue';
   import { useChat } from './useChat';

   const props = defineProps(['roomId']);
   const {messages, sendMessage, connected} = useChat(props.roomId);
   const input = ref('');

   const handleSend = () => {
       sendMessage(input.value);
       input.value = '';
   };
   </script>

Key Patterns
------------

Connection Management
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   function connectWithRetry() {
       let attempts = 0;
       const maxAttempts = 5;

       function connect() {
           const ws = new WebSocket('ws://localhost:8000/messaging/');
           
           ws.onclose = (e) => {
               if (e.code !== 1000 && attempts < maxAttempts) {
                   setTimeout(() => {
                       attempts++;
                       connect();
                   }, Math.min(1000 * Math.pow(2, attempts), 30000));
               }
           };
           
           return ws;
       }

       return connect();
   }

Event Routing
~~~~~~~~~~~~~

.. code-block:: javascript

   const eventHandlers = {
       'message.dispatch': (data) => addMessage(data),
       'messagetyping.dispatch': (data) => showTyping(data.username),
       'reaction.dispatch': (data) => updateReaction(data),
       'readreceipt.dispatch': (data) => updateReadReceipts(data),
   };

   socket.onmessage = (e) => {
       const {eventType, data} = JSON.parse(e.data);
       eventHandlers[eventType]?.(data);
   };

State Management
~~~~~~~~~~~~~~~~

.. code-block:: javascript

   // Redux/Zustand style
   const chatStore = {
       messages: [],
       rooms: [],
       socket: null,
       
       setSocket(socket) {
           this.socket = socket;
       },
       
       addMessage(message) {
           this.messages.push(message);
       },
       
       sendMessage(roomId, content) {
           this.socket?.send(JSON.stringify({
               event_type: 'message.send',
               data: {room_id: roomId, content}
           }));
       }
   };

See Also
--------

* :doc:`authentication` - JWT for SPAs
* :doc:`../api-reference/events` - All events
* :doc:`../getting-started/quickstart` - Complete examples