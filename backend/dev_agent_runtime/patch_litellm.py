#!/usr/bin/env python3
"""
Patch Google ADK's LiteLLM imports to work with newer LiteLLM versions
"""

import sys
import importlib


def patch_litellm_imports():
    """
    Monkey-patch litellm module to provide compatibility with Google ADK
    """
    import litellm

    # Check if already patched
    if hasattr(litellm, '_ioflow_patched'):
        return

    # Mark as patched
    litellm._ioflow_patched = True

    # Store original functions
    original_completion = getattr(litellm, '_original_completion', litellm.completion)
    original_acompletion = getattr(litellm, '_original_acompletion', litellm.acompletion)

    # Save originals
    litellm._original_completion = original_completion
    litellm._original_acompletion = original_acompletion

    def convert_messages_for_anthropic(messages, model=None):
        """Convert message roles for Anthropic compatibility"""
        if not messages:
            return messages

        # Check if this is an Anthropic model
        is_anthropic = model and ('anthropic' in str(model).lower() or 'claude' in str(model).lower())

        if not is_anthropic:
            return messages

        print(f"[PATCH] Converting messages for Anthropic model: {model}")
        converted = []
        for msg in messages:
            if isinstance(msg, dict):
                msg_copy = dict(msg)
                # Convert developer role to system for Anthropic
                if msg_copy.get('role') == 'developer':
                    print(f"[PATCH] Converting developer role to system for message")
                    msg_copy['role'] = 'system'
                converted.append(msg_copy)
            else:
                # Handle object-based messages (including our patched classes)
                try:
                    # Check if it's a dict-like object (our patched classes)
                    if hasattr(msg, '__getitem__') and hasattr(msg, 'get'):
                        msg_copy = dict(msg)
                        if msg_copy.get('role') == 'developer':
                            msg_copy['role'] = 'system'
                        converted.append(msg_copy)
                    else:
                        # Handle other object types
                        role = getattr(msg, 'role', None)
                        content = getattr(msg, 'content', '')

                        if role == 'developer':
                            converted.append({
                                'role': 'system',
                                'content': content
                            })
                        else:
                            # Try to convert to dict
                            if hasattr(msg, '__dict__'):
                                msg_dict = vars(msg).copy()
                                if msg_dict.get('role') == 'developer':
                                    msg_dict['role'] = 'system'
                                converted.append(msg_dict)
                            else:
                                converted.append(msg)
                except Exception as e:
                    print(f"Warning: Could not convert message: {e}")
                    converted.append(msg)
        return converted

    def patched_completion(*args, **kwargs):
        """Patched completion that converts roles for Anthropic"""
        model = kwargs.get('model', args[0] if args else None)
        if 'messages' in kwargs:
            kwargs['messages'] = convert_messages_for_anthropic(kwargs['messages'], model)
        return original_completion(*args, **kwargs)

    async def patched_acompletion(*args, **kwargs):
        """Patched async completion that converts roles for Anthropic"""
        model = kwargs.get('model', args[0] if args else None)
        if 'messages' in kwargs:
            kwargs['messages'] = convert_messages_for_anthropic(kwargs['messages'], model)
        return await original_acompletion(*args, **kwargs)

    # Replace litellm's functions
    litellm.completion = patched_completion
    litellm.acompletion = patched_acompletion

    # Also patch in the litellm module namespace directly
    import sys
    if 'litellm' in sys.modules:
        sys.modules['litellm'].completion = patched_completion
        sys.modules['litellm'].acompletion = patched_acompletion
        print("✅ Patched litellm.completion and litellm.acompletion in sys.modules")

    # Create aliases for missing classes that Google ADK expects
    # These map to the actual classes in newer LiteLLM

    # ChatCompletionAssistantMessage -> Use dict-based class for JSON serialization
    if not hasattr(litellm, 'ChatCompletionAssistantMessage'):
        class ChatCompletionAssistantMessage(dict):
            def __init__(self, content=None, role="assistant", **kwargs):
                super().__init__(role=role, content=content, **kwargs)
                self.content = content
                self.role = role
                for k, v in kwargs.items():
                    setattr(self, k, v)

        litellm.ChatCompletionAssistantMessage = ChatCompletionAssistantMessage

    # ChatCompletionUserMessage -> Use dict-based class for JSON serialization
    if not hasattr(litellm, 'ChatCompletionUserMessage'):
        class ChatCompletionUserMessage(dict):
            def __init__(self, content=None, role="user", **kwargs):
                super().__init__(role=role, content=content, **kwargs)
                self.content = content
                self.role = role
                for k, v in kwargs.items():
                    setattr(self, k, v)

        litellm.ChatCompletionUserMessage = ChatCompletionUserMessage

    # ChatCompletionToolMessage -> Use dict-based class for JSON serialization
    if not hasattr(litellm, 'ChatCompletionToolMessage'):
        class ChatCompletionToolMessage(dict):
            def __init__(self, content=None, role="tool", tool_call_id=None, **kwargs):
                super().__init__(role=role, content=content, tool_call_id=tool_call_id, **kwargs)
                self.content = content
                self.role = role
                self.tool_call_id = tool_call_id
                for k, v in kwargs.items():
                    setattr(self, k, v)

        litellm.ChatCompletionToolMessage = ChatCompletionToolMessage

    # ChatCompletionDeveloperMessage - Intercept and convert role
    if not hasattr(litellm, 'ChatCompletionDeveloperMessage'):
        class ChatCompletionDeveloperMessage(dict):
            def __init__(self, content=None, role="developer", **kwargs):
                # Accept developer role but store as dict with role that can be converted
                actual_role = role if role != "developer" else "developer"
                super().__init__(role=actual_role, content=content, **kwargs)
                self.content = content
                self.role = actual_role
                self._original_role = role  # Keep track of original
                for k, v in kwargs.items():
                    if k != 'role':
                        setattr(self, k, v)

        litellm.ChatCompletionDeveloperMessage = ChatCompletionDeveloperMessage

    # ChatCompletionAssistantToolCall
    if not hasattr(litellm, 'ChatCompletionAssistantToolCall'):
        # Use the existing ChatCompletionMessageToolCall if available
        if hasattr(litellm, 'ChatCompletionMessageToolCall'):
            litellm.ChatCompletionAssistantToolCall = litellm.ChatCompletionMessageToolCall
        else:
            class ChatCompletionAssistantToolCall(dict):
                def __init__(self, id=None, type="function", function=None, **kwargs):
                    super().__init__(id=id, type=type, function=function, **kwargs)
                    self.id = id
                    self.type = type
                    self.function = function
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            litellm.ChatCompletionAssistantToolCall = ChatCompletionAssistantToolCall

    # Message class (if not present)
    if not hasattr(litellm, 'Message'):
        litellm.Message = dict  # Simple fallback

    # Function class - make it JSON serializable
    if not hasattr(litellm, 'Function'):
        class Function(dict):
            def __init__(self, name=None, arguments=None, **kwargs):
                super().__init__(name=name, arguments=arguments, **kwargs)
                self.name = name
                self.arguments = arguments
                for k, v in kwargs.items():
                    setattr(self, k, v)
                    self[k] = v  # Also store in dict

        litellm.Function = Function

    # CustomStreamWrapper
    if not hasattr(litellm, 'CustomStreamWrapper'):
        litellm.CustomStreamWrapper = object  # Simple fallback

    # OpenAIMessageContent
    if not hasattr(litellm, 'OpenAIMessageContent'):
        litellm.OpenAIMessageContent = dict  # Simple fallback

    # CRITICAL: Also patch Google ADK's imported references
    try:
        # Check if Google ADK has already imported litellm functions
        import sys
        if 'google.adk.models.lite_llm' in sys.modules:
            lite_llm_module = sys.modules['google.adk.models.lite_llm']

            # Replace the directly imported functions in Google ADK's namespace
            if hasattr(lite_llm_module, 'acompletion'):
                lite_llm_module.acompletion = patched_acompletion
                print("✅ Patched acompletion in google.adk.models.lite_llm")

            if hasattr(lite_llm_module, 'completion'):
                lite_llm_module.completion = patched_completion
                print("✅ Patched completion in google.adk.models.lite_llm")
    except Exception as e:
        print(f"⚠️ Could not patch Google ADK's imported functions: {e}")

    print("✅ LiteLLM compatibility patches applied successfully")


if __name__ == "__main__":
    patch_litellm_imports()

    # Test the imports
    try:
        from google.adk.models.lite_llm import LiteLlm
        print("✅ Google ADK LiteLLM import successful after patching")
    except ImportError as e:
        print(f"❌ Import still failing: {e}")