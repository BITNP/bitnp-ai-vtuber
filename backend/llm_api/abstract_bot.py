from typing import Callable
import asyncio

class AbstractBot:
    def __init__(self):
        self.messages = []
        self._event_handlers: dict[str, list[Callable[dict, None]]] = {}

    def on(self, name_of_event: str):
        """
        Register a function to be called when the event is dispatched
        
        Args:
            name_of_event (str): The name of the event to register the function for
        
        Usage:
            ```
            @bot.on('message_delta')
            def handle_message_delta(data):
                print(data['content'], end='', flush=True)
            ```
        """
        def decorator(func: Callable[dict, None]):
            if name_of_event not in self._event_handlers:
                self._event_handlers[name_of_event] = []
            self._event_handlers[name_of_event].append(func)
            return func
        return decorator

    async def _dispatch_event(self, name_of_event: str, data: dict = None):
        """
        Dispatch an event to the registered function

        Args:
            name_of_event (str): The name of the event to dispatch
            data (dict, optional): The data to pass to the event handler. Defaults to None.

        Recommended event names:
            - 'message_delta': Called when a new message delta (a short chunk of text) is received
            - 'done': Called when the response is done
        """
        if name_of_event in self._event_handlers:
            for func in self._event_handlers[name_of_event]:
                if asyncio.iscoroutinefunction(func):
                    await func(data)
                else:
                    func(data)

    def append_context(self, text: str, role: str = 'user'):
        """Append context to messages"""
        self.messages.append({
            'role': role,
            'content': text,
        })

    async def respond_to_context(self, messages = None) -> str:
        """Send messages to the LLM API and stream the response"""
        raise NotImplementedError("respond_to_context method must be implemented")