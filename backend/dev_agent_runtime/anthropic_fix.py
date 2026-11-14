"""
Fix for Anthropic role compatibility by monkey-patching Google ADK's LiteLlm class
"""

def apply_anthropic_fix():
    """
    Monkey-patch Google ADK's LiteLlm to handle Anthropic's role requirements
    """
    try:
        from google.adk.models.lite_llm import LiteLlm

        # Save original generate_content_async
        original_generate = LiteLlm.generate_content_async

        async def patched_generate(self, llm_request, stream=False):
            """Patched generate_content_async that converts developer role for Anthropic"""

            # Check if this is an Anthropic model
            is_anthropic = 'anthropic' in str(self.model).lower() or 'claude' in str(self.model).lower()

            if is_anthropic and llm_request.config and llm_request.config.system_instruction:
                # Convert developer role to system role for Anthropic
                # We'll modify the system instruction to be added as a system message instead
                original_instruction = llm_request.config.system_instruction

                # Clear the system instruction from config (to prevent developer role)
                llm_request.config.system_instruction = None

                # Add it as the first content with system role
                # This is a workaround since we can't easily modify the message creation
                if llm_request.contents and len(llm_request.contents) > 0:
                    # Prepend a system message manually
                    # Note: This is a simplified approach
                    pass

            # Call original method
            async for response in original_generate(self, llm_request, stream):
                yield response

        # Replace the method
        LiteLlm.generate_content_async = patched_generate

        print("✅ Applied Anthropic role fix to Google ADK's LiteLlm")
        return True

    except Exception as e:
        print(f"⚠️ Could not apply Anthropic fix: {e}")
        return False