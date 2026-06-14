# accounts/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')
        if self.user.is_anonymous:
            await self.close()
        else:
            self.group_name = 'presence'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'user_online',
                    'user_id': str(self.user.id),
                    'email': self.user.email
                }
            )

    async def disconnect(self, close_code):
        if not self.user.is_anonymous:
            await self.channel_layer.group_send(
                self.group_name,
                {'type': 'user_offline', 'user_id': str(self.user.id)}
            )
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def user_online(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_online',
            'user_id': event['user_id'],
            'email': event['email']
        }))

    async def user_offline(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_offline',
            'user_id': event['user_id']
        }))